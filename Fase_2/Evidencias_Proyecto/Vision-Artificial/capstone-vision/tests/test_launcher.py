"""Launcher orchestration, native probes, calibration exports and real Tk cancellation."""
from contextlib import contextmanager
import json
import gc
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import MagicMock,patch
import numpy as np

from src import launcher,launcher_calibration as calibration,launcher_probe as probes
from src.launcher_calibration import Cancelled
from src.camera_selector import AvailableCamera
from h52_test_support import fixture,profile
from video_test_support import temporary_directory


class FakeUI:
    def __init__(self):
        self.choose=MagicMock(side_effect=Cancelled)
        self.menu=MagicMock(side_effect=Cancelled)
        self.open_video=MagicMock(side_effect=Cancelled)
        self.open_json=MagicMock(side_effect=Cancelled)
        self.save_json=MagicMock(side_effect=Cancelled)
        self.confirm=MagicMock(return_value=True)
        self.text=MagicMock(return_value='Automated reviewer')
        self.integer=MagicMock(return_value=0)
        self.manual_camera=MagicMock(return_value=(2,'msmf'))
        self.notice=MagicMock();self.error=MagicMock();self.close=MagicMock()
        self.run_view=MagicMock(return_value=False)
        self.settings=MagicMock(side_effect=lambda args,p:('bytetrack','cpu',args.weights_dir))
    def busy(self,fn,title):return fn(NS(is_set=lambda:False))


