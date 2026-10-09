"""Comparación controlada FastTracker: sin webcam, GPU física ni pesos."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import cv2
import yaml

from src import camera, detector, devices, track, track_fast, tracker
from src.config import (PROJECT_ROOT, load_config, load_detection_config,
                        load_tracking_config, load_bytetrack_config,
                        load_tracker_config, resolve_tracker_path)
from src.tracker import Detection, FrameTracks, Track
from test_device_selector import fake_torch


def fast_config():
    return {**load_tracking_config(), "tracker_config": track_fast.FASTTRACK_CONFIG}


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.base_path = resolve_tracker_path(load_tracking_config()["tracker_config"])
        self.fast_path = resolve_tracker_path(track_fast.FASTTRACK_CONFIG)
        self.base = load_bytetrack_config(self.base_path)
        self.fast = load_tracker_config(self.fast_path)

    def test_default_tracking_remains_bytetrack(self):
        self.assertEqual(load_tracking_config()["tracker_config"], "config/bytetrack_capstone.yaml")
        self.assertEqual(self.base["tracker_type"], "bytetrack")
        self.assertEqual(self.fast["tracker_type"], "fasttrack")

    def test_shared_values_identical_to_baseline(self):
        for key, value in self.base.items():
            if key != "tracker_type":
                self.assertEqual(self.fast[key], value, key)
        self.assertEqual(load_detection_config()["confidence_threshold"], .65)

    def test_fast_specific_values_are_official_defaults(self):
        import importlib.metadata as metadata
        self.assertEqual(metadata.version("ultralytics"), "8.4.163")
        bundled = Path(metadata.distribution("ultralytics").locate_file("ultralytics/cfg/trackers/fasttrack.yaml"))
        official = yaml.safe_load(bundled.read_text())
        for key in set(self.fast) - set(self.base):
            self.assertEqual(self.fast[key], official[key], key)
        self.assertNotIn("with_reid", self.fast)
        self.assertNotIn("model", self.fast)

    def test_strict_bytetrack_loader_still_rejects_fasttrack(self):
        with self.assertRaisesRegex(ValueError, "tracker_type"):
            load_bytetrack_config(self.fast_path)

    def test_fast_config_bom_and_other_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fasttrack.yaml"
            path.write_text(yaml.safe_dump(self.fast), encoding="utf-8-sig")
            self.assertEqual(load_tracker_config(path), self.fast)
            before = Path.cwd()
            try:
                os.chdir(directory)
                self.assertEqual(resolve_tracker_path(track_fast.FASTTRACK_CONFIG), self.fast_path)
            finally:
                os.chdir(before)

    def test_fast_invalid_fields_and_reid_rejected(self):
        cases = [{**self.fast, "with_reid": True}, {**self.fast, "tracker_type": "botsort"},
                 {key: val for key, val in self.fast.items() if key != "occ_cover_thresh"}]
        cases += [{**self.fast, key: val} for key, val in (
            ("reset_velocity_offset_occ", -1), ("reset_pos_offset_occ", True),
            ("active_occ_to_lost_thresh", 1.5), ("occ_reappear_window", "40"),
            ("enlarge_bbox_occ", .5), ("enlarge_bbox_occ", float("inf")),
            ("dampen_motion_occ", 1.1), ("init_iou_suppress", float("nan")),
            ("occ_cover_thresh", "0.7"))]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fasttrack.yaml"
            for case in cases:
                path.write_text(yaml.safe_dump(case))
                with self.subTest(case=case), self.assertRaises(ValueError):
                    load_tracker_config(path)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.config = load_detection_config()
        self.model = MagicMock()
        self.model.names = {0: "person"}
        self.result = MagicMock()
        self.result.boxes.is_track = True
        self.result.boxes.data.cpu.return_value.tolist.return_value = [[1, 2, 30, 40, 7, .9, 0]]
        self.result.speed = {"inference": 10}
        self.model.track.return_value = [self.result]
        self.factory = MagicMock(return_value=self.model)
        loader = patch.object(detector, "_load_yolo", return_value=self.factory)
        loader.start()
        self.addCleanup(loader.stop)
        preference = patch.object(devices, "load_device_preference", return_value=None)
        preference.start()
        self.addCleanup(preference.stop)
        self.frame = SimpleNamespace(shape=(480, 640, 3), size=480 * 640 * 3)

    def test_person_tracker_default_stays_bytetrack(self):
        instance = tracker.PersonTracker()
        instance.track(self.frame)
        self.assertEqual(instance.tracker_label, "ByteTrack")
        self.assertEqual(self.model.track.call_args.kwargs["tracker"], str(PROJECT_ROOT / "config/bytetrack_capstone.yaml"))

    def test_override_uses_fast_yaml_persist_and_same_detection(self):
        config = fast_config()
        before = config.copy()
        instance = tracker.PersonTracker(self.config, config)
        result = instance.track(self.frame)
        self.assertEqual(instance.tracker_label, "FastTracker")
        args = self.model.track.call_args.kwargs
        self.assertEqual(args["tracker"], str(resolve_tracker_path(track_fast.FASTTRACK_CONFIG)))
        self.assertIs(args["persist"], True)
        self.assertEqual(args["classes"], [0])
        self.assertEqual((args["conf"], args["iou"], args["imgsz"]), (.65, .7, 640))
        self.assertEqual(args["device"], "cpu")
        self.assertEqual([item.track_id for item in result.tracks], [7])
        self.assertEqual(config, before)
        for key in ("save", "save_txt", "save_conf", "save_crop", "show", "visualize", "augment", "stream"):
            self.assertIs(args[key], False)

    def test_one_model_one_track_per_frame_no_predict(self):
        instance = tracker.PersonTracker(self.config, fast_config())
        instance.track(self.frame)
        instance.track(self.frame)
        self.factory.assert_called_once_with(str(PROJECT_ROOT / "yolo26n.pt"), task="detect")
        self.assertEqual(self.model.track.call_count, 2)
        self.model.predict.assert_not_called()
        self.model.train.assert_not_called()

    def test_untracked_person_and_class_filter_unchanged(self):
        self.result.boxes.is_track = False
        self.result.boxes.data.cpu.return_value.tolist.return_value = [
            [1, 2, 30, 40, .8, 0], [1, 2, 30, 40, .9, 1]]
        result = tracker.PersonTracker(self.config, fast_config()).track(self.frame)
        self.assertEqual(result.tracks, ())
        self.assertEqual(result.untracked_detections, (Detection(1, 2, 30, 40, .8, 0),))

    def test_same_device_resolver_cpu_gpu_and_fallback(self):
        for preference, available, expected in ((None, False, "cpu"), ("cpu", True, "cpu"),
                                                ("cuda:0", True, "cuda:0"), ("cuda:0", False, "cpu")):
            torch = fake_torch(1, available, "13.2" if available else None)
            with self.subTest(preference=preference, available=available), \
                    patch.object(devices, "load_device_preference", return_value=preference), \
                    patch.object(devices, "load_torch", return_value=torch), \
                    patch.object(detector, "resolve_effective_device", wraps=devices.resolve_effective_device) as resolve:
                instance = tracker.PersonTracker(self.config, fast_config())
                instance.track(self.frame)
                self.assertEqual(self.model.track.call_args.kwargs["device"], expected)
                self.assertEqual(instance.device_resolution.local_preference, preference)
                resolve.assert_called_once_with("cpu")

    def test_fallback_preserves_local_preference_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "device.local.json"
            path.write_text('{"device":"cuda:0"}')
            before = path.read_bytes()
            with patch.object(devices, "load_device_preference", side_effect=lambda _: json.loads(path.read_text())["device"]), \
                    patch.object(devices, "load_torch", return_value=fake_torch()), \
                    self.assertLogs(devices.LOGGER, level="WARNING"):
                instance = tracker.PersonTracker(self.config, fast_config())
                instance.track(self.frame)
            self.assertEqual(instance.config["device"], "cpu")
            self.assertEqual(path.read_bytes(), before)

    def test_separate_instances_do_not_share_models_or_sessions(self):
        models = [MagicMock(names={0: "person"}), MagicMock(names={0: "person"})]
        self.factory.side_effect = models
        first = tracker.PersonTracker(self.config, load_tracking_config())
        second = tracker.PersonTracker(self.config, fast_config())
        self.assertIsNot(first._model, second._model)
        self.assertIsNot(first.config, second.config)
        self.assertIsNot(first.tracking_config, second.tracking_config)


class EntrypointAndResourceTests(unittest.TestCase):
    def test_imports_are_light_and_do_not_write_or_prompt(self):
        code = '''
import sys
sys.dont_write_bytecode = True
from pathlib import Path
from unittest.mock import patch
before = {p: p.read_bytes() for p in Path("config").iterdir() if p.is_file()}
with patch("builtins.input", side_effect=AssertionError("menú")), patch("os.replace", side_effect=AssertionError("escritura")):
    import src.track, src.track_fast, src.tracker
assert all(x not in sys.modules for x in ("torch", "ultralytics", "cv2", "yaml", "lap"))
assert before == {p: p.read_bytes() for p in before}
'''
        result = subprocess.run([sys.executable, "-c", code], cwd=PROJECT_ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_fast_entrypoint_delegates_to_shared_main(self):
        with patch.object(track, "main", return_value=0) as main:
            self.assertEqual(track_fast.main(), 0)
        main.assert_called_once_with(tracker_config="config/fasttrack_capstone.yaml", tracker_label="FastTracker")

    def test_both_entrypoints_share_camera_detection_and_display_settings(self):
        before = {p: p.read_bytes() for p in (PROJECT_ROOT / "config").iterdir() if p.is_file()}
        with patch.object(track.sys, "platform", "win32"), patch.object(track, "run_tracking") as run:
            self.assertEqual(track.main(), 0)
            baseline = run.call_args
            self.assertEqual(track_fast.main(), 0)
            fast = run.call_args
        self.assertEqual(baseline.args[1], fast.args[1])
        self.assertEqual(baseline.args[2], fast.args[2])
        self.assertEqual(baseline.args[3], load_tracking_config())
        self.assertEqual(fast.args[3], fast_config())
        self.assertEqual(fast.kwargs, {"tracker_label": "FastTracker"})
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        local = PROJECT_ROOT / "config/device.local.json"
        self.assertEqual(local.exists(), local in before)

    def run_loop(self, label, *, scenario="q", frames=1):
        capture = MagicMock()
        capture.getBackendName.return_value = "MOCK"
        frame = MagicMock(shape=(480, 640, 3), size=100)
        capture.read.return_value = (True, frame)
        ui = MagicMock(error=cv2.error)
        ui.waitKey.return_value = ord("q")
        ui.getWindowProperty.return_value = 1
        engine = MagicMock()
        engine.config = load_detection_config()
        engine.bytetrack_config = {"track_buffer": 30}
        engine.track.return_value = FrameTracks((Track(1, 2, 30, 40, .9, 0, 7),), (), 10, 15)
        load_error = None
        expected_error = None
        if scenario == "esc":
            ui.waitKey.return_value = 27
        elif scenario == "close":
            ui.waitKey.return_value = -1
            ui.getWindowProperty.return_value = 0
        elif scenario == "ctrl_c":
            engine.track.side_effect = KeyboardInterrupt()
            expected_error = KeyboardInterrupt
        elif scenario == "load_error":
            load_error = RuntimeError("modelo")
            expected_error = RuntimeError
        elif scenario == "track_error":
            engine.track.side_effect = RuntimeError("tracker")
            expected_error = RuntimeError
        elif scenario == "read_error":
            ui.waitKey.return_value = -1
            capture.read.side_effect = [(True, frame), (False, None)]
            expected_error = RuntimeError
        elif scenario == "ui_error":
            ui.imshow.side_effect = cv2.error("GUI")
            expected_error = cv2.error
        elif scenario == "no_id":
            engine.track.return_value = FrameTracks((), (Detection(1, 2, 30, 40, .8, 0),), 10, 15)
        if frames > 1:
            ui.waitKey.side_effect = [-1] * (frames - 1) + [ord("q")]
        with patch.object(camera.cv2, "VideoCapture", return_value=capture), \
                patch.object(track, "PersonTracker", return_value=engine, side_effect=load_error), \
                patch.object(track.time, "perf_counter", side_effect=[1000, 1000.5, 1001]):
            if expected_error:
                with self.assertRaises(expected_error):
                    track.run_tracking(ui, load_config(), load_detection_config(),
                                       fast_config() if label == "FastTracker" else load_tracking_config(),
                                       tracker_label=label)
            else:
                track.run_tracking(ui, load_config(), load_detection_config(),
                                   fast_config() if label == "FastTracker" else load_tracking_config(),
                                   tracker_label=label)
        capture.release.assert_called_once()
        ui.destroyAllWindows.assert_called_once()
        return ui

    def test_fast_quit_escape_window_ctrl_c_and_failures_release_resources(self):
        for scenario in ("q", "esc", "close", "ctrl_c", "load_error", "track_error", "read_error", "ui_error"):
            with self.subTest(scenario=scenario):
                self.run_loop("FastTracker", scenario=scenario)

    def test_overlay_metrics_and_colors_change_only_tracker_label(self):
        baseline = self.run_loop("ByteTrack", frames=3)
        fast = self.run_loop("FastTracker", frames=3)
        before = [c.args[1] for c in baseline.putText.call_args_list]
        after = [c.args[1] for c in fast.putText.call_args_list]
        self.assertEqual([label.replace("ByteTrack", "FastTracker") for label in before], after)
        self.assertTrue(any("FPS pipeline: 2.0" in label for label in after))
        self.assertTrue(any("Inferencia YOLO: 10.0 ms" in label for label in after))
        self.assertEqual([c.args[-2:] for c in baseline.rectangle.call_args_list],
                         [c.args[-2:] for c in fast.rectangle.call_args_list])
        self.assertEqual(baseline.line.call_count, fast.line.call_count)
        self.assertEqual(fast.namedWindow.call_args.args[0], "CAPSTONE - FastTracker - q / ESC para salir")

    def test_fast_untracked_detection_remains_visible(self):
        ui = self.run_loop("FastTracker", scenario="no_id")
        self.assertTrue(any("person | sin ID | 0.80" == c.args[1] for c in ui.putText.call_args_list))
        ui.line.assert_not_called()


if __name__ == "__main__":
    unittest.main()
