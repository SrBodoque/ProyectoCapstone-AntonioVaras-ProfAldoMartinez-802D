import sys
import unittest
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

import numpy as np

from src import track_count
from src.config import load_config, load_detection_config
from src.count_engine import EntryCounter, Phase
from src.counting_config import load_counting_config, select_tracker
from src.detector import Detection
from src.tracker import FrameTracks, Track
from src.zones import ZoneError
from count_test_support import ENTRY, profile
from zone_test_support import make_ui, camera_module


class IntegrationTests(unittest.TestCase):
    def setup_run(self, name='botsort_reid'):
        ui, capture, _ = make_ui()
        frame = np.full((480,480,3),70,dtype=np.uint8)
        capture.read.side_effect = lambda: (True, frame.copy())
        engine = MagicMock()
        engine.config = {**load_detection_config(), 'device':'cpu'}
        selection = select_tracker(name)
        engine.bytetrack_config = selection.tracker_params
        engine.tracking_confidence = selection.confidence_override or .65
        engine.track.return_value = FrameTracks((),(),1.,2.)
        return ui,capture,engine,selection

    def run_app(self, ui, engine, selection, counter=None, clock=None):
        counter = counter or EntryCounter(profile())
        with camera_module(ui), patch.object(track_count, 'PersonTracker', return_value=engine) as factory:
            total = track_count.run_count(ui,load_config(),load_detection_config(),selection,counter,clock=clock)
        return total, factory

    def test_real_fsm_receives_bottom_centers_and_counts_in_single_inference_loop(self):
        ui,capture,engine,selection = self.setup_run()
        ui.waitKey.side_effect = [-1]*(len(ENTRY)-1)+[ord('q')]
        results=[]
        for _,x,y in ENTRY:
            results.append(FrameTracks((Track(x*480-12,y*480-100,x*480+12,y*480,.9,0,1),),(),2.,3.))
        engine.track.side_effect=results
        clock=iter(t for t,_,_ in ENTRY)
        total,factory=self.run_app(ui,engine,selection,clock=lambda:next(clock))
        self.assertEqual(total,1)
        self.assertEqual(engine.track.call_count,len(ENTRY))
        factory.assert_called_once_with(load_detection_config(), selection.tracking_config)
        capture.open.assert_called_once()
        self.assertEqual(capture.open.call_args.args[0],load_config()['camera_index'])
        capture.release.assert_called_once()
        texts=[call.args[1] for call in ui.putText.call_args_list]
        self.assertTrue(any('ENTRADAS AL BANO: 1' in text for text in texts))
        self.assertTrue(any('FPS:' in text and 'YOLO + tracking' in text for text in texts))

    def test_each_tracker_passes_its_constructor_options(self):
        for name in ('botsort_reid','fasttracker','bytetrack','recovery'):
            with self.subTest(name=name):
                ui,_,engine,selection=self.setup_run(name)
                _,factory=self.run_app(ui,engine,selection)
                factory.assert_called_once_with(load_detection_config(),selection.tracking_config,**selection.constructor_options())

    def test_only_shared_engine_resolves_cpu_cuda(self):
        for device in ('cpu','cuda:0','cuda:1'):
            ui,_,engine,selection=self.setup_run()
            engine.config['device']=device
            self.run_app(ui,engine,selection)
            texts=[c.args[1] for c in ui.putText.call_args_list]
            self.assertTrue(any(device in t and 'Tracker:' in t for t in texts))

    def test_overlays_follow_raw_frame_inference(self):
        ui,_,engine,selection=self.setup_run()
        def infer(frame):
            self.assertTrue(np.all(frame==70))
            self.assertFalse(ui.fillPoly.called)
            return FrameTracks((),(),None,2.)
        engine.track.side_effect=infer
        self.run_app(ui,engine,selection)
        self.assertTrue(ui.fillPoly.called)

    def test_adapter_uses_bottom_center_and_excludes_untracked_from_counter(self):
        box=Track(20.,10.,40.,80.,.9,0,7)
        obs=track_count.frame_observations((box,),100,100)[0]
        self.assertEqual(obs.point,(.3,.8))
        ui,_,engine,selection=self.setup_run()
        engine.track.return_value=FrameTracks((),(Detection(10.,10.,40.,100.,.9,0),),1.,2.)
        counter=EntryCounter(profile())
        self.run_app(ui,engine,selection,counter)
        self.assertEqual(counter.states,{})
        self.assertTrue(any('Sin ID' in c.args[1] for c in ui.putText.call_args_list))

    def test_camera_or_aspect_mismatch_blocks_before_loading_model(self):
        for p in (profile(width=640,height=480),):
            ui,capture,engine,selection=self.setup_run()
            with camera_module(ui), patch.object(track_count,'PersonTracker') as factory:
                with self.assertRaisesRegex(ValueError,'aspecto'):
                    track_count.run_count(ui,load_config(),load_detection_config(),selection,EntryCounter(p))
            factory.assert_not_called();capture.release.assert_called_once()
        ui,capture,engine,selection=self.setup_run()
        camera={**load_config(),'camera_index':2}
        with camera_module(ui),patch.object(track_count,'PersonTracker') as factory:
            with self.assertRaisesRegex(ValueError,'cámara'):
                track_count.run_count(ui,camera,load_detection_config(),selection,EntryCounter(profile()))
        factory.assert_not_called();capture.release.assert_called_once()

    def test_changed_frame_aspect_stops_before_second_inference(self):
        ui,capture,engine,selection=self.setup_run()
        capture.read.side_effect=[(True,np.zeros((480,480,3),np.uint8)),(True,np.zeros((480,640,3),np.uint8))]
        ui.waitKey.return_value=-1
        with self.assertRaisesRegex(ValueError,'aspecto'):self.run_app(ui,engine,selection)
        self.assertEqual(engine.track.call_count,1);capture.release.assert_called_once()

    def test_q_esc_x_and_destroyed_window_release(self):
        for mode in ('q','esc','x','destroyed'):
            ui,capture,engine,selection=self.setup_run()
            if mode=='esc':ui.waitKey.return_value=27
            if mode in ('x','destroyed'):ui.waitKey.return_value=-1
            if mode=='x':ui.getWindowProperty.return_value=-1
            if mode=='destroyed':ui.getWindowProperty.side_effect=ui.error('closed')
            self.run_app(ui,engine,selection)
            capture.release.assert_called_once();ui.destroyAllWindows.assert_called_once()

    def test_ctrl_c_read_and_inference_errors_release(self):
        for mode in ('ctrl_c','read','inference','draw'):
            ui,capture,engine,selection=self.setup_run()
            if mode=='ctrl_c':ui.waitKey.side_effect=KeyboardInterrupt()
            if mode=='read':
                ui.waitKey.return_value=-1
                capture.read.side_effect=[(True,np.zeros((480,480,3),np.uint8)),(False,None)]
            if mode=='inference':engine.track.side_effect=RuntimeError('tracker unavailable')
            if mode=='draw':ui.imshow.side_effect=ui.error('window error')
            with self.subTest(mode=mode),self.assertRaises((KeyboardInterrupt,RuntimeError,ui.error)):
                self.run_app(ui,engine,selection)
            capture.release.assert_called_once();ui.destroyAllWindows.assert_called_once()

    def test_model_construction_and_camera_open_errors_release(self):
        ui,capture,_,selection=self.setup_run()
        with camera_module(ui),patch.object(track_count,'PersonTracker',side_effect=RuntimeError('missing tracker')):
            with self.assertRaises(RuntimeError):
                track_count.run_count(ui,load_config(),load_detection_config(),selection,EntryCounter(profile()))
        capture.release.assert_called_once()
        ui,capture,engine,selection=self.setup_run()
        capture.open.return_value=False
        with self.assertRaises(RuntimeError):self.run_app(ui,engine,selection)
        self.assertGreaterEqual(capture.release.call_count,1)

    def test_missing_or_corrupt_profile_exits_without_camera_model_or_writes(self):
        for message in ('No existe una configuración activa. Ejecute python -m src.zone_calibrator','JSON inválido'):
            with patch.object(track_count,'ZoneStore') as store,patch.object(track_count,'PersonTracker') as factory:
                store.return_value.load_active.side_effect=ZoneError(message)
                with self.assertLogs(track_count.LOGGER,level='ERROR'):self.assertEqual(track_count.main(),1)
                factory.assert_not_called()
                store.return_value.save_and_activate.assert_not_called()

    def test_main_loads_existing_profile_and_config_without_selectors(self):
        ui,_,_,_=self.setup_run()
        with patch.dict(sys.modules,{'cv2':ui}),patch.dict('os.environ',{'DISPLAY':':simulated'}), \
             patch.object(track_count,'ZoneStore') as store,patch.object(track_count,'run_count') as run:
            store.return_value.load_active.return_value=profile()
            self.assertEqual(track_count.main(),0)
            args=run.call_args.args
            self.assertEqual(args[3].name,'botsort_reid')
            self.assertEqual(args[4].geometry.profile,profile())
            self.assertEqual(args[4].total_entries,0)
            store.return_value.load_active.assert_called_once()
            store.return_value.activate.assert_not_called()
            store.return_value.save_and_activate.assert_not_called()

    def test_main_reports_invalid_count_config_and_handles_ctrl_c(self):
        ui,_,_,_=self.setup_run()
        with patch.object(track_count,'ZoneStore') as store:
            store.return_value.load_active.return_value=profile()
            with patch.object(track_count,'load_counting_config',side_effect=ValueError('bad config')):
                with self.assertLogs(track_count.LOGGER,level='ERROR'):self.assertEqual(track_count.main(),1)
            with patch.dict(sys.modules,{'cv2':ui}),patch.dict('os.environ',{'DISPLAY':':simulated'}), \
                 patch.object(track_count,'run_count',side_effect=KeyboardInterrupt()):
                self.assertEqual(track_count.main(),0)


if __name__=='__main__':unittest.main()
