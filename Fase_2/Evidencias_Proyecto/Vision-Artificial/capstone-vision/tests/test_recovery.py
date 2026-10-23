"""Recovery: parámetros y pipeline con inferencia/cámara simuladas, sin pesos."""

import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import src
from src import detector, devices, track, track_fast, track_recovery, tracker
from src.config import (PROJECT_ROOT, load_config, load_detection_config,
                        load_tracking_config, load_tracker_config, resolve_tracker_path)


def recovery_config():
    return {**load_tracking_config(), "tracker_config": track_recovery.RECOVERY_CONFIG}


@contextmanager
def simulated_cv2(ui):
    """Ejecuta la sesión de cámara REAL del proyecto con OpenCV simulado y aislado."""
    previous = getattr(src, "camera", None)
    try:
        with patch.dict(sys.modules, {"cv2": ui}):
            camera = importlib.import_module("src.camera")
            with patch.object(camera, "cv2", ui):
                yield camera
    finally:
        if previous is None:
            if hasattr(src, "camera"):
                delattr(src, "camera")
        else:
            src.camera = previous


def ui_and_capture():
    class CvError(Exception):
        pass
    ui = MagicMock(error=CvError)
    capture = ui.VideoCapture.return_value
    frame = SimpleNamespace(shape=(720, 1280, 3), size=720 * 1280 * 3)
    capture.read.return_value = (True, frame)
    capture.getBackendName.return_value = "MOCK"
    ui.waitKey.return_value = ord("q")
    ui.getWindowProperty.return_value = 1
    return ui, capture, frame


