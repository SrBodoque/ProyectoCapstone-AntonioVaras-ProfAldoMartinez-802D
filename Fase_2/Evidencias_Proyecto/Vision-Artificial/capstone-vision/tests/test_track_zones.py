"""Integración de zonas con contratos existentes; captura/IA/GUI simuladas."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

from src import track_zones as app, track_botsort_reid
from src.config import PROJECT_ROOT, load_config, load_detection_config, load_tracking_config
from src.detector import Detection
from src.tracker import FrameTracks, Track
from src.zones import ZoneStore, ZoneObservations
from video_test_support import temporary_directory
from zone_test_support import profile, make_ui, camera_module


class TrackingZonesTests(unittest.TestCase):
    def setUp(self):
        self.ui, self.capture, self.frame = make_ui()
        self.profile = profile()
        self.tracking = {**load_tracking_config(), "tracker_config": track_botsort_reid.BOTSORT_CONFIG}
        self.engine = MagicMock(config={**load_detection_config(), "device":"cpu"}, bytetrack_config={"track_buffer":30})
        self.engine.track.return_value = FrameTracks((Track(400, 100, 500, 350, .9, 0, 7),), (), 10., 13.)
        self.factory = MagicMock(return_value=self.engine)

    def run_loop(self):
        with camera_module(self.ui), patch.object(app, "PersonTracker", self.factory):
            app.run_zones(self.ui, load_config(), load_detection_config(), self.tracking, self.profile)

    def test_loads_one_tracker_same_yaml_config_and_single_inference_per_frame(self):
        self.ui.waitKey.side_effect = [-1,-1,ord("q")]
        self.run_loop()
        self.factory.assert_called_once_with(load_detection_config(), self.tracking)
        self.assertEqual(self.engine.track.call_count, 3)
        self.assertEqual(self.tracking["tracker_config"], track_botsort_reid.BOTSORT_CONFIG)
        self.assertEqual(self.capture.open.call_args.args[0], load_config()["camera_index"])
        self.capture.release.assert_called_once(); self.ui.destroyAllWindows.assert_called_once()

    def test_overlay_happens_after_tracking_of_raw_frame(self):
        sequence = []
        def infer(frame):
            self.assertTrue((frame == 70).all()); sequence.append("infer")
            return FrameTracks((), (), 1., 2.)
        def paint(cv2, frame, polygons): frame[:] = 0; sequence.append("paint")
        self.engine.track.side_effect = infer
        with patch.object(app, "draw_regions", side_effect=paint): self.run_loop()
        self.assertEqual(sequence, ["infer","paint"])

    def test_cpu_and_cuda_effective_display_come_from_existing_engine(self):
        for device in ("cpu","cuda:0","cuda:1"):
            self.engine.config["device"] = device
            self.run_loop()
            labels = [c.args[1] for c in self.ui.putText.call_args_list]
            self.assertTrue(any(device in text for text in labels))
            self.assertEqual(self.factory.call_args.kwargs, {})

    def test_bottom_center_zone_and_untracked_boxes_without_identity(self):
        result = FrameTracks((Track(300, 10, 500, 300, .9, 0, 9),),
                             (Detection(60,20,100,300,.8,0),), 1, 2)
        app.draw_positions(self.ui, self.frame, result, self.profile, ZoneObservations())
        points = [c.args[1] for c in self.ui.circle.call_args_list]
        self.assertEqual(points, [(400,300),(80,300)])
        labels = [c.args[1] for c in self.ui.putText.call_args_list]
        self.assertTrue(any("ID 9 | ZONA A" in s for s in labels))
        self.assertTrue(any("Sin ID | ZONA B" in s for s in labels))

    def test_outside_and_transitions_only_for_continuous_same_id(self):
        observations = ZoneObservations(stable_frames=1)
        for x, identifier in ((80,1),(400,1),(320,1),(80,2)):
            result = FrameTracks((Track(x-10,20,x+10,300,.9,0,identifier),),(),1,2)
            app.draw_positions(self.ui, self.frame, result, self.profile, observations)
        labels = [c.args[1] for c in self.ui.putText.call_args_list]
        self.assertTrue(any("obs: B -> A" in s for s in labels))
        self.assertTrue(any("FUERA" in s for s in labels))
        self.assertFalse(any("obs:" in s and "ID 2" in s for s in labels))

    def test_metrics_original_box_colors_and_trails(self):
        self.ui.waitKey.side_effect = [-1,ord("q")]
        self.run_loop()
        labels = [c.args[1] for c in self.ui.putText.call_args_list]
        for required in ("FPS pipeline:", "Inferencia YOLO:", "YOLO + tracking:", "Tracks activos:", "Cajas sin ID:", "sin conteo"):
            self.assertTrue(any(required in s for s in labels))
        self.assertEqual(self.ui.rectangle.call_args.args[-2:], ((0,220,0),2))
        self.assertGreater(self.ui.line.call_count, 0)
        self.ui.fillPoly.assert_called()
        self.assertEqual(self.ui.addWeighted.call_args.args[1::2][:2], (.2,.8))

    def test_incompatible_camera_or_aspect_blocks_before_model(self):
        for p in (profile(camera=5), profile(width=1280,height=720)):
            self.profile = p
            with self.assertRaisesRegex(ValueError, "Recalibre"): self.run_loop()
        self.factory.assert_not_called()
        self.assertEqual(self.capture.release.call_count, 2)

    def test_resolution_change_during_loop_is_checked_before_inference(self):
        self.capture.read.side_effect = [(True,self.frame),(True,self.frame[:200])]
        self.ui.waitKey.return_value = -1
        with self.assertRaisesRegex(ValueError,"aspecto"): self.run_loop()
        self.assertEqual(self.engine.track.call_count,1)
        self.capture.release.assert_called_once()

    def test_all_exit_and_error_paths_release(self):
        for scenario in ("q","esc","window","window_error","ctrl_c","load","inference","read","ui"):
            self.setUp()
            expected = None
            if scenario == "esc": self.ui.waitKey.return_value = 27
            if scenario == "window": self.ui.waitKey.return_value = -1; self.ui.getWindowProperty.return_value = 0
            if scenario == "window_error": self.ui.waitKey.return_value = -1; self.ui.getWindowProperty.side_effect = self.ui.error("closed")
            if scenario == "ctrl_c": self.engine.track.side_effect = KeyboardInterrupt(); expected = KeyboardInterrupt
            if scenario == "load": self.factory.side_effect = RuntimeError("model"); expected = RuntimeError
            if scenario == "inference": self.engine.track.side_effect = RuntimeError("ReID"); expected = RuntimeError
            if scenario == "read":
                self.capture.read.side_effect = [(True,self.frame),(False,None)]; self.ui.waitKey.return_value = -1; expected = RuntimeError
            if scenario == "ui": self.ui.imshow.side_effect = self.ui.error("GUI"); expected = self.ui.error
            with self.subTest(scenario=scenario):
                if expected:
                    with self.assertRaises(expected): self.run_loop()
                else: self.run_loop()
                self.capture.release.assert_called_once(); self.ui.destroyAllWindows.assert_called_once()

    def test_missing_or_corrupt_profile_main_fails_without_loading_model(self):
        with temporary_directory() as temp:
            store = ZoneStore(Path(temp)/"zones")
            with patch.object(app,"ZoneStore",return_value=store), patch.object(app,"PersonTracker") as engine, \
                    self.assertLogs(app.LOGGER,level="ERROR") as logs:
                self.assertEqual(app.main(),1)
            engine.assert_not_called(); self.assertIn("zone_calibrator","\n".join(logs.output))
            store.directory.mkdir(); (store.directory/"active.json").write_text("{")
            with patch.object(app,"ZoneStore",return_value=store), self.assertLogs(app.LOGGER,level="ERROR"):
                self.assertEqual(app.main(),1)

    def test_main_loads_active_automatically_no_selectors_or_config_writes(self):
        before = {p:p.read_bytes() for p in (PROJECT_ROOT/"config").glob("*.*")}
        store = MagicMock(); store.load_active.return_value = self.profile
        with patch.dict(sys.modules,{"cv2":self.ui}), patch.object(app.sys,"platform","win32"), \
                patch.object(app,"ZoneStore",return_value=store), patch.object(app,"run_zones") as run, \
                patch("builtins.input",side_effect=AssertionError), patch("os.replace",side_effect=AssertionError):
            self.assertEqual(app.main(),0)
        store.load_active.assert_called_once_with()
        run.assert_called_once_with(self.ui,load_config(),load_detection_config(),self.tracking,self.profile)
        self.assertEqual(before,{p:p.read_bytes() for p in (PROJECT_ROOT/"config").glob("*.*")})


if __name__ == "__main__": unittest.main()
