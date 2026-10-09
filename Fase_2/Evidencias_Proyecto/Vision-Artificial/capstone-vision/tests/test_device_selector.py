"""CPU/CUDA con hardware simulado; configuración persistida solo en temporales."""
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
from unittest.mock import MagicMock, patch

from src import devices, device_selector as selector, detector, diagnostics, tracker
from src.config import PROJECT_ROOT, load_detection_config, load_tracking_config


def fake_torch(count=0, available=False, build=None):
    torch = MagicMock()
    torch.__version__ = "2.14.0+cu132" if build else "2.14.0+cpu"
    torch.version = SimpleNamespace(cuda=build)
    torch.cuda.is_available.return_value = available
    torch.cuda.device_count.return_value = count
    torch.cuda.get_device_name.side_effect = lambda index: f"NVIDIA prueba {index}"
    torch.ones.return_value.item.return_value = 2
    return torch


class DeviceTests(unittest.TestCase):
    def test_import_has_no_input_ai_camera_or_writes(self):
        code = """
import sys
sys.dont_write_bytecode = True
from pathlib import Path
from unittest.mock import patch
before = {p: p.read_bytes() for p in Path('config').iterdir() if p.is_file()}
with patch('builtins.input', side_effect=AssertionError('input')), \
     patch('os.replace', side_effect=AssertionError('escritura')), \
     patch.object(Path, 'write_text', side_effect=AssertionError('escritura')):
    import src.device_selector
assert all(name not in sys.modules for name in ('torch','ultralytics','cv2','torchvision'))
assert before == {p: p.read_bytes() for p in before}
"""
        result = subprocess.run([sys.executable, "-c", code], cwd=PROJECT_ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_cpu_only_does_not_offer_gpu(self):
        torch = fake_torch()
        result = devices.discover_devices(torch)
        self.assertEqual([d.device for d in result.devices], ["cpu"])
        self.assertIn("no incluye un build CUDA", " ".join(result.notices))
        torch.cuda.get_device_name.assert_not_called()
        torch.ones.assert_not_called()

    def test_cuda_build_without_available_gpu_offers_only_cpu(self):
        result = devices.discover_devices(fake_torch(build="13.2"))
        self.assertEqual([d.device for d in result.devices], ["cpu"])
        self.assertFalse(result.cuda_available)
        self.assertEqual(result.cuda_build, "13.2")

    def test_one_and_multiple_gpus_keep_exact_indices_and_names(self):
        for count in (1, 2):
            with self.subTest(count=count):
                torch = fake_torch(count, True, "13.2")
                result = devices.discover_devices(torch)
                self.assertEqual([d.device for d in result.devices], ["cpu"] + [f"cuda:{i}" for i in range(count)])
                self.assertEqual([d.name for d in result.devices[1:]], [f"NVIDIA prueba {i}" for i in range(count)])
                self.assertEqual(result.cuda_count, count)
                torch.ones.assert_not_called()  # La prueba se hace sobre la elegida.

    def test_failed_name_does_not_renumber_other_gpu(self):
        torch = fake_torch(2, True, "13.2")
        torch.cuda.get_device_name.side_effect = [RuntimeError("GPU 0 inaccesible"), "GPU 1"]
        result = devices.discover_devices(torch)
        self.assertEqual([d.device for d in result.devices], ["cpu", "cuda:1"])
        with patch("builtins.input", return_value="1"):
            self.assertEqual(selector.choose_device(result.devices), "cuda:1")

    def test_missing_torch_still_offers_cpu_with_notice(self):
        with patch.object(devices, "load_torch", side_effect=RuntimeError("DLL ausente")):
            result = devices.discover_devices()
        self.assertEqual([d.device for d in result.devices], ["cpu"])
        self.assertIn("DLL ausente", result.notices[0])

    def test_cuda_query_failure_is_controlled(self):
        torch = fake_torch()
        torch.cuda.is_available.side_effect = RuntimeError("driver")
        result = devices.discover_devices(torch)
        self.assertEqual([d.device for d in result.devices], ["cpu"])
        self.assertIn("driver", result.notices[0])

    def test_cpu_runtime_does_not_require_cuda_or_import_torch(self):
        with patch.object(devices, "load_torch", side_effect=AssertionError("no importar")):
            devices.validate_device("cpu")

    def test_cuda_probe_uses_selected_device_and_synchronizes(self):
        torch = fake_torch(2, True, "13.2")
        devices.validate_device("cuda:1", torch_module=torch)
        torch.ones.assert_called_once_with(1, device="cuda:1")
        torch.ones.return_value.add_.assert_called_once_with(1)
        torch.cuda.synchronize.assert_called_once_with(1)

    def test_cuda_unavailable_and_out_of_range_have_actionable_error(self):
        for value, torch in (("cuda:0", fake_torch()),
                             ("cuda:1", fake_torch(1, True, "13.2")),
                             ("cuda:999999", fake_torch(1, True, "13.2"))):
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, "python -m src.device_selector"):
                devices.validate_device(value, torch_module=torch)
            torch.ones.assert_not_called()

    def test_probe_failures_do_not_fallback(self):
        for stage in ("allocate", "kernel", "synchronize", "result"):
            torch = fake_torch(1, True, "13.2")
            if stage == "allocate":
                torch.ones.side_effect = RuntimeError("CUDA memoria")
            elif stage == "kernel":
                torch.ones.return_value.add_.side_effect = RuntimeError("CUDA kernel")
            elif stage == "synchronize":
                torch.cuda.synchronize.side_effect = RuntimeError("CUDA sync")
            else:
                torch.ones.return_value.item.return_value = 0
            with self.subTest(stage=stage), self.assertRaisesRegex(RuntimeError, "validación explícita"):
                devices.validate_device("cuda:0", torch_module=torch)
            self.assertEqual(torch.ones.call_count, 1)
            self.assertEqual(torch.ones.call_args.kwargs["device"], "cuda:0")

    def test_cpu_gpu_and_invalid_choices(self):
        available = devices.discover_devices(fake_torch(2, True, "13.2")).devices
        for answer, expected in (("0", "cpu"), ("1", "cuda:0"), ("2", "cuda:1"), ("q", None)):
            with self.subTest(answer=answer), patch("builtins.input", return_value=answer):
                self.assertEqual(selector.choose_device(available), expected)
        with patch("builtins.input", side_effect=["texto", "", "-1", "3", "1.5", "2"]) as ask, redirect_stdout(io.StringIO()):
            self.assertEqual(selector.choose_device(available), "cuda:1")
        self.assertEqual(ask.call_count, 6)


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base_path = Path(self.directory.name) / "detection.json"
        self.path = Path(self.directory.name) / "device.local.json"
        self.config = {**load_detection_config(), "device": "cpu", "confidence_threshold": .71,
                       "iou_threshold": .63, "image_size": 320, "show_confidence": False}
        self.base_path.write_text(json.dumps(self.config, indent=4), encoding="utf-8-sig")
        self.base_before = self.base_path.read_bytes()
        self.path.write_text(json.dumps({"device": "cpu"}), encoding="utf-8-sig")
        self.before = self.path.read_bytes()
        self.torch = fake_torch(2, True, "13.2")
        self.loader = patch.object(devices, "load_torch", return_value=self.torch)
        self.loader.start()
        self.addCleanup(self.loader.stop)
        selector_loader = patch.object(selector, "load_torch", return_value=self.torch)
        selector_loader.start()
        self.addCleanup(selector_loader.stop)

    def assert_intact(self):
        self.assertEqual(self.path.read_bytes(), self.before)
        self.assertEqual(set(self.path.parent.iterdir()), {self.path, self.base_path})
        self.assertEqual(self.base_path.read_bytes(), self.base_before)

    def test_valid_formats_load_without_hardware(self):
        for value in ("cpu", "cuda:0", "cuda:1", "cuda:999999"):
            with self.subTest(value=value):
                self.base_path.write_text(json.dumps({**self.config, "device": value}), encoding="utf-8")
                self.assertEqual(load_detection_config(self.base_path)["device"], value)
        self.torch.cuda.is_available.assert_not_called()

    def test_invalid_formats_rejected_without_hardware(self):
        for value in ("gpu", "cuda", "cuda:-1", "cuda:x", "cuda:abc", "cuda:01", "cuda:１",
                      "cuda:0,1", "cuda:2147483648", "cuda:" + "9" * 5000,
                      "cpu ", "CPU", "mps", "", None, True, 0, [], {}):
            with self.subTest(value=str(value)[:25]):
                self.base_path.write_text(json.dumps({**self.config, "device": value}), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "device"):
                    load_detection_config(self.base_path)
        self.torch.cuda.is_available.assert_not_called()

    def test_save_cpu_and_cuda_only_writes_local_preference(self):
        for value in ("cuda:1", "cuda:0", "cpu"):
            with self.subTest(value=value):
                saved = selector.save_device(value, self.path)
                self.assertEqual(saved, {"device": value})
                self.assertEqual(devices.load_device_preference(self.path), value)
                self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), saved)
                self.assertEqual(set(self.path.parent.iterdir()), {self.path, self.base_path})
        self.assertEqual(self.base_path.read_bytes(), self.base_before)
        self.assertEqual(self.torch.ones.call_count, 2)

    def test_kernel_failure_never_saves(self):
        self.torch.ones.return_value.add_.side_effect = RuntimeError("kernel incompatible")
        with self.assertRaisesRegex(RuntimeError, "kernel incompatible"):
            selector.save_device("cuda:0", self.path)
        self.assert_intact()

    def test_disappeared_gpu_never_saves(self):
        self.torch.cuda.is_available.return_value = False
        with self.assertRaisesRegex(RuntimeError, "CUDA disponible: False"):
            selector.save_device("cuda:0", self.path)
        self.assert_intact()

    def test_invalid_selection_never_writes(self):
        with self.assertRaises(ValueError):
            selector.save_device("gpu", self.path)
        self.assert_intact()

    def test_partial_write_preserves_original(self):
        def partial(data, stream, **kwargs):
            stream.write('{"device":')
            raise OSError("disco lleno")
        with patch.object(selector.json, "dump", side_effect=partial), self.assertRaises(OSError):
            selector.save_device("cpu", self.path)
        self.assert_intact()

    def test_fsync_or_replace_failure_preserves_original(self):
        for operation in ("fsync", "replace"):
            with self.subTest(operation=operation), patch.object(selector.os, operation, side_effect=PermissionError("permiso")):
                with self.assertRaises(OSError):
                    selector.save_device("cuda:0", self.path)
                self.assert_intact()

    def test_invalid_temporary_not_installed(self):
        with patch.object(selector.json, "dump", side_effect=lambda data, stream, **kw: stream.write("{}")):
            with self.assertRaises(ValueError):
                selector.save_device("cpu", self.path)
        self.assert_intact()

    def test_invalid_local_can_be_repaired_explicitly(self):
        self.path.write_text("{", encoding="utf-8")
        selector.save_device("cpu", self.path)
        self.assertEqual(devices.load_device_preference(self.path), "cpu")
        self.assertEqual(set(self.path.parent.iterdir()), {self.path, self.base_path})
        self.assertEqual(self.base_path.read_bytes(), self.base_before)

    def test_same_directory_atomic_replace_and_reload(self):
        replace = os.replace
        def checked(source, target):
            self.assertEqual(source.parent, self.path.parent)
            self.assertEqual(self.path.read_bytes(), self.before)
            self.assertEqual(devices.load_device_preference(source), "cuda:0")
            replace(source, target)
        with patch.object(selector.os, "replace", side_effect=checked), \
                patch.object(selector, "load_device_preference", wraps=devices.load_device_preference) as read:
            selector.save_device("cuda:0", self.path)
        self.assertEqual(read.call_count, 2)
        self.assertEqual(read.call_args.args[0], self.path)
        self.assertEqual(set(self.path.parent.iterdir()), {self.path, self.base_path})
        self.assertEqual(self.base_path.read_bytes(), self.base_before)

    def test_save_preserves_changed_base_parameters(self):
        changed = {**self.config, "image_size": 960}
        self.base_path.write_text(json.dumps(changed), encoding="utf-8")
        selector.save_device("cuda:0", self.path)
        self.assertEqual(load_detection_config(self.base_path), changed)
        self.assertEqual(devices.load_device_preference(self.path), "cuda:0")

    def test_main_persists_gpu_for_new_process(self):
        with patch("builtins.input", return_value="2"), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(selector.main(self.path, self.base_path), 0)
        self.assertIn("[2] CUDA:1 - NVIDIA prueba 1", output.getvalue())
        script = "import sys; from pathlib import Path; from src.devices import load_device_preference; print(load_device_preference(Path(sys.argv[1])))"
        result = subprocess.run([sys.executable, "-c", script, str(self.path)], cwd=PROJECT_ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "cuda:1")

    def test_cpu_only_can_recover_saved_unavailable_cuda(self):
        self.path.write_text(json.dumps({"device": "cuda:0"}), encoding="utf-8")
        self.torch.cuda.is_available.return_value = False
        self.torch.cuda.device_count.return_value = 0
        self.torch.version.cuda = None
        with patch("builtins.input", return_value="0"), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(selector.main(self.path, self.base_path), 0)
        self.assertNotIn("[1]", output.getvalue())
        self.assertEqual(devices.load_device_preference(self.path), "cpu")
        self.torch.ones.assert_not_called()

    def test_cancel_eof_ctrl_c_leave_config_intact(self):
        for answer, error, status in (("q", None, 0), (None, EOFError, 1), (None, KeyboardInterrupt, 130)):
            with self.subTest(status=status), patch("builtins.input", return_value=answer, side_effect=error), redirect_stdout(io.StringIO()):
                self.assertEqual(selector.main(self.path, self.base_path), status)
            self.assert_intact()

    def test_main_probe_failure_returns_error_and_keeps_original(self):
        self.torch.ones.side_effect = RuntimeError("GPU no utilizable")
        with patch("builtins.input", return_value="1"), redirect_stdout(io.StringIO()), self.assertLogs(selector.LOGGER, level="ERROR") as output:
            self.assertEqual(selector.main(self.path, self.base_path), 1)
        self.assertIn("GPU no utilizable", " ".join(output.output))
        self.assert_intact()


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.config = {**load_detection_config(), "device": "cpu"}
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.local_path = Path(self.directory.name) / "device.local.json"
        self.local_path.write_text(json.dumps({"device": "cuda:1"}))
        read_preference = devices.load_device_preference
        self.preference_reader = patch.object(devices, "load_device_preference",
                                             side_effect=lambda path: read_preference(self.local_path))
        self.preference_reader.start()
        self.addCleanup(self.preference_reader.stop)
        self.torch = fake_torch(2, True, "13.2")
        self.model = MagicMock()
        self.model.names = {0: "person"}
        result = SimpleNamespace(boxes=None, speed={})
        self.model.predict.return_value = [result]
        self.model.track.return_value = [result]
        self.frame = SimpleNamespace(shape=(10, 10, 3), size=300)

    def test_detector_and_tracker_pass_exact_cuda_without_input(self):
        with patch.object(devices, "load_torch", return_value=self.torch), \
                patch.object(detector, "_load_yolo", return_value=MagicMock(return_value=self.model)), \
                patch("builtins.input", side_effect=AssertionError("no preguntar")):
            detector.PersonDetector(self.config).detect(self.frame)
            tracker.PersonTracker(self.config, load_tracking_config()).track(self.frame)
        self.assertEqual(self.model.predict.call_args.kwargs["device"], "cuda:1")
        self.assertEqual(self.model.track.call_args.kwargs["device"], "cuda:1")
        self.assertEqual(self.model.predict.call_count, 1)
        self.assertEqual(self.model.track.call_count, 1)

    def test_unavailable_local_gpu_uses_cpu_in_both(self):
        self.torch.cuda.is_available.return_value = False
        before = self.local_path.read_bytes()
        with patch.object(devices, "load_torch", return_value=self.torch), \
                patch.object(detector, "_load_yolo", return_value=MagicMock(return_value=self.model)), \
                self.assertLogs(devices.LOGGER, level="WARNING"):
            detector.PersonDetector(self.config).detect(self.frame)
            tracker.PersonTracker(self.config, load_tracking_config()).track(self.frame)
        for operation in (self.model.predict, self.model.track):
            self.assertEqual(operation.call_args.kwargs["device"], "cpu")
        self.assertEqual(self.local_path.read_bytes(), before)
        self.torch.ones.assert_not_called()

    def test_fallback_still_releases_camera_in_both_apps(self):
        import cv2
        from src import camera, detect, track
        from src.config import load_config

        self.torch.cuda.is_available.return_value = False
        for app in (detect, track):
            capture = MagicMock()
            capture.read.return_value = (True, self.frame)
            ui = MagicMock(error=cv2.error)
            ui.waitKey.return_value = ord("q")
            with self.subTest(app=app.__name__), \
                    patch.object(camera.cv2, "VideoCapture", return_value=capture), \
                    patch.object(devices, "load_torch", return_value=self.torch), \
                    patch.object(detector, "_load_yolo", return_value=MagicMock(return_value=self.model)), \
                    self.assertLogs(devices.LOGGER, level="WARNING"):
                if app is detect:
                    app.run_detection(ui, load_config(), self.config)
                else:
                    app.run_tracking(ui, load_config(), self.config, load_tracking_config())
            capture.release.assert_called_once()
            ui.destroyAllWindows.assert_called_once()
            labels = [call.args[1] for call in ui.putText.call_args_list]
            self.assertTrue(any(" | cpu" in label for label in labels))
            self.assertFalse(any(" | cuda:" in label for label in labels))

    def test_existing_commands_read_base_without_selecting(self):
        from src import detect, track

        for app, runner in ((detect, "run_detection"), (track, "run_tracking")):
            with self.subTest(app=app.__name__), \
                    patch.object(app, "load_detection_config", return_value=self.config), \
                    patch.object(app.sys, "platform", "win32"), patch.object(app, runner) as run, \
                    patch("builtins.input", side_effect=AssertionError("no preguntar")), \
                    patch.object(selector, "discover_devices", side_effect=AssertionError("no seleccionar")):
                for _ in range(2):
                    self.assertEqual(app.main(), 0)
                    self.assertEqual(run.call_args.args[2]["device"], "cpu")

    def test_inference_failure_does_not_retry_on_cpu(self):
        self.model.predict.side_effect = RuntimeError("CUDA execution failed")
        self.model.track.side_effect = RuntimeError("CUDA execution failed")
        with patch.object(devices, "load_torch", return_value=self.torch), \
                patch.object(detector, "_load_yolo", return_value=MagicMock(return_value=self.model)):
            for operation in (detector.PersonDetector(self.config).detect,
                              tracker.PersonTracker(self.config, load_tracking_config()).track):
                with self.assertRaisesRegex(RuntimeError, "CUDA execution failed"):
                    operation(self.frame)
        for operation in (self.model.predict, self.model.track):
            self.assertEqual(operation.call_count, 1)
            self.assertEqual(operation.call_args.kwargs["device"], "cuda:1")

    def test_diagnostics_cuda_build_names_and_local_version_suffix(self):
        def module(name):
            if name == "torch":
                return self.torch
            return SimpleNamespace(__version__={"ultralytics": "8.4.163", "torchvision": "0.29.0+cu132"}[name])
        versions = {"torch": "2.14.0+cu132", "torchvision": "0.29.0+cu132", "ultralytics": "8.4.163"}
        for device in ("cpu", "cuda:1"):
            with self.subTest(device=device), patch.object(diagnostics, "load_detection_config", return_value={**self.config, "device": device}), \
                    patch.object(diagnostics, "version", side_effect=versions.__getitem__), \
                    patch.object(diagnostics, "import_module", side_effect=module), \
                    patch.object(detector, "_load_yolo"), redirect_stdout(io.StringIO()) as output:
                self.assertTrue(diagnostics.report_detection())
            for expected in ("CUDA build: 13.2", "CUDA disponible: True", "GPUs CUDA: 2", "cuda:1: NVIDIA prueba 1", f"Configuración base: {device}", "Preferencia local: cuda:1", "Dispositivo efectivo: cuda:1"):
                self.assertIn(expected, output.getvalue())
            self.assertNotIn("no coincide", output.getvalue())
        self.assertEqual(self.torch.ones.call_count, 2)  # Misma validación ligera que runtime; sin modelo.

    def test_diagnostics_unavailable_local_gpu_reports_fallback(self):
        self.torch.cuda.is_available.return_value = False
        versions = {"torch": "2.14.0+cpu", "torchvision": "0.29.0+cpu", "ultralytics": "8.4.163"}
        with patch.object(diagnostics, "load_detection_config", return_value=self.config), \
                patch.object(diagnostics, "version", side_effect=versions.__getitem__), \
                patch.object(diagnostics, "import_module", return_value=self.torch), \
                patch.object(detector, "_load_yolo"), redirect_stdout(io.StringIO()) as output:
            self.assertTrue(diagnostics.report_detection())
        self.assertIn("python -m src.device_selector", output.getvalue())
        self.assertEqual(self.config["device"], "cpu")
        self.assertIn("Dispositivo efectivo: cpu", output.getvalue())
        self.assertIn("Fallback GPU → CPU: True", output.getvalue())


if __name__ == "__main__":
    unittest.main()
