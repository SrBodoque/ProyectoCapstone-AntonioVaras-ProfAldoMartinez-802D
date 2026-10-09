"""Preferencia local opcional: archivos temporales, sin webcam ni GPU física."""

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

from src import devices, device_selector, detector, diagnostics, tracker
from src.config import PROJECT_ROOT, load_detection_config, load_tracking_config
from test_device_selector import fake_torch


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "device.local.json"
        self.torch = fake_torch(1, True, "13.2")

    def resolve(self, base="cpu"):
        return devices.resolve_effective_device(base, self.path, torch_module=self.torch)

    def save(self, device):
        self.path.write_text(json.dumps({"device": device}))

    def test_no_local_uses_cpu_without_warning_input_or_write(self):
        with patch.object(devices.LOGGER, "warning") as warning, \
                patch("builtins.input", side_effect=AssertionError("no menú")), \
                patch.object(devices, "load_torch", side_effect=AssertionError("no CUDA")):
            result = self.resolve()
        self.assertEqual(result.effective_device, "cpu")
        self.assertIsNone(result.local_preference)
        self.assertFalse(result.fallback)
        self.assertEqual(result.notices, ())
        self.assertFalse(self.path.exists())
        warning.assert_not_called()
        self.torch.cuda.is_available.assert_not_called()

    def test_explicit_local_cpu_overrides_cuda_base(self):
        self.save("cpu")
        result = self.resolve("cuda:0")
        self.assertEqual((result.base_device, result.local_preference, result.effective_device),
                         ("cuda:0", "cpu", "cpu"))
        self.torch.ones.assert_not_called()

    def test_valid_gpu_keeps_preference_and_effective_separate(self):
        self.save("cuda:0")
        result = self.resolve()
        self.assertEqual((result.base_device, result.local_preference, result.effective_device),
                         ("cpu", "cuda:0", "cuda:0"))
        self.assertFalse(result.fallback)
        self.torch.ones.assert_called_once_with(1, device="cuda:0")
        self.torch.cuda.synchronize.assert_called_once_with(0)

    def test_unavailable_local_gpu_falls_back_without_writing(self):
        self.save("cuda:0")
        before = self.path.read_bytes()
        self.torch.cuda.is_available.return_value = False
        with self.assertLogs(devices.LOGGER, level="WARNING") as logs:
            result = self.resolve()
        self.assertEqual(result.effective_device, "cpu")
        self.assertEqual(result.local_preference, "cuda:0")
        self.assertTrue(result.fallback)
        self.assertIn("CPU para esta ejecución", " ".join(logs.output))
        self.assertIn("python -m src.device_selector", " ".join(logs.output))
        self.assertEqual(self.path.read_bytes(), before)

    def test_local_out_of_range_uses_cpu(self):
        self.save("cuda:99")
        with self.assertLogs(devices.LOGGER, level="WARNING"):
            self.assertEqual(self.resolve().effective_device, "cpu")
        self.torch.ones.assert_not_called()

    def test_failed_tensor_kernel_sync_or_result_uses_cpu(self):
        self.save("cuda:0")
        before = self.path.read_bytes()
        for stage in ("allocate", "kernel", "sync", "result"):
            self.torch = fake_torch(1, True, "13.2")
            if stage == "allocate":
                self.torch.ones.side_effect = RuntimeError("memoria")
            elif stage == "kernel":
                self.torch.ones.return_value.add_.side_effect = RuntimeError("kernel")
            elif stage == "sync":
                self.torch.cuda.synchronize.side_effect = RuntimeError("sync")
            else:
                self.torch.ones.return_value.item.return_value = 0
            with self.subTest(stage=stage), self.assertLogs(devices.LOGGER, level="WARNING"):
                self.assertEqual(self.resolve().effective_device, "cpu")
            self.assertEqual(self.path.read_bytes(), before)

    def test_cuda_recovery_reuses_original_preference(self):
        self.save("cuda:0")
        self.torch.cuda.is_available.return_value = False
        with self.assertLogs(devices.LOGGER, level="WARNING"):
            self.assertEqual(self.resolve().effective_device, "cpu")
        self.torch.cuda.is_available.return_value = True
        self.assertEqual(self.resolve().effective_device, "cuda:0")

    def assert_invalid_local_ignored(self, content):
        self.path.write_bytes(content)
        with self.assertLogs(devices.LOGGER, level="WARNING") as logs:
            result = self.resolve()
        self.assertEqual(result.effective_device, "cpu")
        self.assertIsNone(result.local_preference)
        self.assertIn("local inválida", " ".join(logs.output))
        self.assertEqual(self.path.read_bytes(), content)

    def test_corrupt_local_uses_base_without_repair(self):
        self.assert_invalid_local_ignored(b'{"device":')

    def test_missing_local_field_uses_base_without_repair(self):
        self.assert_invalid_local_ignored(b'{}')

    def test_invalid_local_formats_types_and_extra_fields(self):
        for value in ("gpu", "cuda", "cuda:-1", "cuda:01", None, True, 0, [], {}):
            with self.subTest(value=value):
                self.assert_invalid_local_ignored(json.dumps({"device": value}).encode())
        self.assert_invalid_local_ignored(b'{"device":"cpu","extra":1}')
        self.assert_invalid_local_ignored(b'[]')

    def test_invalid_encoding_is_tolerated(self):
        self.assert_invalid_local_ignored(b'\xff')

    def test_unreadable_local_is_tolerated(self):
        self.path.mkdir()
        with self.assertLogs(devices.LOGGER, level="WARNING"):
            self.assertEqual(self.resolve().effective_device, "cpu")
        self.assertTrue(self.path.is_dir())

    def test_local_bom_is_supported(self):
        self.path.write_text('{"device":"cpu"}', encoding="utf-8-sig")
        self.assertEqual(self.resolve().local_preference, "cpu")

    def test_invalid_base_is_not_hidden_by_local_cpu(self):
        self.save("cpu")
        with self.assertRaises(ValueError):
            self.resolve("gpu")

    def test_unavailable_base_cuda_still_requires_explicit_correction(self):
        self.torch.cuda.is_available.return_value = False
        with self.assertRaises(RuntimeError):
            self.resolve("cuda:0")


