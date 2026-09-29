"""Selector sin cámara física; toda escritura utiliza un directorio temporal."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import cv2

from src import camera
from src import camera_selector as selector
from src.config import PROJECT_ROOT, load_config


CONFIG = {"camera_index": 3, "width": 960, "height": 540,
          "fps": 59.94, "backend": "auto"}
AVAILABLE = [selector.AvailableCamera(1, 640, 480, "MSMF", 30.0)]


def capture_mock(*, opened=True, frame_ok=True, empty=False):
    capture = Mock()
    capture.open.return_value = opened
    capture.isOpened.return_value = opened
    capture.set.return_value = True
    frame = SimpleNamespace(shape=(480, 640, 3), size=0 if empty else 480 * 640 * 3)
    capture.read.return_value = (frame_ok, frame if frame_ok else None)
    capture.getBackendName.return_value = "MSMF"
    capture.get.side_effect = {
        cv2.CAP_PROP_FRAME_WIDTH: 960.0,
        cv2.CAP_PROP_FRAME_HEIGHT: 540.0,
        cv2.CAP_PROP_FPS: 30.0,
    }.__getitem__
    return capture


class ScanTests(unittest.TestCase):
    def test_import_is_light_and_does_not_open_cameras(self):
        script = """
import builtins
original = builtins.__import__
blocked = {'cv2', 'torch', 'torchvision', 'ultralytics', 'lap'}
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in blocked:
        raise AssertionError('Importación inesperada: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
import src.camera_selector
"""
        result = subprocess.run([sys.executable, "-c", script], cwd=PROJECT_ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_scan_requires_frames_releases_all_and_preserves_settings(self):
        captures = [capture_mock(opened=False), capture_mock(),
                    capture_mock(frame_ok=False), capture_mock(empty=True), capture_mock()]
        original = CONFIG.copy()
        with patch.object(camera, "backend_candidates", return_value=[("mock", 123)]), \
                patch.object(camera.cv2, "VideoCapture", side_effect=captures):
            found = selector.scan_cameras(CONFIG)
        self.assertEqual([item.index for item in found], [1, 4])
        self.assertEqual(found[0], AVAILABLE[0])  # Tamaño del frame, no propiedad solicitada.
        self.assertEqual(CONFIG, original)
        for index, capture in enumerate(captures):
            capture.open.assert_called_once_with(index, 123)
            capture.release.assert_called_once_with()
        captures[1].set.assert_has_calls([
            call(cv2.CAP_PROP_FRAME_WIDTH, 960), call(cv2.CAP_PROP_FRAME_HEIGHT, 540),
            call(cv2.CAP_PROP_FPS, 59.94),
        ])

    def test_previous_capture_is_released_before_next_index(self):
        captures = []

        def create():
            if captures:
                captures[-1].release.assert_called_once_with()
            capture = capture_mock()
            captures.append(capture)
            return capture

        with patch.object(camera, "backend_candidates", return_value=[("mock", 123)]), \
                patch.object(camera.cv2, "VideoCapture", side_effect=create):
            self.assertEqual(len(selector.scan_cameras(CONFIG)), 5)
        captures[-1].release.assert_called_once_with()

    def test_opencv_open_error_does_not_abort_scan(self):
        captures = [capture_mock() for _ in range(5)]
        captures[0].open.side_effect = cv2.error("fallo simulado")
        with patch.object(camera, "backend_candidates", return_value=[("mock", 123)]), \
                patch.object(camera.cv2, "VideoCapture", side_effect=captures):
            self.assertEqual([c.index for c in selector.scan_cameras(CONFIG)], [1, 2, 3, 4])
        for capture in captures:
            capture.release.assert_called_once_with()

    def test_info_error_releases_and_continues(self):
        captures = [capture_mock() for _ in range(5)]
        captures[0].get.side_effect = cv2.error("propiedad no disponible")
        with patch.object(camera, "backend_candidates", return_value=[("mock", 123)]), \
                patch.object(camera.cv2, "VideoCapture", side_effect=captures):
            self.assertEqual([c.index for c in selector.scan_cameras(CONFIG)], [1, 2, 3, 4])
        for capture in captures:
            capture.release.assert_called_once_with()

    def test_ctrl_c_releases_current_capture(self):
        capture = capture_mock()
        capture.get.side_effect = KeyboardInterrupt
        with patch.object(camera, "backend_candidates", return_value=[("mock", 123)]), \
                patch.object(camera.cv2, "VideoCapture", return_value=capture) as factory:
            with self.assertRaises(KeyboardInterrupt):
                selector.scan_cameras(CONFIG)
        factory.assert_called_once_with()
        capture.release.assert_called_once_with()


class SelectionTests(unittest.TestCase):
    def test_valid_choice(self):
        with patch("builtins.input", return_value=" 1 "):
            self.assertEqual(selector.choose_camera(AVAILABLE), 1)

    def test_invalid_choices_retry(self):
        with patch("builtins.input", side_effect=["texto", "-1", "5", "0", "1.0", "", "1"]) as ask, \
                redirect_stdout(io.StringIO()):
            self.assertEqual(selector.choose_camera(AVAILABLE), 1)
        self.assertEqual(ask.call_count, 7)

    def test_cancel(self):
        with patch("builtins.input", return_value=" Q "):
            self.assertIsNone(selector.choose_camera(AVAILABLE))

    def test_no_choices_does_not_prompt(self):
        with patch("builtins.input") as ask, self.assertRaises(ValueError):
            selector.choose_camera([])
        ask.assert_not_called()


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "camera.json"
        self.path.write_text(json.dumps({**CONFIG, "backend": "msmf"}, indent=4),
                             encoding="utf-8-sig")
        self.original = self.path.read_bytes()

    def assert_no_temporaries(self):
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_changes_only_index_and_reloads_valid_utf8_json(self):
        before = load_config(self.path)
        with patch.object(selector, "load_config", wraps=load_config) as load:
            saved = selector.save_camera_index(1, self.path)
        self.assertEqual(saved, {**before, "camera_index": 1})
        self.assertEqual(load_config(self.path), saved)
        self.assertEqual(load.call_args_list[0], call(self.path))
        self.assertEqual(load.call_args_list[-1], call(self.path))
        self.assertEqual(load.call_count, 3)  # Original, temporal, archivo reemplazado.
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), saved)
        self.assertIn('\n  "camera_index": 1,\n', self.path.read_text(encoding="utf-8"))
        self.assert_no_temporaries()

    def test_temporary_is_in_same_directory_and_valid_before_replace(self):
        real_replace = os.replace

        def replace(source, target):
            self.assertEqual(source.parent, self.path.parent)
            self.assertEqual(target, self.path)
            self.assertEqual(self.path.read_bytes(), self.original)
            self.assertEqual(load_config(source)["camera_index"], 1)
            real_replace(source, target)

        with patch.object(selector.os, "replace", side_effect=replace) as replace_mock:
            selector.save_camera_index(1, self.path)
        replace_mock.assert_called_once()
        self.assert_no_temporaries()

    def test_invalid_index_never_changes_file(self):
        for value in (-1, True, 1.5, "1", 2**31):
            with self.subTest(value=value), self.assertRaises(ValueError):
                selector.save_camera_index(value, self.path)
            self.assertEqual(self.path.read_bytes(), self.original)
            self.assert_no_temporaries()

    def test_invalid_original_is_not_overwritten(self):
        self.path.write_text('{"camera_index":', encoding="utf-8")
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            selector.save_camera_index(1, self.path)
        self.assertEqual(self.path.read_bytes(), before)
        self.assert_no_temporaries()

    def test_partial_temporary_write_preserves_original(self):
        def partial_write(data, stream, **kwargs):
            stream.write('{"camera_index":')
            raise OSError("disco lleno")

        with patch.object(selector.json, "dump", side_effect=partial_write):
            with self.assertRaises(OSError):
                selector.save_camera_index(1, self.path)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assert_no_temporaries()

    def test_fsync_and_replace_failures_preserve_original(self):
        for operation in ("fsync", "replace"):
            with self.subTest(operation=operation), \
                    patch.object(selector.os, operation, side_effect=PermissionError("sin permiso")):
                with self.assertRaises(OSError):
                    selector.save_camera_index(1, self.path)
                self.assertEqual(self.path.read_bytes(), self.original)
                self.assert_no_temporaries()

    def test_invalid_temporary_is_not_installed(self):
        with patch.object(selector.json, "dump", side_effect=lambda data, stream, **kw: stream.write("{}")):
            with self.assertRaises(ValueError):
                selector.save_camera_index(1, self.path)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assert_no_temporaries()

    def test_save_reads_latest_settings(self):
        self.path.write_text(json.dumps({**CONFIG, "fps": 60, "width": 1280}), encoding="utf-8")
        selector.save_camera_index(1, self.path)
        self.assertEqual(load_config(self.path), {**CONFIG, "camera_index": 1, "fps": 60, "width": 1280})

    def test_main_persists_choice_for_another_process(self):
        with patch.object(selector, "scan_cameras", return_value=AVAILABLE), \
                patch("builtins.input", return_value="1"), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(selector.main(self.path), 0)
        self.assertIn("FPS informado: 30", output.getvalue())
        script = "from pathlib import Path; from src.config import load_config; import sys; print(load_config(Path(sys.argv[1]))['camera_index'])"
        result = subprocess.run([sys.executable, "-c", script, str(self.path)],
                                cwd=PROJECT_ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "1")
        self.assert_no_temporaries()

    def test_no_camera_does_not_ask_or_save(self):
        with patch.object(selector, "scan_cameras", return_value=[]), \
                patch("builtins.input") as ask, redirect_stdout(io.StringIO()) as output:
            self.assertEqual(selector.main(self.path), 1)
        ask.assert_not_called()
        self.assertIn("No se encontraron cámaras", output.getvalue())
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assert_no_temporaries()

    def test_invalid_input_and_cancel_do_not_write(self):
        with patch.object(selector, "scan_cameras", return_value=AVAILABLE), \
                patch("builtins.input", side_effect=["texto", "-1", "5", "0", "q"]), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(selector.main(self.path), 0)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assert_no_temporaries()

    def test_eof_and_ctrl_c_do_not_write(self):
        for error, status in ((EOFError, 1), (KeyboardInterrupt, 130)):
            with self.subTest(error=error), \
                    patch.object(selector, "scan_cameras", return_value=AVAILABLE), \
                    patch("builtins.input", side_effect=error), redirect_stdout(io.StringIO()):
                self.assertEqual(selector.main(self.path), status)
            self.assertEqual(self.path.read_bytes(), self.original)
            self.assert_no_temporaries()

    def test_save_failure_returns_error_without_traceback(self):
        with patch.object(selector, "scan_cameras", return_value=AVAILABLE), \
                patch("builtins.input", return_value="1"), \
                patch.object(selector.os, "replace", side_effect=PermissionError("sin permiso")), \
                redirect_stdout(io.StringIO()), self.assertLogs(selector.LOGGER, level="ERROR") as logs:
            self.assertEqual(selector.main(self.path), 1)
        self.assertIn("sin permiso", logs.output[0])
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assert_no_temporaries()

    def test_existing_entrypoints_read_saved_index_without_asking(self):
        from src import detect, main, track

        selector.save_camera_index(1, self.path)
        for module, runner in ((main, "run_preview"), (detect, "run_detection"), (track, "run_tracking")):
            with self.subTest(module=module.__name__), \
                    patch.object(module, "load_config", side_effect=lambda: load_config(self.path)), \
                    patch.object(module.sys, "platform", "win32"), \
                    patch.object(module, runner) as run, \
                    patch("builtins.input", side_effect=AssertionError("No debe preguntar")), \
                    patch.object(selector, "scan_cameras", side_effect=AssertionError("No debe escanear")):
                for _ in range(2):
                    self.assertEqual(module.main(), 0)
                    self.assertEqual(run.call_args.args[1]["camera_index"], 1)
        self.assertEqual(load_config(self.path)["camera_index"], 1)


if __name__ == "__main__":
    unittest.main()
