"""Presentation contracts: simulated sources plus real MP4 decode and Tk layout."""
from contextlib import contextmanager
from dataclasses import replace
import json
import gc
from pathlib import Path
import threading
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch, MagicMock

import numpy as np

from src.presentation_sources import CameraFrames, load_profile, open_source, validate_frame
from src.presentation_processing import CountAdapter, ProcessedFrame, open_processor
from src.presentation_session import PresentationState, Session
from src.video_source import FramePacket
from src.view_presentation import parser, resolve_choices, fit_size, PresentationWindow
from h52_test_support import profile, fixture
from video_test_support import temporary_directory


def options(**changes):
    values = vars(parser().parse_args(['--device', 'cpu']))
    values.update(changes)
    return NS(**values)


def packet(index=0, x=20):
    frame = np.zeros((160,160,3), np.uint8)
    return FramePacket(index, index*200., 'synthetic', frame, 0.)


def result(x):
    return NS(tracks=(NS(track_id=1,x1=x,y1=30,x2=x+40,y2=80),), untracked_detections=())


class PresentationTestCase(unittest.TestCase):
    # Repeated Tk roots must be reclaimed on the UI thread before any next worker.
    def setUp(self):
        gc.collect()

    def tearDown(self):
        gc.collect()


class SourcesTests(PresentationTestCase):
    def setUp(self):
        super().setUp()
        self.temp = temporary_directory()
        self.addCleanup(self.temp.cleanup)
        self.video, self.case, self.zones = fixture(Path(self.temp.name), real_video=True)

    def test_real_mp4_initialization_and_timestamps(self):
        with open_source(options(video=self.video), profile()) as source:
            packets = list(source)
            self.assertEqual(len(packets), 4)
            self.assertEqual(source.status, 'completed')
            self.assertEqual(source.metadata['reported_fps'], 5)
            self.assertTrue(all(a.timestamp_ms < b.timestamp_ms for a,b in zip(packets, packets[1:])))
            capture = source.capture
        self.assertFalse(capture.isOpened())

    def test_missing_or_corrupt_mp4(self):
        for path in (Path(self.temp.name)/'absent.mp4', Path(self.temp.name)/'corrupt.mp4'):
            if path.name == 'corrupt.mp4':
                path.write_bytes(b'corrupt synthetic fixture')
            with self.subTest(path=path), self.assertRaises((ValueError, RuntimeError)):
                with open_source(options(video=path), profile()):
                    pass

    def test_zone_hash_and_camera_confirmation(self):
        self.assertEqual(load_profile(self.zones,'video',self.video),profile())
        with self.assertRaises(ValueError):
            load_profile(self.zones,'camera')
        self.assertEqual(load_profile(self.zones,'camera',confirmed=True),profile())
        wrong = Path(self.temp.name)/'wrong.mp4'
        wrong.write_bytes(b'other video')
        with self.assertRaises(ValueError):
            load_profile(self.zones,'video',wrong)
        data=json.loads(self.zones.read_text(encoding='utf-8'))
        data['profile_sha256']='bad'
        self.zones.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ValueError):
            load_profile(self.zones,'camera',confirmed=True)

    def test_coordinates_and_exact_resolution(self):
        validate_frame(packet().frame, profile())
        for frame in (np.zeros((80,80,3)),np.zeros((160,160)),None):
            with self.subTest(frame=type(frame)), self.assertRaises(ValueError):
                validate_frame(frame,profile())

    def test_camera_first_frame_once_monotonic_and_disconnect(self):
        frame=packet().frame
        capture=MagicMock()
        capture.read.side_effect=[(True,frame.copy()),(False,None)]
        source=CameraFrames(capture,frame,clock=lambda:10.)
        iterator=iter(source)
        first,second=next(iterator),next(iterator)
        self.assertIs(first.frame,frame)
        self.assertGreater(second.timestamp_ms,first.timestamp_ms)
        self.assertEqual([first.index,second.index],[0,1])
        with self.assertRaises(RuntimeError):
            next(iterator)

    def test_camera_context_releases_on_error_and_uses_backend(self):
        capture=MagicMock()
        @contextmanager
        def camera(config):
            self.assertEqual(config['backend'],'msmf')
            self.assertEqual(config['width'],160)
            try:
                yield capture,packet().frame
            finally:
                capture.release()
        with patch('src.presentation_sources.native_camera_session',camera):
            with self.assertRaisesRegex(RuntimeError,'consumer'):
                with open_source(options(source='camera',camera_index=0,camera_backend='msmf'),profile()) as source:
                    self.assertIsNotNone(next(iter(source)).frame)
                    raise RuntimeError('consumer')
        capture.release.assert_called_once()

    def test_unavailable_camera(self):
        with patch('src.presentation_sources.native_camera_session',side_effect=RuntimeError('indisponible')):
            with self.assertRaisesRegex(RuntimeError,'indisponible'):
                with open_source(options(source='camera',camera_index=0),profile()):
                    pass


