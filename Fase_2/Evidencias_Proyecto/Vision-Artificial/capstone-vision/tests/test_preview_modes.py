"""Previews automático/forzado/selector con dobles explícitos de OpenCV.

Verifica lógica Python y liberación de recursos simulados, no drivers ni IA reales.
"""

import contextlib
import importlib
import io
import subprocess
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from src import main, main_seleccionar_camera as selector
from src.config import CONFIG_PATH, PROJECT_ROOT, load_config


class PreviewModesTests(unittest.TestCase):
    def setUp(self):
        self.config = {**load_config(), "camera_index": 2}
        self.before_json = CONFIG_PATH.read_bytes()
        self.available = {2}
        self.captures = []
        self.indices = []
        self.frame = MagicMock(size=100, shape=(480, 640, 3))
        self.cv2 = types.ModuleType("cv2")
        self.cv2.error = type("SimulatedOpenCVError", (Exception,), {})
        for i, name in enumerate(("CAP_DSHOW", "CAP_MSMF", "CAP_V4L2", "CAP_AVFOUNDATION", "CAP_ANY",
                                  "CAP_PROP_FRAME_WIDTH", "CAP_PROP_FRAME_HEIGHT", "CAP_PROP_FPS",
                                  "WINDOW_NORMAL", "FONT_HERSHEY_SIMPLEX", "LINE_AA", "WND_PROP_VISIBLE")):
            setattr(self.cv2, name, i)
        for name in ("namedWindow", "putText", "imshow", "waitKey", "getWindowProperty", "destroyAllWindows"):
            setattr(self.cv2, name, MagicMock())
        self.cv2.waitKey.return_value = ord("q")
        self.cv2.getWindowProperty.return_value = 1
        self.cv2.VideoCapture = MagicMock(side_effect=self.capture_factory)
        self.enterContext(patch.dict(sys.modules, {"cv2": self.cv2}))
        self.camera = importlib.import_module("src.camera")
        self.enterContext(patch.object(self.camera, "cv2", self.cv2))
        self.enterContext(patch.object(self.camera, "backend_candidates", return_value=[("simulated", 123)]))
        self.enterContext(patch.dict("os.environ", {"DISPLAY": ":test"}))
        self.enterContext(patch.object(main, "load_config", return_value=self.config))
        self.enterContext(patch.object(selector, "load_config", return_value=self.config))
        self.output = self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def tearDown(self):
        self.assertEqual(CONFIG_PATH.read_bytes(), self.before_json)

    def capture_factory(self):
        capture = MagicMock()
        def open_capture(index, api):
            for previous in self.captures[:-1]:
                previous.release.assert_called_once()
            self.indices.append(index)
            return index in self.available
        capture.open.side_effect = open_capture
        capture.read.return_value = (True, self.frame)
        capture.get.return_value = 30.0
        capture.getBackendName.return_value = "SIMULATED"
        self.captures.append(capture)
        return capture

    def released(self):
        self.assertTrue(self.captures)
        for capture in self.captures:
            capture.release.assert_called_once()

    def interactive(self):
        self.enterContext(patch.object(self.camera.sys, "stdin", MagicMock(isatty=lambda: True)))

    def test_both_import_without_opencv_or_ai(self):
        code = ("import sys; import src.main, src.main_seleccionar_camera; "
                "assert all(n not in sys.modules for n in "
                "('cv2','torch','ultralytics','src.detector','src.tracker')); print('OK')")
        result = subprocess.run([sys.executable, "-c", code], cwd=PROJECT_ROOT,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_auto_first_integer_json_never_uses_full_discovery_or_prompts(self):
        with patch.object(self.camera, "resolve_camera_config") as resolver, \
                patch.object(self.camera, "discover_cameras") as scan, \
                patch.object(self.camera, "select_camera") as choose, patch("builtins.input") as prompt:
            self.assertEqual(main.main([]), 0)
            resolver.assert_not_called()
            scan.assert_not_called()
            choose.assert_not_called()
            prompt.assert_not_called()
        self.assertEqual(self.indices, [0, 1, 2, 2])
        self.assertNotIn("Cámaras disponibles", self.output.getvalue())
        self.assertNotIn("Seleccione cámara", self.output.getvalue())
        self.released()
        self.cv2.destroyAllWindows.assert_called_once()

    def test_auto_first_stops_at_zero_with_integer_json(self):
        self.config["camera_index"] = 0
        self.available = {0, 2}
        with patch.object(self.camera, "discover_cameras") as scan, patch("builtins.input") as prompt:
            self.assertEqual(main.main([]), 0)
            scan.assert_not_called()
            prompt.assert_not_called()
        self.assertEqual(self.indices, [0, 0])
        self.released()

    def test_direct_cli_override_auto_without_mutation(self):
        self.config["camera_index"] = "auto"
        with patch.object(self.camera, "resolve_camera_config") as resolver, patch("builtins.input") as prompt:
            self.assertEqual(main.main(["--camera", "2"]), 0)
            resolver.assert_not_called()
            prompt.assert_not_called()
        self.assertEqual(self.indices, [2])
        self.assertEqual(self.config["camera_index"], "auto")
        self.released()

    def test_auto_first_no_cameras_controlled_before_window(self):
        self.config["camera_index"] = "auto"
        self.available = set()
        with patch.object(self.camera, "discover_cameras") as scan, patch("builtins.input") as prompt, \
                self.assertLogs(main.LOGGER, level="ERROR") as logs:
            self.assertEqual(main.main([]), 1)
            scan.assert_not_called()
            prompt.assert_not_called()
        self.assertIn("python -m src.diagnostics --scan", " ".join(logs.output))
        self.assertIn("No se detectó ninguna cámara funcional", " ".join(logs.output))
        self.assertEqual(self.indices, list(range(5)))
        self.released()
        self.cv2.namedWindow.assert_not_called()

    def test_shared_preview_also_rejects_auto_without_discovery(self):
        with patch.object(self.camera, "resolve_camera_config") as resolver, patch("builtins.input") as prompt:
            with self.assertRaisesRegex(ValueError, "índice resuelto"):
                main.run_preview(self.cv2, {**self.config, "camera_index": "auto"})
            resolver.assert_not_called()
            prompt.assert_not_called()
        self.cv2.VideoCapture.assert_not_called()
        self.cv2.destroyAllWindows.assert_called_once()

    def test_direct_rejects_invalid_programmatic_indices(self):
        for value in (True, False, -1, 1.5, "0", "AUTO", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                main.direct_camera_config({**self.config, "camera_index": value})
        self.cv2.VideoCapture.assert_not_called()

    def test_direct_failed_index_never_opens_another(self):
        self.available = {0}
        with patch.object(self.camera, "discover_cameras") as scan:
            self.assertEqual(main.main(["--camera", "2"]), 1)
            scan.assert_not_called()
        self.assertEqual(self.indices, [2])
        self.released()
        self.cv2.destroyAllWindows.assert_called_once()

    def test_selector_reuses_resolver_and_same_preview_even_with_fixed_json(self):
        resolved = {**self.config, "camera_index": 4}
        with patch.object(self.camera, "resolve_camera_config", return_value=resolved) as resolver, \
                patch.object(main, "run_preview") as preview:
            self.assertEqual(selector.main([]), 0)
            resolver.assert_called_once_with({**self.config, "camera_index": "auto"})
            preview.assert_called_once_with(self.cv2, resolved)
        self.assertEqual(self.config["camera_index"], 2)

    def test_selector_zero_cameras_controlled_and_all_probes_released(self):
        self.available = set()
        with patch("builtins.input") as prompt, self.assertLogs(selector.LOGGER, level="ERROR") as logs:
            self.assertEqual(selector.main([]), 1)
            prompt.assert_not_called()
        self.assertIn("No se detectaron cámaras", " ".join(logs.output))
        self.assertEqual(self.indices, list(range(5)))
        self.cv2.namedWindow.assert_not_called()
        self.released()

    def test_selector_single_automatic_preview_uses_discovered_index(self):
        self.available = {4}  # JSON fija 2; comando selector debe descubrir 4.
        with patch("builtins.input") as prompt:
            self.assertEqual(selector.main([]), 0)
            prompt.assert_not_called()
        self.assertEqual(self.indices, [0, 1, 2, 3, 4, 4])
        self.assertIn("automáticamente cámara 4", self.output.getvalue())
        self.assertTrue(any("cam: 4" in call.args[1] for call in self.cv2.putText.call_args_list))
        self.released()
        self.cv2.destroyAllWindows.assert_called_once()

    def test_selector_multiple_invalid_retry_no_rescan(self):
        self.available = {0, 2}
        self.interactive()
        answers = iter(("99", "hola", "1", "2"))
        def choose(prompt):
            self.released()  # Ningún sondeo permanece abierto al solicitar input.
            return next(answers)
        with patch("builtins.input", side_effect=choose) as prompt, \
                patch.object(self.camera, "discover_cameras", wraps=self.camera.discover_cameras) as scan:
            self.assertEqual(selector.main([]), 0)
            scan.assert_called_once()
            self.assertEqual(prompt.call_count, 4)
        self.assertEqual(self.indices, [0, 1, 2, 3, 4, 2])
        self.assertEqual(self.output.getvalue().count("Selección inválida"), 3)
        self.released()

    def test_selector_q_cancellation_and_ctrl_c_before_preview(self):
        self.available = {0, 2}
        self.interactive()
        for value in ("q", KeyboardInterrupt()):
            self.captures.clear()
            with self.subTest(value=repr(value)), patch("builtins.input", side_effect=[value]):
                self.assertEqual(selector.main([]), 0)
                self.released()
        self.cv2.namedWindow.assert_not_called()

    def test_selector_eof_and_missing_stdin_controlled(self):
        self.available = {0, 2}
        with patch.object(self.camera.sys, "stdin", None), patch("builtins.input") as prompt:
            self.assertEqual(selector.main([]), 1)
            prompt.assert_not_called()
            self.released()
        self.captures.clear()
        self.interactive()
        with patch("builtins.input", side_effect=EOFError()):
            self.assertEqual(selector.main([]), 1)
            self.released()
        self.cv2.namedWindow.assert_not_called()

    def test_both_modes_q_escape_and_window_close_release(self):
        for module in (main, selector):
            for key, visible in ((ord("q"), 1), (27, 1), (-1, 0)):
                with self.subTest(module=module.__name__, key=key):
                    self.captures.clear()
                    self.cv2.destroyAllWindows.reset_mock()
                    self.cv2.waitKey.return_value = key
                    self.cv2.getWindowProperty.return_value = visible
                    self.assertEqual(module.main([]), 0)
                    self.released()
                    self.cv2.destroyAllWindows.assert_called_once()

    def test_both_modes_ctrl_c_and_ui_error_release(self):
        for module in (main, selector):
            for error, expected in ((KeyboardInterrupt(), 0), (self.cv2.error("GUI"), 1)):
                with self.subTest(module=module.__name__, error=type(error)):
                    self.captures.clear()
                    self.cv2.destroyAllWindows.reset_mock()
                    self.cv2.imshow.side_effect = error
                    self.assertEqual(module.main([]), expected)
                    self.released()
                    self.cv2.destroyAllWindows.assert_called_once()

    def test_selector_interrupt_during_probe_releases(self):
        capture = MagicMock()
        capture.read.side_effect = KeyboardInterrupt()
        self.cv2.VideoCapture.side_effect = None
        self.cv2.VideoCapture.return_value = capture
        self.assertEqual(selector.main([]), 0)
        capture.release.assert_called_once()
        self.cv2.namedWindow.assert_not_called()

    def test_selector_selected_camera_disappears_without_new_scan(self):
        found = self.camera.CameraCandidate(4, 640, 480, 30, "SIMULATED")
        with patch.object(self.camera, "discover_cameras", return_value=[found]) as scan:
            self.assertEqual(selector.main([]), 1)
            scan.assert_called_once()
        self.assertEqual(self.indices, [4])
        self.released()
        self.cv2.destroyAllWindows.assert_called_once()

    def test_help_works_without_dependencies(self):
        for module in ("src.main", "src.main_seleccionar_camera"):
            result = subprocess.run([sys.executable, "-m", module, "--help"], cwd=PROJECT_ROOT,
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("preview", result.stdout.lower())

    def test_find_first_returns_zero_without_probing_later_indices(self):
        self.available = {0, 1, 2}
        with patch("builtins.input") as prompt:
            found = self.camera.find_first_available_camera(self.config)
            prompt.assert_not_called()
        self.assertEqual(found.index, 0)
        self.assertEqual(self.indices, [0])
        self.released()

    def test_find_first_skips_failed_zero_returns_one_and_stops(self):
        self.available = {1, 3}
        found = self.camera.find_first_available_camera(self.config)
        self.assertEqual(found.index, 1)
        self.assertEqual(self.indices, [0, 1])
        self.released()

    def test_find_first_uses_same_candidate_range_as_discovery(self):
        self.available = {4}
        with patch.object(self.camera, "SCAN_INDICES", (2, 4)):
            found = self.camera.find_first_available_camera(self.config)
        self.assertEqual(found.index, 4)
        self.assertEqual(self.indices, [2, 4])
        self.released()

    def test_auto_first_auto_json_multiple_cameras_no_stdin_needed(self):
        self.config["camera_index"] = "auto"
        self.available = {0, 1}
        with patch.object(self.camera.sys, "stdin", None), patch("builtins.input") as prompt, \
                patch.object(self.camera, "discover_cameras") as scan, \
                patch.object(self.camera, "select_camera") as choose:
            self.assertEqual(main.main([]), 0)
            prompt.assert_not_called()
            scan.assert_not_called()
            choose.assert_not_called()
        self.assertEqual(self.indices, [0, 0])  # Probe liberado y sesión definitiva.
        self.assertNotIn("Cámaras disponibles", self.output.getvalue())
        self.assertNotIn("Seleccione cámara", self.output.getvalue())
        self.assertEqual(self.config["camera_index"], "auto")
        self.released()

    def test_auto_first_opens_one_when_zero_fails(self):
        self.config["camera_index"] = "auto"
        self.available = {1, 3}
        self.assertEqual(main.main([]), 0)
        self.assertEqual(self.indices, [0, 1, 1])
        self.assertTrue(any("cam: 1" in call.args[1] for call in self.cv2.putText.call_args_list))
        self.released()

    def test_auto_first_ignores_legacy_fixed_index_without_cli(self):
        self.config["camera_index"] = 4
        self.available = {0, 4}
        self.assertEqual(main.main([]), 0)
        self.assertEqual(self.indices, [0, 0])
        self.assertEqual(self.config["camera_index"], 4)
        self.released()

    def test_forced_zero_or_one_bypasses_every_search(self):
        self.available = {0, 1}
        self.config["camera_index"] = "auto"
        for index in (0, 1):
            self.indices.clear()
            self.captures.clear()
            with self.subTest(index=index), \
                    patch.object(self.camera, "find_first_available_camera") as first, \
                    patch.object(self.camera, "discover_cameras") as scan, \
                    patch.object(self.camera, "probe_camera") as probe, patch("builtins.input") as prompt:
                self.assertEqual(main.main(["--camera", str(index)]), 0)
                first.assert_not_called()
                scan.assert_not_called()
                probe.assert_not_called()
                prompt.assert_not_called()
            self.assertEqual(self.indices, [index])
            self.released()

    def test_forced_99_failure_does_not_fall_back_to_available_zero(self):
        self.available = {0}
        with patch.object(self.camera, "find_first_available_camera") as first, \
                patch.object(self.camera, "discover_cameras") as scan, \
                patch.object(self.camera, "probe_camera") as probe, \
                self.assertLogs(main.LOGGER, level="ERROR") as logs:
            self.assertEqual(main.main(["--camera", "99"]), 1)
            first.assert_not_called()
            scan.assert_not_called()
            probe.assert_not_called()
        self.assertIn("camera_index=99", " ".join(logs.output))
        self.assertEqual(self.indices, [99])
        self.released()
        self.cv2.destroyAllWindows.assert_called_once()

    def test_auto_first_skips_open_camera_without_valid_frame(self):
        self.available = {0, 1}
        def factory():
            capture = self.capture_factory()
            capture.read.side_effect = lambda: (False, None) if self.indices[-1] == 0 else (True, self.frame)
            return capture
        self.cv2.VideoCapture.side_effect = factory
        self.assertEqual(main.main([]), 0)
        self.assertEqual(self.indices, [0, 1, 1])
        self.released()

    def test_auto_first_ctrl_c_during_probe_releases(self):
        capture = MagicMock()
        capture.read.side_effect = KeyboardInterrupt()
        self.cv2.VideoCapture.side_effect = None
        self.cv2.VideoCapture.return_value = capture
        self.assertEqual(main.main([]), 0)
        capture.release.assert_called_once()
        self.cv2.namedWindow.assert_not_called()

    def test_auto_first_reopen_failure_does_not_restart_search(self):
        self.available = {0}
        found = self.camera.CameraCandidate(2, 640, 480, 30, "SIMULATED")
        with patch.object(self.camera, "find_first_available_camera", return_value=found) as first:
            self.assertEqual(main.main([]), 1)
            first.assert_called_once()
        self.assertEqual(self.indices, [2])
        self.released()
        self.cv2.destroyAllWindows.assert_called_once()

    def test_auto_first_search_occurs_once_before_three_preview_frames(self):
        self.available = {0, 1}
        self.cv2.waitKey.side_effect = [-1, -1, ord("q")]
        with patch.object(self.camera, "find_first_available_camera",
                          wraps=self.camera.find_first_available_camera) as first:
            self.assertEqual(main.main([]), 0)
            first.assert_called_once()
        self.assertEqual(self.indices, [0, 0])
        self.assertEqual(self.cv2.imshow.call_count, 3)
        self.released()



if __name__ == "__main__":
    unittest.main()
