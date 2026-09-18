"""Pruebas sin webcam: errores y propiedad de recursos con unittest.mock."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
from src import camera, main
from src.config import load_config


class ConfigTests(unittest.TestCase):
    def test_load_from_other_directory(self):
        original = Path.cwd()
        expected = load_config()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                self.assertEqual(load_config(), expected)
            finally:
                os.chdir(original)

    def test_invalid_values(self):
        changes = [("camera_index", True), ("camera_index", -1), ("width", 0),
                   ("height", "720"), ("fps", 0), ("fps", float("nan")),
                   ("fps", float("inf")), ("backend", "unknown")]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "camera.json"
            for key, value in changes:
                with self.subTest(key=key, value=value):
                    path.write_text(json.dumps({**load_config(), key: value}))
                    with self.assertRaisesRegex(ValueError, key):
                        load_config(path)

    def test_missing_malformed_and_incomplete(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "camera.json"
            with self.assertRaisesRegex(ValueError, "camera.json"):
                load_config(path)
            for text in ("{", "[]", "{}", '{"extra":1}'):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    load_config(path)


class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()
        self.frame = MagicMock(size=10, shape=(720, 1280, 3))
        self.capture = MagicMock()
        self.capture.read.return_value = (True, self.frame)
        self.capture.getBackendName.return_value = "MOCK"
        self.capture.get.return_value = 30

    def run_session(self, failure):
        with patch.object(camera.cv2, "VideoCapture", return_value=self.capture):
            with self.assertRaises(type(failure)):
                with camera.camera_session(self.config):
                    raise failure
        self.capture.release.assert_called_once()

    def test_consumer_failure_releases(self):
        self.run_session(RuntimeError("consumer"))

    def test_ctrl_c_releases(self):
        self.run_session(KeyboardInterrupt())

    def test_failed_open_releases_each_attempt(self):
        self.capture.open.return_value = False
        with patch.object(camera.cv2, "VideoCapture", return_value=self.capture):
            with self.assertRaisesRegex(RuntimeError, f"camera_index={self.config['camera_index']}"):
                camera.open_camera(self.config)
        self.assertEqual(self.capture.release.call_count, len(camera.backend_candidates("auto")))

    def test_unreadable_first_frame_falls_back(self):
        failed = MagicMock()
        failed.read.return_value = (False, None)
        with patch.object(camera, "backend_candidates", return_value=[("first", 1), ("second", 2)]), \
             patch.object(camera.cv2, "VideoCapture", side_effect=[failed, self.capture]):
            with camera.camera_session(self.config):
                failed.release.assert_called_once()
        self.capture.release.assert_called_once()

    def test_open_exception_releases(self):
        self.capture.open.side_effect = cv2.error("open failure")
        with patch.object(camera, "backend_candidates", return_value=[("mock", 1)]), \
             patch.object(camera.cv2, "VideoCapture", return_value=self.capture):
            with self.assertRaises(RuntimeError):
                camera.open_camera(self.config)
        self.capture.release.assert_called_once()

    def run_preview(self, key=ord("q"), read_failure=False, ui_failure=False, closed=False):
        fake_ui = MagicMock()
        fake_ui.error = cv2.error
        fake_ui.waitKey.return_value = key
        fake_ui.getWindowProperty.return_value = 0 if closed else 1
        if read_failure:
            self.capture.read.side_effect = [(True, self.frame), (False, None)]
        if ui_failure:
            fake_ui.imshow.side_effect = cv2.error("UI failure")
        with patch.object(camera.cv2, "VideoCapture", return_value=self.capture):
            if read_failure or ui_failure:
                with self.assertRaises((RuntimeError, cv2.error)):
                    main.run_preview(fake_ui, self.config)
            else:
                main.run_preview(fake_ui, self.config)
        self.capture.release.assert_called_once()
        fake_ui.destroyAllWindows.assert_called_once()

    def test_q(self):
        self.run_preview()

    def test_escape(self):
        self.run_preview(key=27)

    def test_window_close(self):
        self.run_preview(key=-1, closed=True)

    def test_later_read_failure(self):
        self.run_preview(key=-1, read_failure=True)

    def test_ui_failure(self):
        self.run_preview(ui_failure=True)

    def test_failed_open_still_cleans_windows(self):
        fake_ui = MagicMock()
        fake_ui.error = cv2.error
        self.capture.open.return_value = False
        with patch.object(camera.cv2, "VideoCapture", return_value=self.capture):
            with self.assertRaises(RuntimeError):
                main.run_preview(fake_ui, self.config)
        fake_ui.destroyAllWindows.assert_called_once()
        self.assertEqual(self.capture.release.call_count, len(camera.backend_candidates("auto")))

    def test_windows_auto_order(self):
        with patch.object(camera.platform, "system", return_value="Windows"):
            self.assertEqual([name for name, _ in camera.backend_candidates("auto")],
                             ["dshow", "msmf", "auto"])

    def test_wrong_platform_backend(self):
        with patch.object(camera.platform, "system", return_value="Linux"):
            with self.assertRaisesRegex(ValueError, "auto"):
                camera.backend_candidates("dshow")


if __name__ == "__main__":
    unittest.main()