class ProcessingTests(PresentationTestCase):
    def test_confirmed_events_and_no_repeat_in_same_zone(self):
        engine=CountAdapter(profile(),lambda p:result(20 if p.index<2 or p.index>=6 else 100))
        states=[engine.update(packet(i)) for i in range(8)]
        self.assertEqual([(s.entries,s.exits) for s in states],[(0,0),(0,0),(0,0),(1,0),(1,0),(1,0),(1,0),(1,1)])
        self.assertEqual(states[-1].last_event.direction,'OUT')
        self.assertEqual(states[3].last_event,states[5].last_event)
        with self.assertRaises(ValueError):
            engine.update(packet(7))

    def test_fresh_counter_per_session(self):
        first=CountAdapter(profile(),lambda p:result(20 if p.index<2 else 100))
        for i in range(4):
            first.update(packet(i))
        second=CountAdapter(profile(),lambda p:result(100))
        self.assertEqual(second.update(packet()).entries,0)
        self.assertIsNone(second.last_event)
        self.assertIsNot(first.counter,second.counter)

    def test_tracker_adapter_both_variants_and_device_no_fallback(self):
        for tracker_name in ('bytetrack','botsort'):
            with self.subTest(tracker=tracker_name):
                prepared=NS(weights=(),detection={},tracking={},experimental_botsort=tracker_name=='botsort')
                tracker=NS(device_resolution=NS(effective_device='cpu',fallback=False),track=MagicMock(return_value=result(20)))
                with patch('src.video_runner.prepare_runtime',return_value=prepared) as prepare, patch('src.tracker.PersonTracker',return_value=tracker) as ctor:
                    with open_processor(options(tracker=tracker_name),profile()) as processor:
                        processor.update(packet())
                    tracker.track.assert_called_once()
                    self.assertEqual(prepare.call_args.args[0].tracker,tracker_name)
                    self.assertEqual(ctor.call_args.kwargs['experimental_botsort'],tracker_name=='botsort')
                    tracker.device_resolution.fallback=True
                    with self.assertRaises(RuntimeError):
                        with open_processor(options(tracker=tracker_name),profile()):
                            pass

    def test_existing_device_selector_does_not_persist(self):
        with patch('src.devices.load_torch'), patch('src.devices.discover_devices',return_value=NS(devices=())), patch('src.device_selector.choose_device',return_value='cuda:0') as choose, patch('src.device_selector.save_device') as save:
            self.assertEqual(resolve_choices(options(device=None)).device,'cuda:0')
            choose.assert_called_once()
            save.assert_not_called()

    def test_existing_camera_selector_does_not_persist(self):
        with patch('src.camera_selector.scan_cameras',return_value=[]), patch('src.camera_selector.choose_camera',return_value=2), patch('src.camera_selector.save_camera_index') as save:
            self.assertEqual(resolve_choices(options(source='camera')).camera_index,2)
            save.assert_not_called()

    def test_cli_invalid_combinations(self):
        for o in (options(source='camera',predictions=Path('x')),options(camera_index=-1),options(source='camera',video=Path('x'))):
            with self.assertRaises(ValueError):
                resolve_choices(o)


