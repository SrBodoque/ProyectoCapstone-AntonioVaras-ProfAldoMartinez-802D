"""Selección y recursos sin cámaras, pesos YOLO ni ventanas reales."""

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
import weakref
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

from src import camera, detect, diagnostics, main, track, main_seleccionar_camera
from src.camera_cli import CameraSelectionCancelled, parse_camera_args
from src.config import CONFIG_PATH, PROJECT_ROOT, load_config, load_detection_config, load_tracking_config
from src.detector import FrameDetections
from src.tracker import FrameTracks


def candidate(index):
    return camera.CameraCandidate(index, 640, 480, 30.0, "FAKE")


class CaptureFactory:
    """Cada instancia modela un handle separado; detecta solapamientos reales."""
    def __init__(self, available=(0, 2), failure=None):
        self.available = set(available)
        self.failure = failure
        self.captures = []
        self.active = set()
        self.opened = []
        self.frames = []  # Referencias débiles: el fake tampoco conserva imágenes.

    def __call__(self):
        capture = FakeCapture(self)
        self.captures.append(capture)
        return capture

    def assert_released(self, test):
        test.assertFalse(self.active)
        test.assertTrue(self.captures)
        test.assertTrue(all(c.releases == 1 for c in self.captures))


class FakeCapture:
    def __init__(self, owner):
        self.owner = owner
        self.releases = 0
        self.index = None
        self.reads = 0

    def fail(self, stage):
        if self.owner.failure and self.owner.failure[0] == stage:
            raise self.owner.failure[1]

    def open(self, index, api):
        if self.owner.active:
            raise AssertionError("Otra captura sigue abierta")
        self.index = index
        self.owner.active.add(self)
        self.owner.opened.append((index, api))
        self.fail("open")
        return index in self.owner.available

    def isOpened(self):
        return self.index in self.owner.available

    def set(self, prop, value):
        self.fail("set")
        return True

    def read(self):
        self.reads += 1
        self.fail("read")
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.owner.frames.append(weakref.ref(frame))
        return True, frame

    def get(self, prop):
        self.fail("get")
        return 30.0 if prop == cv2.CAP_PROP_FPS else 9999.0

    def getBackendName(self):
        self.fail("backend")
        return "FAKE"

    def release(self):
        self.releases += 1
        self.owner.active.discard(self)