class RecoveryConfigTests(unittest.TestCase):
    def test_exact_recovery_parameters_and_unchanged_baselines(self):
        params = load_tracker_config(resolve_tracker_path(track_recovery.RECOVERY_CONFIG))
        self.assertEqual(params, dict(tracker_type="bytetrack", track_high_thresh=.65,
                         track_low_thresh=.10, new_track_thresh=.65, track_buffer=30,
                         match_thresh=.80, fuse_score=True))
        self.assertEqual(load_detection_config()["confidence_threshold"], .65)
        self.assertEqual(load_tracking_config()["tracker_config"], "config/bytetrack_capstone.yaml")
        for path, kind in ((load_tracking_config()["tracker_config"], "bytetrack"),
                           (track_fast.FASTTRACK_CONFIG, "fasttrack")):
            baseline = load_tracker_config(resolve_tracker_path(path))
            self.assertEqual(baseline["tracker_type"], kind)
            self.assertEqual((baseline["track_high_thresh"], baseline["new_track_thresh"]), (.25, .25))

    def test_recovery_path_is_independent_of_cwd(self):
        expected = PROJECT_ROOT / track_recovery.RECOVERY_CONFIG
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                self.assertEqual(resolve_tracker_path(track_recovery.RECOVERY_CONFIG), expected)
            finally:
                os.chdir(previous)

    def test_recovery_import_is_light_and_does_not_prompt_or_write_configs(self):
        code = '''
import sys
sys.dont_write_bytecode = True
from pathlib import Path
from unittest.mock import patch
before = {p: p.read_bytes() for p in Path("config").iterdir() if p.is_file()}
with patch("builtins.input", side_effect=AssertionError("input")), patch("os.replace", side_effect=AssertionError("write")):
    import src.tracker, src.track, src.track_fast, src.track_recovery
assert not any(x in sys.modules for x in ("torch", "ultralytics", "cv2", "yaml", "lap"))
assert before == {p: p.read_bytes() for p in Path("config").iterdir() if p.is_file()}
'''
        result = subprocess.run([sys.executable, "-c", code], cwd=PROJECT_ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_entrypoint_delegates_exact_overrides(self):
        with patch.object(track, "main", return_value=0) as main:
            self.assertEqual(track_recovery.main(), 0)
        main.assert_called_once_with(tracker_config="config/bytetrack_recovery_capstone.yaml",
                                     tracker_label="ByteTrack Recovery (Experimental)",
                                     tracking_confidence_override=.10)


class RecoveryPipelineTests(unittest.TestCase):
    def setUp(self):
        self.base = load_detection_config()
        self.frame = SimpleNamespace(shape=(720, 1280, 3), size=100)
        self.model = MagicMock(names={0: "person"})
        self.result = MagicMock()
        self.result.boxes.is_track = True
        self.result.boxes.data.cpu.return_value.tolist.return_value = [[10, 20, 100, 200, 7, .35, 0]]
        self.result.speed = {"inference": 10}
        self.model.track.return_value = [self.result]
        self.factory = MagicMock(return_value=self.model)
        for mock in (patch.object(detector, "_load_yolo", return_value=self.factory),
                     patch.object(devices, "load_device_preference", return_value=None)):
            mock.start()
            self.addCleanup(mock.stop)

    def make_tracker(self, **kwargs):
        return tracker.PersonTracker(self.base, recovery_config(), **kwargs)

    def test_recovery_passes_effective_confidence_without_mutating_general_config(self):
        before = self.base.copy()
        engine = self.make_tracker(tracking_confidence_override=.10)
        result = engine.track(self.frame)
        args = self.model.track.call_args.kwargs
        self.assertEqual(args["conf"], .10)
        self.assertEqual(engine.tracking_confidence, .10)
        self.assertEqual(engine.config["confidence_threshold"], .65)
        self.assertEqual(self.base, before)
        self.assertEqual(args["tracker"], str(PROJECT_ROOT / track_recovery.RECOVERY_CONFIG))
        self.assertEqual((args["classes"], args["iou"], args["imgsz"], args["device"]), ([0], .7, 640, "cpu"))
        self.assertIs(args["persist"], True)
        self.assertEqual((result.tracks[0].track_id, result.tracks[0].confidence), (7, .35))
        for name in ("save", "save_txt", "save_conf", "save_crop", "show", "visualize", "augment", "stream"):
            self.assertIs(args[name], False)

    def test_optional_override_keeps_bytetrack_and_fasttrack_at_general_confidence(self):
        for config in (load_tracking_config(), {**load_tracking_config(), "tracker_config": track_fast.FASTTRACK_CONFIG}):
            for kwargs in ({}, {"tracking_confidence_override": None}):
                with self.subTest(config=config, kwargs=kwargs):
                    engine = tracker.PersonTracker(self.base, config, **kwargs)
                    engine.track(self.frame)
                    self.assertEqual(self.model.track.call_args.kwargs["conf"], .65)
                    self.assertEqual(engine.tracking_confidence, .65)

    def test_detect_still_predicts_with_general_confidence(self):
        self.model.predict.return_value = [SimpleNamespace(boxes=None, speed={})]
        detector.PersonDetector(self.base).detect(self.frame)
        self.assertEqual(self.model.predict.call_args.kwargs["conf"], .65)
        self.model.track.assert_not_called()

    def test_override_invalid_rejected_before_model_load(self):
        for value in ("0.10", True, False, float("nan"), float("inf"), -float("inf"), -.1, 1.1, 10**1000, [], {}):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "confianza efectiva"):
                self.make_tracker(tracking_confidence_override=value)
        self.factory.assert_not_called()

    def test_none_must_resolve_to_a_valid_general_value(self):
        self.base["confidence_threshold"] = None
        with self.assertRaisesRegex(ValueError, "confianza efectiva"):
            self.make_tracker(tracking_confidence_override=None)
        self.factory.assert_not_called()

    def test_finite_boundary_values_are_not_replaced_by_truthiness(self):
        for value in (0, .10, 1):
            with self.subTest(value=value):
                self.make_tracker(tracking_confidence_override=value).track(self.frame)
                self.assertEqual(self.model.track.call_args.kwargs["conf"], value)

    def test_new_track_threshold_below_high_rejected_only_for_override(self):
        params = load_tracker_config(resolve_tracker_path(track_recovery.RECOVERY_CONFIG))
        params["new_track_thresh"] = .60
        with patch.object(tracker, "load_tracker_config", return_value=params):
            with self.assertRaisesRegex(ValueError, "new_track_thresh"):
                self.make_tracker(tracking_confidence_override=.10)
            self.factory.assert_not_called()
            self.make_tracker()  # Las reglas anteriores no cambian sin override.

    def test_low_must_be_less_than_high_before_loading(self):
        params = load_tracker_config(resolve_tracker_path(track_recovery.RECOVERY_CONFIG))
        for low in (.65, .70):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "invalid.yaml"
                path.write_text(json.dumps({**params, "track_low_thresh": low}))
                with patch.object(tracker, "resolve_tracker_path", return_value=path), \
                        self.assertRaisesRegex(ValueError, "track_low_thresh"):
                    self.make_tracker(tracking_confidence_override=.10)
        self.factory.assert_not_called()

    def test_one_model_and_one_track_per_frame_no_extra_predict_or_install(self):
        with patch("subprocess.run", side_effect=AssertionError("no instalar")), \
                patch("os.system", side_effect=AssertionError("no instalar")):
            engine = self.make_tracker(tracking_confidence_override=.10)
            engine.track(self.frame)
            engine.track(self.frame)
        self.factory.assert_called_once_with(str(PROJECT_ROOT / "yolo26n.pt"), task="detect")
        self.assertEqual(self.model.track.call_count, 2)
        self.model.predict.assert_not_called()

    def test_low_confidence_untracked_detections_are_not_hidden_or_given_ids(self):
        self.result.boxes.is_track = False
        self.result.boxes.data.cpu.return_value.tolist.return_value = [
            [10, 20, 100, 200, .35, 0], [10, 20, 100, 200, .8, 1]]
        result = self.make_tracker(tracking_confidence_override=.10).track(self.frame)
        self.assertEqual(result.tracks, ())
        self.assertEqual(len(result.untracked_detections), 1)
        self.assertEqual(result.untracked_detections[0].confidence, .35)

    def test_logging_uses_effective_thresholds_without_false_baseline_warning(self):
        with self.assertLogs(tracker.LOGGER, level="INFO") as logs:
            self.make_tracker(tracking_confidence_override=.10)
        output = "\n".join(logs.output)
        for text in ("YOLO tracking conf: 0.10", "confianza general: 0.65", "track_high_thresh: 0.65",
                     "track_low_thresh: 0.1", "new_track_thresh: 0.65", "track_buffer: 30"):
            self.assertIn(text, output)
        self.assertNotIn("segunda asociación", output)
        with self.assertLogs(tracker.LOGGER, level="WARNING") as baseline:
            tracker.PersonTracker(self.base, load_tracking_config())
        self.assertIn("conf=0.65", "\n".join(baseline.output))

    def test_same_device_resolver_and_local_preference_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "device.local.json"
            for preference, available, expected in ((None, False, "cpu"), ("cpu", True, "cpu"),
                                                     ("cuda:0", True, "cuda:0"), ("cuda:0", False, "cpu")):
                path.write_text(json.dumps({"device": preference}))
                before = path.read_bytes()
                torch = MagicMock()
                torch.version.cuda = "13.2" if available else None
                torch.cuda.is_available.return_value = available
                torch.cuda.device_count.return_value = 1 if available else 0
                torch.ones.return_value.item.return_value = 2
                with self.subTest(preference=preference, available=available), \
                        patch.object(devices, "load_device_preference", side_effect=lambda _: json.loads(path.read_text())["device"]), \
                        patch.object(devices, "load_torch", return_value=torch), \
                        patch.object(detector, "resolve_effective_device", wraps=devices.resolve_effective_device) as resolver:
                    engine = self.make_tracker(tracking_confidence_override=.10)
                    engine.track(self.frame)
                    resolver.assert_called_once_with("cpu")
                    self.assertEqual(self.model.track.call_args.kwargs["device"], expected)
                    self.assertEqual(engine.device_resolution.local_preference, preference)
                self.assertEqual(path.read_bytes(), before)

    def test_sessions_do_not_share_models_or_override(self):
        self.factory.side_effect = [MagicMock(names={0: "person"}), MagicMock(names={0: "person"})]
        recovery = self.make_tracker(tracking_confidence_override=.10)
        baseline = tracker.PersonTracker(self.base, load_tracking_config())
        self.assertIsNot(recovery._model, baseline._model)
        self.assertEqual((recovery.tracking_confidence, baseline.tracking_confidence), (.10, .65))