class OptionalPipelineTests(unittest.TestCase):
    def setUp(self):
        self.base = load_detection_config()
        self.model = MagicMock()
        self.model.names = {0: "person"}
        self.model.predict.return_value = [SimpleNamespace(boxes=None, speed={})]
        self.model.track.return_value = [SimpleNamespace(boxes=None, speed={})]
        self.frame = SimpleNamespace(shape=(10, 10, 3), size=300)
        model_loader = patch.object(detector, "_load_yolo", return_value=MagicMock(return_value=self.model))
        model_loader.start()
        self.addCleanup(model_loader.stop)
        preference = patch.object(devices, "load_device_preference", return_value=None)
        preference.start()
        self.addCleanup(preference.stop)

    def test_detector_without_selector_passes_cpu(self):
        detector.PersonDetector(self.base).detect(self.frame)
        self.assertEqual(self.model.predict.call_args.kwargs["device"], "cpu")

    def test_tracker_without_selector_passes_cpu(self):
        tracker.PersonTracker(self.base, load_tracking_config()).track(self.frame)
        self.assertEqual(self.model.track.call_args.kwargs["device"], "cpu")

    def test_both_use_one_shared_resolver_and_preserve_input(self):
        before = self.base.copy()
        with patch.object(detector, "resolve_effective_device", wraps=devices.resolve_effective_device) as resolve:
            detector.PersonDetector(self.base)
            tracker.PersonTracker(self.base, load_tracking_config())
        self.assertEqual(resolve.call_count, 2)  # Una vez por instancia, no por frame.
        self.assertEqual(self.base, before)

    def test_fallback_metadata_keeps_preference_and_effective(self):
        with patch.object(devices, "load_device_preference", return_value="cuda:0"), \
                patch.object(devices, "load_torch", return_value=fake_torch()), \
                self.assertLogs(devices.LOGGER, level="WARNING"):
            for instance in (detector.PersonDetector(self.base), tracker.PersonTracker(self.base)):
                self.assertEqual(instance.device_resolution.local_preference, "cuda:0")
                self.assertEqual(instance.device_resolution.effective_device, "cpu")
                self.assertEqual(instance.config["device"], "cpu")
        self.assertEqual(self.base["device"], "cpu")

    def test_main_never_resolves_or_loads_inference(self):
        from src import main
        with patch.object(main.sys, "platform", "win32"), patch.object(main, "run_preview") as preview, \
                patch.object(devices, "resolve_effective_device", side_effect=AssertionError("inferencia")), \
                patch.object(devices, "load_torch", side_effect=AssertionError("torch")):
            self.assertEqual(main.main(), 0)
        preview.assert_called_once()


class SelectorAndDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "device.local.json"

    def test_selector_first_save_cpu_only_creates_local(self):
        camera_path = PROJECT_ROOT / "config" / "camera.json"
        base_path = PROJECT_ROOT / "config" / "detection.json"
        before = [p.read_bytes() for p in (camera_path, base_path)]
        with patch.object(device_selector, "load_torch", return_value=fake_torch()), \
                patch("builtins.input", return_value="0"), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(device_selector.main(self.path), 0)
        self.assertEqual(devices.load_device_preference(self.path), "cpu")
        self.assertNotIn("[1]", out.getvalue())
        self.assertEqual(before, [p.read_bytes() for p in (camera_path, base_path)])

    def test_selector_gpu_first_save_validates_before_creation(self):
        torch = fake_torch(1, True, "13.2")
        with patch.object(device_selector, "load_torch", return_value=torch), \
                patch.object(devices, "load_torch", return_value=torch), \
                patch("builtins.input", return_value="1"), redirect_stdout(io.StringIO()):
            self.assertEqual(device_selector.main(self.path), 0)
        self.assertEqual(devices.load_device_preference(self.path), "cuda:0")
        torch.ones.assert_called_once_with(1, device="cuda:0")

    def test_selector_torch_import_failure_has_no_menu_or_write(self):
        with patch.object(device_selector, "load_torch", side_effect=RuntimeError("WinError 4551: torch.dll")), \
                patch("builtins.input", side_effect=AssertionError("no menú")), \
                redirect_stdout(io.StringIO()), self.assertLogs(device_selector.LOGGER, level="ERROR") as logs:
            self.assertEqual(device_selector.main(self.path), 1)
        self.assertIn("4551", " ".join(logs.output))
        self.assertFalse(self.path.exists())

    def test_failed_first_write_leaves_no_local_or_temporary(self):
        with patch.object(device_selector.os, "replace", side_effect=PermissionError("permiso")):
            with self.assertRaises(OSError):
                device_selector.save_device("cpu", self.path)
        self.assertEqual(list(self.path.parent.iterdir()), [])

    def test_diagnostics_without_local_reports_cpu_and_never_saves(self):
        torch = fake_torch()
        versions = {"ultralytics": "8.4.163", "torch": "2.14.0+cpu", "torchvision": "0.29.0+cpu"}
        with patch.object(diagnostics, "version", side_effect=versions.__getitem__), \
                patch.object(diagnostics, "import_module", return_value=torch), \
                patch.object(detector, "_load_yolo"), \
                patch.object(devices, "load_device_preference", return_value=None), \
                patch("builtins.input", side_effect=AssertionError("selector")), \
                patch.object(device_selector, "save_device", side_effect=AssertionError("escritura")), \
                redirect_stdout(io.StringIO()) as out:
            self.assertTrue(diagnostics.report_detection())
        for expected in ("Configuración base: cpu", "Preferencia local: no configurada", "Dispositivo efectivo: cpu",
                         "Fallback GPU → CPU: False", "CUDA disponible: False", "GPUs CUDA: 0", "CUDA build: None"):
            self.assertIn(expected, out.getvalue())

    def test_diagnostics_broken_torch_is_controlled(self):
        with patch.object(diagnostics, "version", return_value="2.14.0"), \
                patch.object(diagnostics, "import_module", side_effect=OSError("WinError 4551: torch.dll")), \
                patch.object(detector, "_load_yolo", side_effect=RuntimeError("DLL")), \
                redirect_stdout(io.StringIO()) as out:
            self.assertFalse(diagnostics.report_detection())
        self.assertIn("PyTorch no pudo cargarse correctamente", out.getvalue())
        self.assertIn("no comprobable", out.getvalue())
        self.assertIn("4551", out.getvalue())

    def test_git_excludes_only_local_device_config(self):
        rules = (PROJECT_ROOT / ".gitignore").read_text().splitlines()
        self.assertIn("config/device.local.json", rules)
        self.assertNotIn("config/detection.json", rules)
        self.assertNotIn("config/camera.json", rules)

    def test_local_path_is_absolute_and_independent_of_cwd(self):
        script = "from src.devices import DEVICE_LOCAL_PATH; print(DEVICE_LOCAL_PATH)"
        result = subprocess.run([sys.executable, "-c", script], cwd=self.path.parent,
                                env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(PROJECT_ROOT / "config" / "device.local.json"))


if __name__ == "__main__":
    unittest.main()