class SessionTests(PresentationTestCase):
    def make_session(self, fail=False, delay=.005):
        released=[]
        @contextmanager
        def source(o,p):
            class Frames:
                status='completed'
                def __iter__(self):
                    for i in range(200):
                        yield packet(i)
            try:
                yield Frames()
            finally:
                released.append('source')
        @contextmanager
        def processor(o,p):
            class Processor:
                def update(self, packet):
                    time.sleep(delay)
                    if fail:
                        raise RuntimeError('fallo simulado')
                    return ProcessedFrame((),(),packet.index,0,None)
            try:
                yield Processor()
            finally:
                released.append('processor')
        session=Session(options(realtime=False),source_factory=source,processor_factory=processor,profile_loader=lambda *a:profile())
        self.addCleanup(lambda: (session.stop(), session.thread.join(3) if session.thread else None))
        return session,released

    def await_state(self,session,predicate):
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            state=session.snapshot()
            if predicate(state): return state
            time.sleep(.005)
        self.fail(f'State deadline exceeded: {session.snapshot()}')

    def test_pause_resume_stop_and_resources(self):
        s,released=self.make_session()
        s.start()
        self.assertFalse(s.start())
        self.await_state(s,lambda state:state.frames_processed>=2)
        s.toggle_pause()
        paused=self.await_state(s,lambda state:state.status=='Pausado')
        time.sleep(.04)
        self.assertEqual(s.snapshot().frames_processed,paused.frames_processed)
        s.toggle_pause()
        self.await_state(s,lambda state:state.frames_processed>paused.frames_processed)
        s.stop();s.thread.join(3)
        self.assertFalse(s.running)
        self.assertEqual(released,['source','processor'])
        self.assertEqual(s.snapshot().status,'Detenido')
        s.start()
        self.assertEqual(s.snapshot().entries,0)
        self.assertIsNone(s.snapshot().last_event)

    def test_error_is_published_after_resources_release(self):
        s,released=self.make_session(fail=True)
        with self.assertLogs('src.presentation_session',level='ERROR'):
            s.start();s.thread.join(3)
        self.assertFalse(s.running)
        self.assertIn('fallo simulado',s.snapshot().error)
        self.assertEqual(released,['source','processor'])

    def test_latest_state_mailbox_bounded_and_all_frames_processed(self):
        s,released=self.make_session(delay=0)
        s.start();s.thread.join(3)
        self.assertEqual(s.snapshot().frames_processed,200)
        self.assertEqual(s.snapshot().index,199)
        self.assertEqual(s.snapshot().status,'Finalizado')
        self.assertIsInstance(s.state,PresentationState)

    def test_stop_wakes_paused_worker(self):
        s,_=self.make_session()
        s.start();s.toggle_pause()
        self.await_state(s,lambda state:state.status=='Pausado')
        s.stop();s.thread.join(3)
        self.assertFalse(s.running)


class LayoutTests(PresentationTestCase):
    def test_letterbox_preserves_aspect(self):
        self.assertEqual(fit_size(1920,1080,800,600),(800,450))
        self.assertEqual(fit_size(1080,1920,800,600),(338,600))

    def test_real_tk_layout_stable_counters_status_and_render(self):
        import tkinter as tk
        root=tk.Tk()
        def cleanup():
            try:
                root.destroy()
            except tk.TclError:
                pass
        self.addCleanup(cleanup)
        window=PresentationWindow(root,options())
        window.session.profile=profile()
        root.update()
        before=(window.canvas.winfo_width(),window.canvas.winfo_height())
        for count in (9,10,99,100):
            window.session.publish(entries=count,exits=count,status='Finalizado' if count==100 else 'Reproduciendo video',frame=packet().frame)
            window.tick();root.update()
            self.assertEqual((window.canvas.winfo_width(),window.canvas.winfo_height()),before)
        self.assertGreater(window.render_count,0)
        self.assertEqual(window.photo.width(),min(before))
        window.close();window.tick()