class RecoveryLoopTests(unittest.TestCase):
    def test_all_entrypoints_use_same_camera_and_in_memory_detection(self):
        before = {p: p.read_bytes() for p in (PROJECT_ROOT / "config").iterdir() if p.is_file()}
        ui, _, _ = ui_and_capture()
        with patch.dict(sys.modules, {"cv2": ui}), patch.object(track.sys, "platform", "win32"), \
                patch.object(track, "run_tracking") as run, patch("builtins.input", side_effect=AssertionError("input")):
            for entry in (track.main, track_fast.main, track_recovery.main):
                self.assertEqual(entry(), 0)
            base, fast, recovery = run.call_args_list
        for call in (base, fast, recovery):
            self.assertEqual(call.args[1], load_config())
            self.assertEqual(call.args[2], load_detection_config())
        self.assertEqual(base.kwargs, {})
        self.assertEqual(fast.kwargs, {"tracker_label": "FastTracker"})
        self.assertEqual(recovery.kwargs, {"tracker_label": track_recovery.RECOVERY_LABEL,
                                         "tracking_confidence_override": .10})
        self.assertEqual(recovery.args[3], recovery_config())
        self.assertEqual(before, {p: p.read_bytes() for p in (PROJECT_ROOT / "config").iterdir() if p.is_file()})

    def run_scenario(self, scenario="q", *, baseline=False):
        ui, capture, frame = ui_and_capture()
        model = MagicMock(names={0: "person"})
        result = MagicMock()
        result.boxes.is_track = True
        result.boxes.data.cpu.return_value.tolist.return_value = [[10, 20, 100, 200, 7, .35, 0]]
        result.speed = {"inference": 10}
        model.track.return_value = [result]
        factory = MagicMock(return_value=model)
        expected = None
        if scenario == "esc": ui.waitKey.return_value = 27
        if scenario == "close":
            ui.waitKey.return_value = -1
            ui.getWindowProperty.return_value = 0
        if scenario == "ctrl_c":
            model.track.side_effect = KeyboardInterrupt()
            expected = KeyboardInterrupt
        if scenario == "load_error":
            factory.side_effect = RuntimeError("modelo ausente")
            expected = RuntimeError
        if scenario == "track_error":
            model.track.side_effect = RuntimeError("tracking falló")
            expected = RuntimeError
        if scenario == "read_error":
            ui.waitKey.return_value = -1
            capture.read.side_effect = [(True, frame), (False, None)]
            expected = RuntimeError
        if scenario == "ui_error":
            ui.imshow.side_effect = ui.error("GUI")
            expected = ui.error
        if scenario == "three_frames": ui.waitKey.side_effect = [-1, -1, ord("q")]
        options = {} if baseline else {"tracker_label": track_recovery.RECOVERY_LABEL,
                                      "tracking_confidence_override": .10}
        with simulated_cv2(ui), patch.object(devices, "load_device_preference", return_value=None), \
                patch.object(detector, "_load_yolo", return_value=factory), \
                patch.object(track.time, "perf_counter", side_effect=iter(range(100))):
            args = (ui, load_config(), load_detection_config(), load_tracking_config() if baseline else recovery_config())
            if expected:
                with self.assertRaises(expected): track.run_tracking(*args, **options)
            else:
                track.run_tracking(*args, **options)
        capture.release.assert_called_once()
        ui.destroyAllWindows.assert_called_once()
        return ui, model, factory

    def test_quit_escape_close_ctrl_c_and_failures_release_resources(self):
        for scenario in ("q", "esc", "close", "ctrl_c", "load_error", "track_error", "read_error", "ui_error"):
            with self.subTest(scenario=scenario): self.run_scenario(scenario)

    def test_shared_loop_passes_override_and_preserves_metrics_colors_and_weak_box(self):
        base_ui, base_model, _ = self.run_scenario("three_frames", baseline=True)
        ui, model, factory = self.run_scenario("three_frames")
        self.assertEqual(base_model.track.call_args.kwargs["conf"], .65)
        self.assertEqual(model.track.call_args.kwargs["conf"], .10)
        self.assertEqual(model.track.call_count, 3)
        self.assertEqual(factory.call_count, 1)
        before = [c.args[1] for c in base_ui.putText.call_args_list]
        after = [c.args[1] for c in ui.putText.call_args_list]
        self.assertEqual([s.replace("ByteTrack", track_recovery.RECOVERY_LABEL) for s in before], after)
        self.assertIn("ID 7 | person | 0.35", after)
        for metric in ("FPS pipeline:", "Inferencia YOLO:", "YOLO + tracking:", "Tracks activos:", "Cajas sin ID:"):
            self.assertTrue(any(metric in s for s in after), metric)
        self.assertEqual([c.args[-2:] for c in base_ui.rectangle.call_args_list],
                         [c.args[-2:] for c in ui.rectangle.call_args_list])
        self.assertEqual(base_ui.line.call_count, ui.line.call_count)
        self.assertIn(track_recovery.RECOVERY_LABEL, ui.namedWindow.call_args.args[0])

    def test_invalid_override_main_returns_controlled_error_and_releases(self):
        ui, capture, _ = ui_and_capture()
        with simulated_cv2(ui), patch.object(track.sys, "platform", "win32"), \
                patch.object(detector, "_load_yolo") as factory, self.assertLogs(track.LOGGER, level="ERROR"):
            self.assertEqual(track.main(tracker_config=track_recovery.RECOVERY_CONFIG,
                                       tracking_confidence_override=float("nan")), 1)
        factory.assert_not_called()
        capture.release.assert_called_once()
        ui.destroyAllWindows.assert_called_once()


if __name__ == "__main__":
    unittest.main()