class LauncherTests(unittest.TestCase):
    def setUp(self):
        gc.collect()
        self.temp=temporary_directory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        env=patch.dict('os.environ',{'LOCALAPPDATA':str(self.root/'userdata')});env.start();self.addCleanup(env.stop)
        roots=patch('src.launcher_resources.resource_roots',return_value=[self.root]);roots.start();self.addCleanup(roots.stop)
        self.video,self.case,self.zones=fixture(self.root,real_video=True)
        self.weights=self.root/'weights';self.weights.mkdir();(self.weights/'yolo26n.pt').write_bytes(b'synthetic; never loaded')
        self.ui=FakeUI();self.controller=launcher.Launcher(self.ui)
        self.camera=AvailableCamera(0,160,160,'MSMF',30.)
    def tearDown(self):
        gc.collect()

    def args(self,*args):
        return launcher.parser().parse_args([*args,'--device','cpu','--weights-dir',str(self.weights)])
    def video_args(self):return self.args('--mp4','--video',str(self.video),'--zones',str(self.zones))

    def test_cli_source_contract_and_validation(self):
        for flags in (('--mp4',),('--camara',),('--calibrar','--mp4'),('--calibrar','--camara')):
            args=self.args(*flags);launcher.validate_args(args)
        with patch('sys.stderr'),self.assertRaises(SystemExit):launcher.parser().parse_args(['--mp4','--camara'])
        for flags in (('--mp4','--tracking-only'),('--camera-index','-1'),('--camera-limit','17'),('--probe-timeout','0'),('--frame','-1')):
            with self.assertRaises(ValueError):launcher.validate_args(self.args(*flags))

    def test_direct_mp4_reuses_existing_presentation_options(self):
        prepared=self.controller.prepare(self.video_args())
        self.assertEqual((prepared.source,prepared.video,prepared.zones),('video',self.video,self.zones))
        self.assertEqual((prepared.tracker,prepared.device,prepared.realtime),('bytetrack','cpu',True))
        self.assertFalse(prepared.tracking_only)
        self.ui.open_video.assert_not_called();self.ui.open_json.assert_not_called()

    def test_mp4_dialog_and_profile_selection(self):
        self.ui.open_video.return_value=self.video;self.ui.open_video.side_effect=None
        self.ui.open_json.return_value=self.zones;self.ui.open_json.side_effect=None
        self.ui.choose.side_effect=None;self.ui.choose.return_value='existing'
        result=self.controller.prepare(self.args('--mp4'))
        self.assertEqual(result.video,self.video);self.assertEqual(result.zones,self.zones)

    def test_cancel_video_selection(self):
        with self.assertRaises(Cancelled):self.controller.prepare(self.args('--mp4'))
        self.ui.run_view.assert_not_called()

    def test_missing_and_corrupt_mp4(self):
        for name in ('absent.mp4','corrupt.mp4'):
            video=self.root/name
            if name.startswith('corrupt'):video.write_bytes(b'not an mp4')
            with self.assertRaises((ValueError,RuntimeError)):
                self.controller.prepare(self.args('--mp4','--video',str(video),'--zones',str(self.zones)))

    def test_invalid_json_schema_and_video_hash(self):
        for content in ('not json','{}',self.zones.read_text(encoding='utf-8').replace('video3','wrong')):
            bad=self.root/'bad.json';bad.write_text(content,encoding='utf-8')
            if content==self.zones.read_text(encoding='utf-8'):continue
            with self.assertRaises(ValueError):self.controller.prepare(self.args('--mp4','--video',str(self.video),'--zones',str(bad)))
        data=json.loads(self.zones.read_text(encoding='utf-8'));data['video_sha256']='0'*64
        bad.write_text(json.dumps(data),encoding='utf-8')
        with self.assertRaises(ValueError):self.controller.prepare(self.args('--mp4','--video',str(self.video),'--zones',str(bad)))

    def test_single_camera_is_automatic_and_tracking_only(self):
        with patch.object(launcher,'scan_cameras',return_value=[self.camera]) as scan:
            result=self.controller.prepare(self.args('--camara','--tracking-only'))
        self.assertEqual((result.source,result.camera_index,result.tracking_only),('camera',0,True))
        scan.assert_called_once();self.ui.choose.assert_not_called()

    def test_multiple_cameras_user_selection(self):
        other=AvailableCamera(2,160,160,'MSMF',30.)
        self.ui.choose.side_effect=None;self.ui.choose.return_value=2
        with patch.object(launcher,'scan_cameras',return_value=[self.camera,other]):
            result=self.controller.choose_camera(self.args('--camara'))
        self.assertEqual(result.index,2)

    def test_explicit_camera_index_not_rescanned(self):
        with patch.object(launcher,'probe_camera',return_value=self.camera) as probe,patch.object(launcher,'scan_cameras') as scan:
            self.controller.prepare(self.args('--camara','--camera-index','0','--tracking-only'))
        probe.assert_called_once();self.assertEqual(probe.call_args.args[:2],(0,'msmf'));scan.assert_not_called()

    def test_retry_and_manual_selection_after_camera_error(self):
        self.ui.choose.side_effect=['retry','manual']
        with patch.object(launcher,'scan_cameras',side_effect=[[],[]]),patch.object(launcher,'probe_camera',return_value=self.camera) as probe:
            self.assertEqual(self.controller.choose_camera(self.args('--camara')),self.camera)
        self.assertEqual(probe.call_args.args[0],2)

    def test_camera_failure_can_switch_to_video(self):
        args=self.args('--camara','--tracking-only');self.ui.choose.side_effect=None;self.ui.choose.return_value='video'
        with patch.object(launcher,'scan_cameras',return_value=[]):self.assertIsNone(self.controller.choose_camera(args))
        self.assertTrue(args.mp4);self.assertFalse(args.camara);self.assertFalse(args.tracking_only)

    def test_camera_profile_confirm_and_geometry(self):
        raw=self.root/'camera.json';raw.write_text(json.dumps(profile().to_dict()),encoding='utf-8')
        with patch.object(launcher,'probe_camera',return_value=self.camera):
            prepared=self.controller.prepare(self.args('--camara','--camera-index','0','--zones',str(raw)))
        self.assertTrue(prepared.confirm_camera_zones);self.assertFalse(prepared.tracking_only)
        self.ui.confirm.return_value=False
        with patch.object(launcher,'probe_camera',return_value=self.camera),self.assertRaises(Cancelled):
            self.controller.prepare(self.args('--camara','--camera-index','0','--zones',str(raw)))
        with patch.object(launcher,'probe_camera',return_value=AvailableCamera(0,320,240,'MSMF',30)),self.assertRaises(ValueError):
            self.controller.prepare(self.args('--camara','--camera-index','0','--zones',str(raw)))

    def test_no_args_menu_cancel_and_runtime_error_return_to_menu(self):
        with patch('src.launcher_ui.TkDialogs',return_value=self.ui):self.assertEqual(launcher.main([]),0)
        self.ui.close.assert_called_once()
        self.ui.run_view.return_value=True
        with patch('src.launcher_ui.TkDialogs',return_value=self.ui),patch.object(launcher.Launcher,'prepare',return_value=NS()):
            self.assertEqual(launcher.main(['--camara']),0)
        self.ui.menu.assert_called()

    def test_mp4_calibration_export_uses_real_schema(self):
        output=self.root/'new.zones.json'
        with patch.object(calibration,'edit_profile',return_value=profile()):
            calibration.calibrate_video(self.video,output,0,'TEST REVIEWER')
        self.assertEqual(calibration.load_profile(output,'video',self.video),profile())

    def test_camera_freeze_export_actual_index_and_provenance(self):
        output=self.root/'camera2.json'
        selected=calibration.ZoneProfile.create('camera_two',2,160,160,profile().a,profile().b)
        with patch.object(calibration,'freeze_camera',return_value=np.zeros((160,160,3),np.uint8)),patch.object(calibration,'edit_profile',return_value=selected):
            calibration.calibrate_camera(2,'msmf',output,'TEST')
        self.assertEqual(calibration.load_profile(output,'camera',confirmed=True).camera_index,2)
        side=json.loads(output.with_name('camera2.provenance.json').read_text(encoding='utf-8'))
        self.assertEqual(side['camera_index'],2);self.assertEqual(side['frame_storage'],'not_saved')
        self.assertIn('encuadre',side['warning'])

    def test_editor_adapter_uses_existing_editor_and_own_workspace(self):
        frame=np.zeros((160,160,3),np.uint8)
        with patch.object(calibration,'edit_frame',return_value=profile()) as editor:
            result=calibration.edit_profile(frame,seed=profile())
        self.assertEqual(result,profile());editor.assert_called_once()

    def test_output_prevents_overwrite_and_baseline_write(self):
        before=self.zones.read_bytes()
        for path in (self.zones,calibration.PROJECT_ROOT/'config/baselines/new.json'):
            with self.assertRaises(ValueError):calibration.new_output(path)
        self.assertEqual(before,self.zones.read_bytes())

    def test_calibration_controller_cancel_after_success_preserves_file(self):
        self.ui.confirm.return_value=False
        args=self.args('--calibrar','--mp4','--video',str(self.video),'--output',str(self.root/'fresh.json'),'--frame','0','--reviewer','TEST')
        with patch.object(calibration,'edit_profile',return_value=profile()),self.assertRaises(Cancelled):
            self.controller.prepare(args)
        self.assertTrue((self.root/'fresh.json').is_file())
        self.assertEqual(calibration.load_profile(self.root/'fresh.json','video',self.video),profile())

    def test_scan_bounded_invalid_devices_ignored(self):
        probe=MagicMock(side_effect=[RuntimeError('not available'),self.camera,RuntimeError('no frame')])
        found=probes.scan_cameras(3,'msmf',1.,probe=probe)
        self.assertEqual(found,[self.camera]);self.assertEqual(probe.call_count,3)

    def test_probe_worker_rejects_open_but_empty_and_releases(self):
        released=[]
        @contextmanager
        def camera(config):
            try:yield MagicMock(),None
            finally:released.append(True)
        output=MagicMock()
        with patch('src.presentation_sources.native_camera_session',camera):probes._probe_worker(0,'msmf',output)
        self.assertEqual(output.put.call_args.args[0][0],'error');self.assertEqual(released,[True])

    def test_probe_worker_valid_frame_is_closed_before_return(self):
        released=[]
        @contextmanager
        def camera(config):
            try:yield MagicMock(),np.zeros((160,160,3),np.uint8)
            finally:released.append(True)
        output=MagicMock(side_effect=None)
        def check(value):self.assertEqual(released,[True])
        output.put.side_effect=check
        with patch('src.presentation_sources.native_camera_session',camera),patch('src.camera.camera_info',return_value={'backend':'MSMF','fps':30}):
            probes._probe_worker(0,'msmf',output)
        self.assertEqual(output.put.call_args.args[0][0],'ok')

    def test_capture_space_returns_frozen_frame_without_saving(self):
        import cv2
        capture=MagicMock();frame=np.zeros((160,160,3),np.uint8);released=[]
        @contextmanager
        def camera(config):
            try:yield capture,frame
            finally:released.append(True)
        with patch.object(calibration,'native_camera_session',camera),patch.object(cv2,'namedWindow'),patch.object(cv2,'imshow'),patch.object(cv2,'waitKey',return_value=32),patch.object(cv2,'destroyWindow'),patch.object(cv2,'imwrite') as save:
            frozen=calibration.freeze_camera(0,'msmf')
        self.assertIsNot(frozen,frame);self.assertEqual(released,[True]);save.assert_not_called()

    def test_busy_completion_and_cancellation_join_threads(self):
        import threading
        from src.launcher_ui import TkDialogs
        from tkinter import ttk
        ui=TkDialogs()
        try:
            self.assertEqual(ui.busy(lambda cancel:42,'TEST'),42)
            def cancel_button():
                top=ui.root.winfo_children()[0]
                for widget in top.winfo_children():
                    if isinstance(widget,ttk.Button):widget.invoke();return
            ui.root.after(5,cancel_button)
            def work(cancel):
                cancel.wait(2)
                return 1
            with self.assertRaises(Cancelled):ui.busy(work,'Cancelacion simulada')
            self.assertFalse(any(t.name=='LimpIA-launcher-check' and t.is_alive() for t in threading.enumerate()))
        finally:ui.close()

    def test_actual_menu_exit_without_selecting_source(self):
        from src.launcher_ui import TkDialogs
        ui=TkDialogs()
        try:
            ui.root.after(10,lambda:ui.root.winfo_children()[0].destroy())
            with self.assertRaises(Cancelled):ui.menu()
        finally:ui.close()

    def test_probe_timeout_terminates_only_owned_worker(self):
        from queue import Empty
        context=MagicMock();process=context.Process.return_value
        process.pid=123;process.is_alive.return_value=True
        output=context.Queue.return_value;output.get.side_effect=Empty
        with patch.object(probes.mp,'get_context',return_value=context),patch.object(probes.time,'monotonic',side_effect=[0.,0.,0.,1.]):
            with self.assertRaises(RuntimeError):probes.probe_camera(0,'msmf',.1)
        process.terminate.assert_called_once();process.close.assert_called_once();output.close.assert_called_once()

    def test_camera_editor_uses_actual_index_and_geometry_engine(self):
        import cv2
        from src.zones import ZoneStore,ZoneProfile
        selected=ZoneProfile.create('camera_two',2,160,160,profile().a,profile().b)
        store=ZoneStore(self.root/'editing');store.save_and_activate(selected)
        with patch.object(cv2,'namedWindow'),patch.object(cv2,'setMouseCallback'),patch.object(cv2,'imshow'),patch.object(cv2,'waitKey',return_value=ord('q')),patch.object(cv2,'destroyWindow'):
            result=calibration.edit_camera_frame(cv2,np.zeros((160,160,3),np.uint8),store,2)
        self.assertEqual(result,selected)

    def test_camera_full_calibration_adapter_preserves_index(self):
        import cv2
        from src.zones import ZoneProfile
        selected=ZoneProfile.create('camera_two',2,160,160,profile().a,profile().b)
        output=self.root/'actual-adapter.json'
        with patch.object(calibration,'freeze_camera',return_value=np.zeros((160,160,3),np.uint8)),patch.object(cv2,'namedWindow'),patch.object(cv2,'setMouseCallback'),patch.object(cv2,'imshow'),patch.object(cv2,'waitKey',return_value=ord('q')),patch.object(cv2,'destroyWindow'):
            calibration.calibrate_camera(2,'msmf',output,'AUTOMATED',seed=selected)
        self.assertEqual(calibration.load_profile(output,'camera',confirmed=True),selected)

    def test_packaging_whitelist_excludes_private_assets(self):
        import ast
        spec=calibration.PROJECT_ROOT/'packaging/LimpIA.spec'
        ast.parse(spec.read_text(encoding='utf-8-sig'))
        text=spec.read_text(encoding='utf-8-sig')
        self.assertNotIn('videos_testing',text);self.assertNotIn('device.local.json',text)
        self.assertNotIn('sala_v4.json',text);self.assertIn('exclude_binaries=True',text)

    def test_main_dispatches_valid_options_to_existing_window_host(self):
        args=['--mp4','--video',str(self.video),'--zones',str(self.zones),'--tracker','bytetrack','--device','cpu','--weights-dir',str(self.weights)]
        with patch('src.launcher_ui.TkDialogs',return_value=self.ui):self.assertEqual(launcher.main(args),0)
        prepared=self.ui.run_view.call_args.args[0]
        self.assertEqual(prepared.video,self.video);self.assertEqual(prepared.tracker,'bytetrack')
        self.assertEqual(prepared.zones,self.zones);self.ui.menu.assert_not_called()

    def test_window_host_starts_session_and_releases_on_close(self):
        from src.launcher_ui import TkDialogs
        ui=TkDialogs();instance=MagicMock()
        instance.session.thread=None;instance.session.snapshot.return_value=NS(error='')
        def window(top,options):top.after(100,top.destroy);return instance
        try:
            with patch('src.view_presentation.PresentationWindow',side_effect=window):self.assertFalse(ui.run_view(NS()))
            instance.start.assert_called_once();instance.session.stop.assert_called_once()
        finally:ui.close()

    def test_interactive_profile_always_gets_review_with_configured_options(self):
        self.ui.open_video.side_effect=None;self.ui.open_video.return_value=self.video
        self.ui.open_json.side_effect=None;self.ui.open_json.return_value=self.zones
        self.ui.choose.side_effect=None;self.ui.choose.return_value='existing'
        self.controller.prepare(self.args('--mp4','--tracker','bytetrack'))
        self.ui.settings.assert_called_once()

    def test_calibration_can_select_existing_profile_as_editable_seed(self):
        args=self.video_args();args.output=None
        self.ui.choose.side_effect=None;self.ui.choose.return_value='edit'
        self.ui.open_json.side_effect=None;self.ui.open_json.return_value=self.zones
        self.ui.save_json.side_effect=None;self.ui.save_json.return_value=self.root/'edited.json'
        with patch.object(launcher,'calibrate_video',return_value=self.root/'edited.json') as calibrate:
            self.controller.calibrate(args,self.video,None,offer_seed=True)
        self.assertEqual(calibrate.call_args.args[-1],profile())
        self.assertEqual(calibrate.call_args.args[1],self.root/'edited.json')

    def test_video_changed_during_edit_is_not_exported(self):
        output=self.root/'changed-source.json'
        def edit(*args,**kwargs):
            self.video.write_bytes(b'changed synthetic fixture, not user video')
            return profile()
        with patch.object(calibration,'edit_profile',side_effect=edit),self.assertRaises(RuntimeError):
            calibration.calibrate_video(self.video,output,0,'TEST')
        self.assertFalse(output.exists())

    def test_resource_catalog_weights_preferences_and_dedup(self):
        from src import launcher_resources as r
        import shutil
        folder=self.root/'videos_testing';folder.mkdir();target=folder/'clip.mp4';shutil.copyfile(self.video,target)
        r.save_preferences(weights_dir=str(self.weights),video=str(target),zones=str(self.zones),profile_dirs=[str(self.root)])
        self.assertEqual(r.default_weights(),self.weights)
        self.assertEqual(r.videos(),[target])
        self.assertEqual(r.load_preferences()['weights_dir'],str(self.weights))
        self.assertFalse(r.valid_weights(self.root/'missing'))
        self.assertEqual(r.profiles('video',self.video)[0][0],self.zones)
        self.assertTrue(r.profiles('video',target))
        target.write_bytes(b'changed incompatible fixture')
        with self.assertRaises((ValueError,RuntimeError)):r.profiles('video',target)

    def test_empty_catalog_and_explicit_cli_weights(self):
        from src import launcher_resources as r
        self.assertEqual(r.videos(),[])
        r.save_preferences(weights_dir=str(self.root/'missing'))
        self.assertEqual(self.controller.prepare(self.video_args()).weights_dir,self.weights)

    def test_automatic_cuda_and_explicit_cpu(self):
        args=self.video_args();args.device=None
        with patch('src.devices.load_device_preference',return_value=None),patch('src.devices.load_torch'),patch('src.devices.discover_devices',return_value=NS(devices=[NS(device='cpu'),NS(device='cuda:0')])),patch('src.devices.validate_device'):
            self.ui.settings.side_effect=lambda a,p:('bytetrack',a.device,a.weights_dir)
            self.assertEqual(self.controller.prepare(args).device,'cuda:0')
            self.assertEqual(self.controller.prepare(self.video_args()).device,'cpu')

    def test_interactive_invalid_profile_can_be_corrected_without_restarting(self):
        bad=self.root/'invalid-profile.json';bad.write_text('{}',encoding='utf-8')
        self.ui.choose.side_effect=None;self.ui.choose.return_value='existing'
        self.ui.open_json.side_effect=[bad,self.zones]
        args=self.args('--mp4','--video',str(self.video))
        self.assertEqual(self.controller.prepare(args).zones,self.zones)
        self.ui.error.assert_called_once()