class MultiCameraTests(unittest.TestCase):
    def setUp(self):
        self.config = {**load_config(), "camera_index": "auto"}
        self.output = io.StringIO()
        self.enterContext(contextlib.redirect_stdout(self.output))

    def captures(self, factory):
        self.enterContext(patch.object(camera.cv2, "VideoCapture", side_effect=factory))
        self.enterContext(patch.object(camera, "backend_candidates", return_value=[("fake", 123)]))

    def interactive(self):
        self.enterContext(patch.object(camera.sys, "stdin", MagicMock(isatty=lambda: True)))

    def test_config_accepts_auto_zero_positive_and_max(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "camera.json"
            for value in ("auto", 0, 1, 7, 2**31 - 1):
                with self.subTest(value=value):
                    path.write_text(json.dumps({**self.config, "camera_index": value}))
                    self.assertEqual(load_config(path)["camera_index"], value)

    def test_config_rejects_invalid_types_and_ranges(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "camera.json"
            for value in (-1, 1.5, True, False, "0", "AUTO", "automatico", " auto", None, [], {}, 2**31):
                with self.subTest(value=value):
                    path.write_text(json.dumps({**self.config, "camera_index": value}))
                    with self.assertRaisesRegex(ValueError, "camera_index"):
                        load_config(path)

    def test_cli_priority_no_scan_no_json_write(self):
        before = CONFIG_PATH.read_bytes()
        with patch.object(camera, "discover_cameras") as scan, patch("builtins.input") as prompt:
            for value in (0, "auto"):
                config = {**self.config, "camera_index": value}
                result = camera.resolve_camera_config(config, 1)
                self.assertEqual(result, {**config, "camera_index": 1})
                self.assertEqual(config["camera_index"], value)
                self.assertIsNot(result, config)
            scan.assert_not_called()
            prompt.assert_not_called()
        self.assertEqual(CONFIG_PATH.read_bytes(), before)

    def test_fixed_zero_and_index_outside_scan_bypass_discovery(self):
        with patch.object(camera, "discover_cameras") as scan, patch("builtins.input") as prompt:
            for index in (0, 1, 9):
                self.assertEqual(camera.resolve_camera_config({**self.config, "camera_index": index})["camera_index"], index)
            scan.assert_not_called()
            prompt.assert_not_called()

    def test_invalid_programmatic_override_rejected(self):
        for value in (-1, True, False, 1.5, "auto", "0"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                camera.resolve_camera_config(self.config, value)

    def test_auto_zero_clear_error(self):
        with patch.object(camera, "discover_cameras", return_value=[]) as scan, patch("builtins.input") as prompt:
            with self.assertRaisesRegex(RuntimeError, "diagnostics --scan"):
                camera.resolve_camera_config(self.config)
            scan.assert_called_once_with(self.config)
            prompt.assert_not_called()

    def test_auto_single_nonzero_without_stdin(self):
        with patch.object(camera, "discover_cameras", return_value=[candidate(2)]) as scan, \
                patch.object(camera.sys, "stdin", None), patch("builtins.input") as prompt:
            self.assertEqual(camera.resolve_camera_config(self.config)["camera_index"], 2)
            scan.assert_called_once()
            prompt.assert_not_called()
        self.assertIn("automáticamente cámara 2", self.output.getvalue())

    def test_multiple_nonconsecutive_and_invalid_retry_without_rescan(self):
        self.interactive()
        with patch.object(camera, "discover_cameras", return_value=[candidate(0), candidate(2)]) as scan, \
                patch("builtins.input", side_effect=["hola", "-1", "99", "1", "1.5", "", "2"]) as prompt:
            self.assertEqual(camera.resolve_camera_config(self.config)["camera_index"], 2)
            scan.assert_called_once()
            self.assertEqual(prompt.call_count, 7)
        self.assertEqual(self.output.getvalue().count("Selección inválida"), 6)

    def test_multiple_can_select_zero(self):
        self.interactive()
        with patch("builtins.input", return_value="0"):
            self.assertEqual(camera.select_camera([candidate(0), candidate(2)]), 0)

    def test_q_cancels(self):
        self.interactive()
        with patch("builtins.input", return_value=" q "), self.assertRaises(CameraSelectionCancelled):
            camera.select_camera([candidate(0), candidate(2)])

    def test_eof_and_unreadable_stdin_are_controlled(self):
        self.interactive()
        for error in (EOFError(), OSError(), ValueError()):
            with self.subTest(error=type(error)), patch("builtins.input", side_effect=error):
                with self.assertRaisesRegex(RuntimeError, "--camera N"):
                    camera.select_camera([candidate(0), candidate(2)])

    def test_noninteractive_never_calls_input(self):
        for stdin in (None, io.StringIO(), MagicMock(isatty=MagicMock(side_effect=ValueError()))):
            with self.subTest(stdin=type(stdin)), patch.object(camera.sys, "stdin", stdin), patch("builtins.input") as prompt:
                with self.assertRaisesRegex(RuntimeError, "entrada interactiva"):
                    camera.select_camera([candidate(0), candidate(2)])
                prompt.assert_not_called()

    def test_probe_actual_dimensions_release_and_discard_frame(self):
        factory = CaptureFactory()
        self.captures(factory)
        found = camera.probe_camera(self.config, 2)
        self.assertEqual(found, candidate(2))  # 640x480, no solicitado 1280x720 ni informado 9999.
        factory.assert_released(self)
        self.assertEqual(factory.captures[0].reads, 1)
        self.assertTrue(all(ref() is None for ref in factory.frames))

    def test_failed_read_empty_or_none_release(self):
        for result in ((False, None), (True, None), (True, np.empty((0, 0, 3)))):
            factory = CaptureFactory()
            with self.subTest(result=str(result)), patch.object(camera.cv2, "VideoCapture", side_effect=factory), \
                    patch.object(camera, "backend_candidates", return_value=[("fake", 123)]), \
                    patch.object(FakeCapture, "read", return_value=result):
                with self.assertRaises(RuntimeError):
                    camera.probe_camera(self.config, 0)
                factory.assert_released(self)

    def test_probe_exceptions_and_interrupt_release(self):
        for stage in ("open", "set", "read"):
            for error in (cv2.error("fake"), OSError("fake"), KeyboardInterrupt()):
                factory = CaptureFactory(failure=(stage, error))
                with self.subTest(stage=stage, error=type(error)), \
                        patch.object(camera.cv2, "VideoCapture", side_effect=factory), \
                        patch.object(camera, "backend_candidates", return_value=[("fake", 123)]):
                    with self.assertRaises(KeyboardInterrupt if isinstance(error, KeyboardInterrupt) else RuntimeError):
                        camera.probe_camera(self.config, 0)
                    factory.assert_released(self)

    def test_metadata_unavailable_still_returns_functional_camera(self):
        factory = CaptureFactory()
        self.captures(factory)
        with patch.object(FakeCapture, "get", side_effect=cv2.error("unknown")), \
                patch.object(FakeCapture, "getBackendName", side_effect=cv2.error("unknown")):
            found = camera.probe_camera(self.config, 0)
        self.assertIsNone(found.fps)
        self.assertEqual(found.backend, "no informado")
        self.assertIn("desconocidos", camera.describe_camera(found))
        factory.assert_released(self)

    def test_invalid_reported_fps_is_unknown(self):
        for fps in (0, -1, float("nan"), float("inf"), None):
            with self.subTest(fps=fps):
                capture = MagicMock(get=MagicMock(return_value=fps))
                self.assertIsNone(camera.camera_info(capture)["fps"])

    def test_scan_sequential_exact_range_unique_indices_and_all_released(self):
        factory = CaptureFactory()
        self.captures(factory)
        found = camera.discover_cameras(self.config)
        self.assertEqual([c.index for c in found], [0, 2])
        self.assertEqual([index for index, api in factory.opened], list(range(5)))
        factory.assert_released(self)
        self.assertTrue(all(ref() is None for ref in factory.frames))

    def test_scan_releases_everything_before_prompt_and_cancellation(self):
        factory = CaptureFactory()
        self.captures(factory)
        self.interactive()
        def cancel(prompt):
            factory.assert_released(self)
            return "q"
        with patch("builtins.input", side_effect=cancel), self.assertRaises(CameraSelectionCancelled):
            camera.resolve_camera_config(self.config)
        factory.assert_released(self)

    def test_scan_continues_after_index_exception(self):
        with patch.object(camera, "probe_camera", side_effect=[RuntimeError(), candidate(1), cv2.error(), OSError(), candidate(4)]) as probe:
            self.assertEqual([c.index for c in camera.discover_cameras(self.config)], [1, 4])
            self.assertEqual([c.args[1] for c in probe.call_args_list], list(range(5)))

    def test_windows_backend_policy_and_fallback_same_index(self):
        with patch.object(camera.platform, "system", return_value="Windows"):
            self.assertEqual(camera.backend_candidates("auto"), [("dshow", cv2.CAP_DSHOW), ("msmf", cv2.CAP_MSMF), ("auto", cv2.CAP_ANY)])
            factory = CaptureFactory((2,))
            original_read = FakeCapture.read
            def read(capture):
                return (False, None) if len(factory.captures) == 1 else original_read(capture)
            with patch.object(camera.cv2, "VideoCapture", side_effect=factory), patch.object(FakeCapture, "read", read):
                self.assertEqual(camera.probe_camera(self.config, 2).index, 2)
            self.assertEqual(factory.opened, [(2, cv2.CAP_DSHOW), (2, cv2.CAP_MSMF)])
            factory.assert_released(self)

    def test_fixed_failure_never_falls_back_to_other_index(self):
        factory = CaptureFactory((0,))
        self.captures(factory)
        with patch.object(camera, "discover_cameras") as scan:
            with self.assertRaisesRegex(RuntimeError, "camera_index=2"):
                with camera.camera_session(camera.resolve_camera_config(self.config, 2)):
                    self.fail("No debería abrir")
            scan.assert_not_called()
        self.assertEqual([i for i, api in factory.opened], [2])
        factory.assert_released(self)

    def test_open_requires_resolved_index(self):
        with patch.object(camera.cv2, "VideoCapture") as capture, self.assertRaisesRegex(ValueError, "resolve_camera_config"):
            camera.open_camera(self.config)
        capture.assert_not_called()

    def test_shared_cli_valid_and_invalid(self):
        self.assertIsNone(parse_camera_args("test", []).camera)
        self.assertEqual(parse_camera_args("test", ["--camera", "0"]).camera, 0)
        for value in ("-1", "hola", "auto", "1.5", "2147483648"):
            with self.subTest(value=value), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    parse_camera_args("test", ["--camera", value])
                self.assertEqual(error.exception.code, 2)

    def test_all_entrypoints_forward_override_and_handle_cancellation(self):
        for module, run in ((main, "run_preview"), (detect, "run_detection"), (track, "run_tracking")):
            with self.subTest(module=module.__name__), patch.dict("os.environ", {"DISPLAY": ":test"}), \
                    patch.object(module, "load_config", return_value={**self.config, "camera_index": 0}), \
                    patch.object(module, run) as runner:
                self.assertEqual(module.main(["--camera", "1"]), 0)
                self.assertEqual(runner.call_args.args[-1], 1)
                runner.side_effect = CameraSelectionCancelled()
                self.assertEqual(module.main(["--camera", "1"]), 0)
                runner.side_effect = RuntimeError("No se detectaron cámaras disponibles")
                self.assertEqual(module.main(["--camera", "1"]), 1)

    def test_help_and_imports_do_not_load_cv2_or_ai(self):
        for module in ("main", "detect", "track"):
            code = (f"import sys; from src import {module} as app; "
                    "assert not any(m in sys.modules for m in ('cv2','torch','ultralytics')); "
                    "app.main(['--help'])")
            process = subprocess.run([sys.executable, "-c", code], cwd=PROJECT_ROOT, text=True, capture_output=True, timeout=15)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn("--camera N", process.stdout)

    def test_diagnostics_reuses_scan_without_selector(self):
        with patch.object(sys, "argv", ["diagnostics", "--scan"]), \
                patch.object(diagnostics, "report_detection", return_value=True), \
                patch.object(diagnostics, "report_tracking", return_value=True), \
                patch.object(camera, "discover_cameras", return_value=[candidate(0), candidate(2)]) as scan, \
                patch.object(camera, "select_camera") as selector:
            self.assertEqual(diagnostics.main(), 0)
            scan.assert_called_once()
            selector.assert_not_called()
        self.assertIn("[0, 2]", self.output.getvalue())

    def test_diagnostics_without_scan_does_not_open_camera(self):
        with patch.object(sys, "argv", ["diagnostics"]), \
                patch.object(diagnostics, "report_detection", return_value=True), \
                patch.object(diagnostics, "report_tracking", return_value=True), \
                patch.object(camera, "discover_cameras") as scan, patch.object(camera.cv2, "VideoCapture") as capture:
            self.assertEqual(diagnostics.main(), 0)
            scan.assert_not_called()
            capture.assert_not_called()

    def run_pipeline(self, module, ui, config, override=None):
        if module is main_seleccionar_camera:
            main_seleccionar_camera.run_preview(ui, config)
        elif module is detect:
            detect.run_detection(ui, config, load_detection_config(), override)
        else:
            track.run_tracking(ui, config, load_detection_config(), load_tracking_config(), override)

    def fake_models(self):
        detector = self.enterContext(patch.object(detect, "PersonDetector"))
        detector.return_value.detect.return_value = FrameDetections((), 10, 15)
        tracker = self.enterContext(patch.object(track, "PersonTracker"))
        tracker.return_value.track.return_value = FrameTracks((), (), 10, 15)
        tracker.return_value.bytetrack_config = {"track_buffer": 30}
        return detector, tracker

    def test_all_pipelines_scan_once_before_three_frames(self):
        detector, tracker = self.fake_models()
        self.interactive()
        for module in (main_seleccionar_camera, detect, track):
            with self.subTest(module=module.__name__):
                factory = CaptureFactory()
                ui = MagicMock(error=cv2.error)
                ui.waitKey.side_effect = [-1, -1, ord("q")]
                ui.getWindowProperty.return_value = 1
                def choose(prompt):
                    factory.assert_released(self)
                    return "2"
                with patch.object(camera.cv2, "VideoCapture", side_effect=factory), \
                        patch.object(camera, "backend_candidates", return_value=[("fake", 123)]), \
                        patch("builtins.input", side_effect=choose) as prompt, \
                        patch.object(camera, "discover_cameras", wraps=camera.discover_cameras) as scan:
                    self.run_pipeline(module, ui, self.config)
                scan.assert_called_once()
                prompt.assert_called_once()
                self.assertEqual([i for i, api in factory.opened], [0, 1, 2, 3, 4, 2])
                factory.assert_released(self)
                self.assertEqual(ui.imshow.call_count, 3)
                self.assertTrue(any("cam: 2" in call.args[1] for call in ui.putText.call_args_list))
                ui.destroyAllWindows.assert_called_once()
                if module is main_seleccionar_camera:
                    detector.assert_not_called()
                    tracker.assert_not_called()
                elif module is detect:
                    detector.return_value.detect.assert_called()
                    self.assertEqual(detector.return_value.detect.call_count, 3)
                    tracker.assert_not_called()
                else:
                    self.assertEqual(tracker.return_value.track.call_count, 3)

    def test_all_pipelines_cancel_before_models_or_windows(self):
        detector, tracker = self.fake_models()
        self.interactive()
        for module in (main_seleccionar_camera, detect, track):
            ui = MagicMock(error=cv2.error)
            with self.subTest(module=module.__name__), \
                    patch.object(camera, "discover_cameras", return_value=[candidate(0), candidate(2)]), \
                    patch("builtins.input", return_value="q"), patch.object(camera, "open_camera") as opened:
                with self.assertRaises(CameraSelectionCancelled):
                    self.run_pipeline(module, ui, self.config)
                opened.assert_not_called()
                ui.namedWindow.assert_not_called()
                if module is main_seleccionar_camera:
                    ui.destroyAllWindows.assert_not_called()  # Canceló antes del preview compartido.
                else:
                    ui.destroyAllWindows.assert_called_once()
        detector.assert_not_called()
        tracker.assert_not_called()

    def test_selected_camera_disappearing_is_error_without_rescan(self):
        factory = CaptureFactory(())
        self.captures(factory)
        detector, tracker = self.fake_models()
        with patch.object(camera, "discover_cameras", return_value=[candidate(2)]) as scan:
            with self.assertRaisesRegex(RuntimeError, "camera_index=2"):
                self.run_pipeline(track, MagicMock(error=cv2.error), self.config)
            scan.assert_called_once()
        self.assertEqual([i for i, api in factory.opened], [2])
        detector.assert_not_called()
        tracker.assert_not_called()
        factory.assert_released(self)


if __name__ == "__main__":
    unittest.main()
