"""Hito 2 sin webcam, descargas ni carga real de PyTorch/YOLO."""

import dataclasses
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import cv2

from src import camera, detect, detector, diagnostics
from src.config import PROJECT_ROOT, load_config, load_detection_config
from src.detector import Detection, FrameDetections, PersonDetector


class DetectionConfigTests(unittest.TestCase):
    def test_valid_and_bom(self):
        expected = load_detection_config()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "detection.json"
            path.write_text(json.dumps(expected), encoding="utf-8-sig")
            self.assertEqual(load_detection_config(path), expected)

    def test_load_from_other_directory(self):
        original = Path.cwd()
        expected = load_detection_config()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                self.assertEqual(load_detection_config(), expected)
            finally:
                os.chdir(original)

    def test_invalid_fields(self):
        cases = {
            "model": ("", " ", 3, "other.pt", "https://example.com/model.pt"),
            "confidence_threshold": (-0.1, 1.1, True, "0.5", float("nan"), float("inf")),
            "iou_threshold": (-0.1, 1.1, False, "0.7", float("nan"), float("inf")),
            "image_size": (0, -1, True, 1.5, "640"),
            "device": ("", "cuda", "0", None, 0),
            "person_class_id": (-1, True, "0", 0.5),
            "show_confidence": (1, "true", None),
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "detection.json"
            for field, values in cases.items():
                for value in values:
                    with self.subTest(field=field, value=value):
                        path.write_text(json.dumps({**load_detection_config(), field: value}))
                        with self.assertRaisesRegex(ValueError, field):
                            load_detection_config(path)

    def test_threshold_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "detection.json"
            for value in (0, 1):
                path.write_text(json.dumps({**load_detection_config(),
                                            "confidence_threshold": value, "iou_threshold": value}))
                self.assertEqual(load_detection_config(path)["confidence_threshold"], value)

    def test_missing_malformed_incomplete_extra(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "detection.json"
            with self.assertRaisesRegex(ValueError, "detection.json"):
                load_detection_config(path)
            for text in ("{", "[]", "{}", json.dumps({**load_detection_config(), "extra": 1})):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    load_detection_config(path)


class DetectorTests(unittest.TestCase):
    def setUp(self):
        self.config = load_detection_config()
        self.frame = MagicMock(shape=(720, 1280, 3), size=720 * 1280 * 3)
        self.model = MagicMock()
        self.model.names = {0: "person", 1: "bicycle"}
        self.result = MagicMock()
        self.result.boxes.data.cpu.return_value.tolist.return_value = [
            [10, 20, 100, 200, 0.87, 0],
            [20, 20, 100, 200, 0.90, 1],
            [10, 20, 100, 200, 0.10, 0],
        ]
        self.result.speed = {"inference": 12.5}
        self.model.predict.return_value = [self.result]
        self.factory = MagicMock(return_value=self.model)
        self.loader = patch.object(detector, "_load_yolo", return_value=self.factory)
        self.loader.start()
        self.addCleanup(self.loader.stop)

    def test_one_model_multiple_frames_person_filter_and_memory_only(self):
        instance = PersonDetector(self.config)
        result = instance.detect(self.frame)
        instance.detect(self.frame)
        self.factory.assert_called_once_with(str(PROJECT_ROOT / "yolo26n.pt"), task="detect")
        self.assertEqual(result.detections, (Detection(10, 20, 100, 200, 0.87, 0),))
        self.assertEqual(result.inference_ms, 12.5)
        self.assertGreaterEqual(result.processing_ms, 0)
        args = self.model.predict.call_args.kwargs
        self.assertIs(args["source"], self.frame)
        self.assertEqual(args["classes"], [0])
        for arg in ("save", "save_txt", "save_conf", "save_crop", "show", "visualize", "stream"):
            self.assertIs(args[arg], False)
        self.assertEqual(args["device"], "cpu")
        self.model.track.assert_not_called()
        self.model.train.assert_not_called()
        self.result.save.assert_not_called()

    def test_inference_parameters_are_configurable(self):
        config = {**self.config, "confidence_threshold": 0.5, "iou_threshold": 0.6, "image_size": 320}
        PersonDetector(config).detect(self.frame)
        args = self.model.predict.call_args.kwargs
        self.assertEqual((args["conf"], args["iou"], args["imgsz"]), (0.5, 0.6, 320))

    def test_no_people_and_no_timing(self):
        self.result.boxes = None
        self.result.speed = {}
        result = PersonDetector(self.config).detect(self.frame)
        self.assertEqual(result.detections, ())
        self.assertIsNone(result.inference_ms)

    def test_invalid_timing_is_not_displayed(self):
        instance = PersonDetector(self.config)
        for value in (float("nan"), float("inf"), -1, "10"):
            with self.subTest(value=value):
                self.result.speed = {"inference": value}
                self.assertIsNone(instance.detect(self.frame).inference_ms)

    def test_wrong_class_mapping(self):
        for names, class_id in (({0: "cat"}, 0), ({0: "person", 1: "cat"}, 1), ({0: "person"}, 2)):
            with self.subTest(names=names, class_id=class_id):
                self.model.names = names
                with self.assertRaisesRegex(RuntimeError, "person_class_id"):
                    PersonDetector({**self.config, "person_class_id": class_id})

    def test_failed_model_download_has_clear_error(self):
        self.factory.side_effect = FileNotFoundError("pesos ausentes")
        with self.assertRaisesRegex(RuntimeError, "primera descarga"):
            PersonDetector(self.config)

    def test_failed_inference_has_clear_error(self):
        self.model.predict.side_effect = RuntimeError("inference failure")
        with self.assertRaisesRegex(RuntimeError, "inferencia local"):
            PersonDetector(self.config).detect(self.frame)

    def test_empty_frame_or_external_source_rejected(self):
        instance = PersonDetector(self.config)
        for frame in (None, "https://example.com/video", 0, MagicMock(shape=(0, 0, 3), size=0)):
            with self.subTest(frame=frame):
                with self.assertRaisesRegex(ValueError, "frame OpenCV"):
                    instance.detect(frame)
        self.model.predict.assert_not_called()

    def test_detection_data_contains_no_tracking_identity(self):
        self.assertEqual([field.name for field in dataclasses.fields(Detection)],
                         ["x1", "y1", "x2", "y2", "confidence", "class_id"])

    def test_model_path_independent_of_cwd(self):
        original = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                instance = PersonDetector(self.config)
                self.assertEqual(instance.model_path, PROJECT_ROOT / "yolo26n.pt")
            finally:
                os.chdir(original)


class DependencyTests(unittest.TestCase):
    def test_import_does_not_load_ai_or_open_camera(self):
        script = ("import sys; import src.detector, src.detect, src.main; "
                  "assert all(x not in sys.modules for x in ('torch', 'ultralytics', 'cv2')); "
                  "print('imports sin IA ni cámara')")
        result = subprocess.run([sys.executable, "-c", script], cwd=PROJECT_ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_ultralytics(self):
        with patch.dict(sys.modules, {"ultralytics": None}), patch.dict(os.environ):
            with self.assertRaisesRegex(RuntimeError, "pip install -r requirements.txt"):
                detector._load_yolo()

    def test_local_settings_disable_sync_and_autoinstall(self):
        module = SimpleNamespace(YOLO=MagicMock(), settings=MagicMock())
        with patch.dict(sys.modules, {"ultralytics": module}), patch.dict(os.environ):
            self.assertIs(detector._load_yolo(), module.YOLO)
            module.settings.update.assert_called_once_with({"sync": False})
            self.assertEqual(os.environ["YOLO_OFFLINE"], "true")
            self.assertEqual(os.environ["YOLO_AUTOINSTALL"], "false")

    def test_diagnostics_missing_dependencies(self):
        output = StringIO()
        with patch.object(diagnostics, "version", side_effect=diagnostics.PackageNotFoundError), \
                redirect_stdout(output):
            self.assertFalse(diagnostics.report_detection())
        self.assertIn("FALTA ultralytics", output.getvalue())
        self.assertIn("FALTA torch", output.getvalue())
        self.assertIn("Detección configurada", output.getvalue())

    def test_diagnostics_bad_import_and_config_still_reports_versions(self):
        with patch.object(diagnostics, "load_detection_config", side_effect=ValueError("JSON inválido")), \
                patch.object(diagnostics, "version", return_value="0"), \
                patch.object(diagnostics, "import_module", side_effect=OSError("DLL ausente")), \
                patch.object(detector, "_load_yolo", side_effect=RuntimeError("DLL ausente")), \
                redirect_stdout(StringIO()) as output:
            self.assertFalse(diagnostics.report_detection())
        self.assertIn("JSON inválido", output.getvalue())
        self.assertIn("DLL ausente", output.getvalue())
        self.assertIn("Distribución torchvision", output.getvalue())


class DetectionResourceTests(unittest.TestCase):
    def setUp(self):
        self.camera_config = load_config()
        self.config = load_detection_config()
        self.frame = MagicMock(shape=(720, 1280, 3), size=100)
        self.capture = MagicMock()
        self.capture.read.return_value = (True, self.frame)
        self.capture.getBackendName.return_value = "MOCK"
        self.ui = MagicMock()
        self.ui.error = cv2.error
        self.ui.waitKey.return_value = ord("q")
        self.ui.getWindowProperty.return_value = 1
        self.detector = MagicMock()
        self.detector.detect.return_value = FrameDetections((Detection(10, 20, 100, 200, 0.87, 0),), 10, 15)

    def run_app(self, error=None, load_error=None):
        with patch.object(camera.cv2, "VideoCapture", return_value=self.capture), \
                patch.object(detect, "PersonDetector", return_value=self.detector, side_effect=load_error):
            if error:
                with self.assertRaises(error):
                    detect.run_detection(self.ui, self.camera_config, self.config)
            else:
                detect.run_detection(self.ui, self.camera_config, self.config)
        self.capture.release.assert_called_once()
        self.ui.destroyAllWindows.assert_called_once()

    def test_q(self):
        self.run_app()
        self.ui.rectangle.assert_called_once()
        labels = [c.args[1] for c in self.ui.putText.call_args_list]
        self.assertIn("person 0.87", labels)

    def test_escape(self):
        self.ui.waitKey.return_value = 27
        self.run_app()

    def test_window_close(self):
        self.ui.waitKey.return_value = -1
        self.ui.getWindowProperty.return_value = 0
        self.run_app()

    def test_ctrl_c_during_inference(self):
        self.detector.detect.side_effect = KeyboardInterrupt()
        self.run_app(KeyboardInterrupt)

    def test_loading_failure_releases(self):
        self.run_app(RuntimeError, RuntimeError("modelo ausente"))

    def test_ctrl_c_during_load_releases(self):
        self.run_app(KeyboardInterrupt, KeyboardInterrupt())

    def test_inference_failure_releases(self):
        self.detector.detect.side_effect = RuntimeError("infer")
        self.run_app(RuntimeError)

    def test_ui_failure_releases(self):
        self.ui.imshow.side_effect = cv2.error("GUI")
        self.run_app(cv2.error)

    def test_later_read_failure_releases(self):
        self.ui.waitKey.return_value = -1
        self.capture.read.side_effect = [(True, self.frame), (False, None)]
        self.run_app(RuntimeError)

    def test_open_failure_still_cleans_windows(self):
        self.capture.open.return_value = False
        with patch.object(camera, "backend_candidates", return_value=[("mock", 0)]):
            self.run_app(RuntimeError)

    def test_confidence_hidden(self):
        self.config = {**self.config, "show_confidence": False}
        self.run_app()
        labels = [c.args[1] for c in self.ui.putText.call_args_list]
        self.assertIn("person", labels)
        self.assertNotIn("person 0.87", labels)

    def test_pipeline_fps_excludes_initial_inference(self):
        self.ui.waitKey.side_effect = [-1, -1, ord("q")]
        with patch.object(detect.time, "perf_counter", side_effect=[1000, 1000.5, 1001]):
            self.run_app()
        labels = [c.args[1] for c in self.ui.putText.call_args_list]
        self.assertTrue(any("FPS pipeline: 2.0" in label for label in labels))


if __name__ == "__main__":
    unittest.main()