class UnifiedIntegrationTests(PresentationTestCase):
    def test_replay_real_decode_and_confirmed_counts_without_yolo(self):
        with temporary_directory() as temp:
            video,case,zones=fixture(Path(temp),real_video=True)
            metadata=case/'metadata.json'
            data=json.loads(metadata.read_text(encoding='utf-8'))
            data['configuration']['tracker_name']='bytetrack'
            metadata.write_text(json.dumps(data),encoding='utf-8')
            o=options(video=video,zones=zones,predictions=case,realtime=False)
            with patch('src.tracker.PersonTracker',side_effect=AssertionError('Replay must not load YOLO')):
                session=Session(o)
                session.start();session.thread.join(5)
            self.assertFalse(session.running)
            state=session.snapshot()
            self.assertEqual(state.status,'Finalizado',state.error)
            self.assertEqual((state.entries,state.exits,state.frames_processed),(1,0,4))

    def test_simulated_camera_through_real_adapter_and_counter(self):
        with temporary_directory() as temp:
            _,_,zones=fixture(Path(temp),real_video=True)
            prepared=NS(weights=(),detection={},tracking={},experimental_botsort=False)
            tracker=NS(device_resolution=NS(effective_device='cpu',fallback=False),
                       track=MagicMock(side_effect=[result(20),result(20),result(100),result(100)]))
            capture=MagicMock()
            capture.read.side_effect=[(True,packet().frame)]*3+[(False,None)]
            @contextmanager
            def camera(config):
                try:
                    yield capture,packet().frame
                finally:
                    capture.release()
            ticks=iter([0.,0.,.1,.2,.3,.4,.5,.6,.7,.8])
            # Synthetic monotonic timestamps stand in for capture arrivals only.
            @contextmanager
            def source(o,p):
                with camera({}) as (cap,first):
                    yield CameraFrames(cap,first,clock=lambda:next(ticks))
            o=options(source='camera',camera_index=0,zones=zones,confirm_camera_zones=True)
            with patch('src.video_runner.prepare_runtime',return_value=prepared),patch('src.tracker.PersonTracker',return_value=tracker):
                session=Session(o,source_factory=source)
                with self.assertLogs('src.presentation_session',level='ERROR'):
                    session.start();session.thread.join(5)
            state=session.snapshot()
            self.assertEqual((state.entries,state.exits,state.frames_processed),(1,0,4))
            self.assertEqual(tracker.track.call_count,4)
            self.assertIn('cámara dejó',state.error)
            capture.release.assert_called_once()

    def test_initialization_error_keeps_window_responsive(self):
        import tkinter as tk
        root=tk.Tk()
        window=PresentationWindow(root,options(zones=Path('missing-profile.json')))
        try:
            with self.assertLogs('src.presentation_session',level='ERROR'):
                window.session.start();window.session.thread.join(3)
            window.tick();root.update()
            self.assertIn('Error',window.values['status'].cget('text'))
            self.assertEqual(str(window.start_button.cget('state')),'normal')
            self.assertTrue(root.winfo_exists())
        finally:
            root.destroy()

    def test_replay_rejects_different_tracker(self):
        with temporary_directory() as temp:
            video,case,zones=fixture(Path(temp),real_video=True)
            with self.assertRaises(ValueError):
                with open_processor(options(video=video,zones=zones,predictions=case,tracker='botsort'),profile()):
                    pass


class PerformanceRegressionTests(PresentationTestCase):
    def test_absolute_mp4_clock_resists_repeated_wakeup_overshoot(self):
        @contextmanager
        def source(o,p):
            class Frames:
                status='completed'
                def __iter__(self):
                    for i in range(40):
                        yield replace(packet(i),timestamp_ms=i*1000/30)
            yield Frames()
        times=[]
        @contextmanager
        def processor(o,p):
            class Processor:
                def update(self,packet):
                    if not times: time.sleep(.12)  # Model warmup must not accelerate playback.
                    times.append(time.monotonic())
                    time.sleep(.004)
                    return ProcessedFrame((),(),0,0,None)
            yield Processor()
        session=Session(options(),source_factory=source,processor_factory=processor,profile_loader=lambda *a:profile())
        original=session._gate
        def overshoot(delay=0):
            result=original(delay)
            if delay>0:time.sleep(.008)
            return result
        session._gate=overshoot
        session.start();session.thread.join(5)
        self.assertFalse(session.running)
        self.assertEqual(session.snapshot().frames_processed,40)
        elapsed=times[-1]-times[0]
        self.assertGreater(elapsed,1.2)
        self.assertLess(elapsed,1.5)  # Relative waits accumulate 39*8ms drift.

    def test_camera_fifo_is_bounded_and_overload_explicit(self):
        capture=MagicMock();capture.read.return_value=(True,packet().frame)
        source=CameraFrames(capture,packet().frame)
        iterator=iter(source)
        self.assertEqual(next(iterator).index,0)
        self.assertEqual(next(iterator).index,1)
        source.thread.join(2)
        indices=[1]
        with self.assertRaisesRegex(RuntimeError,'cola de 8'):
            while True:indices.append(next(iterator).index)
        self.assertEqual(indices,list(range(1,len(indices)+1)))
        self.assertLessEqual(source.pending.qsize(),8)
        self.assertFalse(source.thread.is_alive())

    def test_tracking_only_never_constructs_counter(self):
        from src.presentation_processing import TrackingAdapter
        processor=TrackingAdapter(lambda frame:result(20))
        processed=processor.update(packet())
        self.assertIsNone(processed.entries)
        self.assertIsNone(processed.exits)
        self.assertEqual(len(processed.tracks),1)
        with self.assertRaises(ValueError):resolve_choices(options(tracking_only=True))

    def test_floating_card_does_not_reserve_video_column_and_photo_reused(self):
        import tkinter as tk
        root=tk.Tk();window=PresentationWindow(root,options())
        try:
            root.update();window.session.profile=profile()
            window.session.publish(frame=packet().frame)
            window.tick();root.update()
            photo=window.photo
            for count in (9,10,99,100):
                window.session.publish(frame=packet().frame,entries=count)
                window.tick();root.update()
                self.assertIs(window.photo,photo)
            self.assertEqual(window.card.master,window.canvas)
            self.assertEqual(window.card.winfo_manager(),'place')
            self.assertGreater(window.canvas.winfo_width(),root.winfo_width()-40)
        finally:root.destroy()

class NativeInputRevisionTests(PresentationTestCase):
    def test_native_camera_never_sets_capture_fps(self):
        import cv2
        from src.presentation_sources import native_camera_session
        cap=MagicMock();cap.open.return_value=True;cap.isOpened.return_value=True
        cap.read.return_value=(True,packet().frame)
        config=dict(camera_index=0,width=160,height=160,backend='msmf',fps=17)
        with patch('src.presentation_sources.backend_candidates',return_value=[('msmf',cv2.CAP_MSMF)]),patch('cv2.VideoCapture',return_value=cap):
            with native_camera_session(config):pass
        self.assertNotIn(cv2.CAP_PROP_FPS,[call.args[0] for call in cap.set.call_args_list])
        cap.release.assert_called_once()

    def test_no_public_speed_controls(self):
        with patch('sys.stderr'):
            for args in (['--unpaced'],['--camera-fps','30']):
                with self.assertRaises(SystemExit):parser().parse_args(args)
        self.assertTrue(parser().parse_args([]).realtime)

    def test_card_metadata_and_notice_fit_inside_card(self):
        import tkinter as tk
        root=tk.Tk();window=PresentationWindow(root,options(source='camera',tracking_only=True))
        try:
            window.session.publish(error='Aviso de prueba de camara sin calibrar')
            window.tick();root.update()
            self.assertLess(window.card.winfo_height(),470)
            self.assertLess(window.card.winfo_height()-(window.values['error'].winfo_y()+window.values['error'].winfo_height()),25)
            for key in ('details','error'):
                widget=window.values[key]
                self.assertLess(widget.winfo_y()+widget.winfo_height(),window.card.winfo_height())
                self.assertLessEqual(widget.winfo_reqheight(),widget.winfo_height())
        finally:root.destroy()

    def test_tracking_only_latest_frame_preserves_source_indices(self):
        capture=MagicMock();capture.read.side_effect=[(True,packet().frame)]*99+[(False,None)]
        source=CameraFrames(capture,packet().frame,latest_only=True)
        iterator=iter(source);received=[next(iterator)]
        try:
            while True:received.append(next(iterator))
        except RuntimeError as exc:self.assertIn('entregar',str(exc))
        self.assertEqual(received[-1].index,99)
        self.assertTrue(all(a.index<b.index and a.timestamp_ms<b.timestamp_ms for a,b in zip(received,received[1:])))
        self.assertEqual(len(received)+source.frames_skipped,100)
        self.assertFalse(source.thread.is_alive())

    def test_mp4_does_not_fast_forward_after_inference_stall(self):
        @contextmanager
        def source(o,p):
            class Frames:
                status='completed'
                def __iter__(self):
                    for i in range(8):yield replace(packet(i),timestamp_ms=i*50.)
            yield Frames()
        @contextmanager
        def processor(o,p):
            class Processor:
                def update(self,p):
                    if p.index==3:time.sleep(.2)
                    return ProcessedFrame((),(),0,0,None)
            yield Processor()
        session=Session(options(),source_factory=source,processor_factory=processor,profile_loader=lambda *a:profile())
        published=[];original=session.publish
        def publish(**kw):
            if 'frame' in kw:published.append((kw['index'],time.monotonic()))
            original(**kw)
        session.publish=publish
        session.start();session.thread.join(3)
        self.assertEqual(session.snapshot().frames_processed,8)
        for (_,a),(_,b) in zip(published[3:],published[4:]):self.assertGreater(b-a,.035)

class OrderedPlaybackTests(PresentationTestCase):
    def test_fifo_clock_does_not_compress_frames_after_late_presentation(self):
        from src.presentation_playback import DisplayQueue
        now=[0.]
        queue=DisplayQueue(clock=lambda:now[0])
        for i in range(4):queue.put(PresentationState(index=i,timestamp=i*.1))
        self.assertEqual(queue.take().index,0);queue.acknowledge()
        self.assertIsNone(queue.take())
        now[0]=.1;self.assertEqual(queue.take().index,1);queue.acknowledge()
        now[0]=.5;self.assertEqual(queue.take().index,2);queue.acknowledge()
        self.assertIsNone(queue.take())
        now[0]=.61;self.assertEqual(queue.take().index,3);queue.acknowledge()

    def test_prefill_short_clip_and_stop_unblock_worker(self):
        from src.presentation_playback import DisplayQueue
        queue=DisplayQueue(capacity=2,prefill=2)
        queue.put(PresentationState(index=0))
        self.assertIsNone(queue.take())
        queue.finish();self.assertEqual(queue.take().index,0);queue.acknowledge()
        queue.put(PresentationState(index=1));queue.put(PresentationState(index=2))
        done=threading.Event()
        worker=threading.Thread(target=lambda:(queue.put(PresentationState(index=3)),done.set()))
        worker.start();self.assertFalse(done.wait(.02))
        queue.cancel();worker.join(1)
        self.assertTrue(done.is_set());self.assertIsNone(queue.take())

    def test_actual_tk_displays_all_frames_and_frame_aligned_metrics(self):
        import tkinter as tk
        @contextmanager
        def source(o,p):
            class Frames:
                metadata={'reported_fps':30,'reported_frames':40}
                status='completed'
                def __iter__(self):
                    for i in range(40):yield replace(packet(i),timestamp_ms=i*1000/30)
            yield Frames()
        @contextmanager
        def processor(o,p):
            class Processor:
                def update(self,p):
                    time.sleep(.004 if p.index%3 else .018)
                    return ProcessedFrame((),(),p.index,0,None)
            yield Processor()
        root=tk.Tk();window=PresentationWindow(root,options(video=Path('simulated.mp4')))
        window.session=Session(window.options,source_factory=source,processor_factory=processor,profile_loader=lambda *a:profile(),display_buffer=True)
        drawn=[];original=window.draw
        def draw(state,*args):
            drawn.append((state.index,state.entries))
            original(state,*args)
        window.draw=draw
        def monitor():
            if window.session.thread and not window.session.running:window.close();return
            root.after(5,monitor)
        root.after(5,window.start);root.after(10,monitor)
        root.after(5000,window.close)
        try:
            root.mainloop()
            self.assertEqual(drawn,[(i,i) for i in range(40)])
            self.assertEqual(window.session.snapshot().status,'Finalizado')
        finally:
            window.draw=original
            window.session.stop()
            if window.session.thread:window.session.thread.join(2)
            try:root.destroy()
            except tk.TclError:pass

class LiveCadenceTests(PresentationTestCase):
    def test_live_clock_uses_device_period_not_processing_jitter(self):
        from src.presentation_playback import DisplayQueue
        now=[0.];queue=DisplayQueue(clock=lambda:now[0],nominal=True)
        for i,timestamp in enumerate((0.,.024,.073,.10)):
            queue.put(PresentationState(index=i,timestamp=timestamp,source_fps=30))
        self.assertEqual(queue.take().index,0);queue.acknowledge()
        now[0]=.025;self.assertIsNone(queue.take())
        now[0]=.034;self.assertEqual(queue.take().index,1);queue.acknowledge()
        now[0]=.067;self.assertEqual(queue.take().index,2);queue.acknowledge()
        now[0]=1.;self.assertEqual(queue.take().index,3);queue.acknowledge()
        queue.put(PresentationState(index=4,timestamp=.133,source_fps=30))
        now[0]=1.001;self.assertIsNone(queue.take())
        now[0]=1.034;self.assertEqual(queue.take().index,4);queue.acknowledge()

    def test_camera_warmup_frame_is_processed_without_flashing_stale_image(self):
        session=Session(options(source='camera'),display_buffer=True)
        session.publish(frame=packet().frame,index=0,entries=5,frame_age_ms=1000.)
        self.assertEqual(session.snapshot().entries,5)
        self.assertIsNone(session.display_queue.take())
        session.publish(frame=packet().frame,index=1,timestamp=1.,frame_age_ms=10.,source_fps=30)
        self.assertEqual(session.display_queue.take().index,1)
        session.display_queue.acknowledge();session.stop()
