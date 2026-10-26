"""Runner: inferencia simulada explícitamente; MP4/serialización reales cuando indicado."""

import csv
import io
import json
import subprocess
import sys
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src import detector, tracker, video_runner as runner
from src.config import PROJECT_ROOT, load_detection_config, load_tracking_config
from src.detector import FrameDetections
from src.devices import DeviceResolution
from src.process_videos import main
from src.tracker import FrameTracks, Track
from src.video_source import FramePacket, discover_cases
from video_test_support import temporary_directory


PARAMS = dict(tracker_type="bytetrack", track_high_thresh=.25, track_low_thresh=.1,
              new_track_thresh=.25, track_buffer=30, match_thresh=.8, fuse_score=True)


def prepared():
    return runner.PreparedRun(load_detection_config(), load_tracking_config(),
                              {"profile": "bytetrack_baseline", "model_sha256": "mock"}, MagicMock())


class FakeSource:
    status = "completed"
    reason = "synthetic source (not inference evidence)"
    metadata = {"reported_frames": 2}

    def __init__(self, path):
        self.frames_read = 0
        self.released = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.released = True

    def __iter__(self):
        for i in range(2):
            self.frames_read += 1
            yield FramePacket(i, i * 40, "mock", object(), .1)


class FakeEngine:
    instances = []
    failure = None

    def __init__(self, config, *args, device_override):
        self.config = {**config, "device": device_override}
        self.device_resolution = DeviceResolution(config["device"], None, device_override)
        self.frames = 0
        self.instances.append(self)

    def track(self, frame):
        if self.failure:
            raise self.failure
        self.frames += 1
        return FrameTracks((Track(1, 2, 3, 4, .9, 0, self.frames),), (), None, .2)

    def detect(self, frame):
        if self.failure:
            raise self.failure
        self.frames += 1
        return FrameDetections((), None, .2)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("b.mp4", "a.mp4"):
            (self.root / name).write_bytes(name.encode())
        self.cases = discover_cases(directory=self.root)
        FakeEngine.instances = []
        FakeEngine.failure = None
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(runner, "prepare_runtime", side_effect=lambda options: prepared()))
        self.stack.enter_context(patch.object(runner, "PersonDetector", FakeEngine))
        self.stack.enter_context(patch.object(runner, "PersonTracker", FakeEngine))
        self.sources = []
        def source(path):
            result = FakeSource(path)
            self.sources.append(result)
            return result
        self.stack.enter_context(patch.object(runner, "VideoSource", side_effect=source))

    def run_cases(self, mode="tracking", device="cpu"):
        return runner.run_cases(self.cases, runner.RunOptions(mode, device), self.root / "results")

    def test_sequential_isolation_complete_results_and_no_overwrite(self):
        path, summary = self.run_cases()
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["not_processed"], [])
        self.assertEqual([e.frames for e in FakeEngine.instances], [2, 2])
        self.assertIsNot(FakeEngine.instances[0], FakeEngine.instances[1])
        self.assertTrue(all(source.released for source in self.sources))
        for case in self.cases:
            rows = [json.loads(line) for line in (path / case.case_id / "predictions.jsonl").read_text().splitlines()]
            self.assertEqual([row["tracks"][0]["track_id"] for row in rows], [1, 2])
            metadata = json.loads((path / case.case_id / "metadata.json").read_text())
            self.assertEqual(metadata["device_effective"], "cpu")
            self.assertEqual(metadata["frames_processed"], 2)
            self.assertEqual(metadata["frames_read"], 2)
            self.assertEqual(metadata["input_sha256"], case.sha256)
        before = (path / "summary.json").read_bytes()
        other, _ = self.run_cases()
        self.assertNotEqual(path, other)
        self.assertEqual((path / "summary.json").read_bytes(), before)

    def test_detection_mode_empty_rows_and_cuda_forwarded(self):
        path, summary = self.run_cases("detection", "cuda:0")
        self.assertEqual(summary["status"], "completed")
        self.assertTrue(all(e.config["device"] == "cuda:0" for e in FakeEngine.instances))
        rows = (path / self.cases[0].case_id / "predictions.jsonl").read_text().splitlines()
        self.assertEqual(len(rows), 2)
        self.assertEqual(json.loads(rows[0])["detections"], [])

    def test_per_video_failure_continues_and_release(self):
        FakeEngine.failure = RuntimeError("inference mock failure")
        _, summary = self.run_cases()
        self.assertEqual(summary["status"], "failed")
        self.assertEqual(len(summary["results"]), 2)
        self.assertTrue(all(s.released for s in self.sources))
        self.assertEqual(summary["results"][0]["frames_processed"], 0)

    def test_interrupt_stops_batch_and_keeps_metadata(self):
        FakeEngine.failure = KeyboardInterrupt()
        directory, summary = self.run_cases()
        self.assertEqual(summary["status"], "interrupted")
        self.assertEqual(len(summary["results"]), 1)
        self.assertEqual(len(summary["not_processed"]), 1)
        self.assertTrue(self.sources[0].released)
        self.assertEqual(json.loads((directory / "run.json").read_text())["status"], "interrupted")

    def test_incomplete_eof_is_not_success(self):
        with patch.object(FakeSource, "status", "incomplete"):
            _, summary = self.run_cases()
        self.assertEqual(summary["status"], "incomplete")

    def test_changed_input_rejected_before_engine(self):
        self.cases[0].path.write_bytes(b"changed")
        _, summary = self.run_cases()
        self.assertEqual(summary["results"][0]["status"], "failed")
        self.assertEqual(len(FakeEngine.instances), 1)

    def test_global_preflight_failure_keeps_manifest_and_skips_videos(self):
        with patch.object(runner, "prepare_runtime", side_effect=RuntimeError("weights absent")):
            directory, summary = self.run_cases()
        self.assertEqual(summary["status"], "failed")
        self.assertEqual(len(summary["not_processed"]), 2)
        self.assertEqual(FakeEngine.instances, [])
        self.assertTrue((directory / "run.json").is_file())

    def test_existing_case_metadata_untouched(self):
        case = self.cases[0]
        directory = self.root / case.case_id
        directory.mkdir()
        existing = directory / "metadata.json"
        existing.write_text("previous")
        result = runner.process_case(case, runner.RunOptions("tracking", "cpu"), prepared(), self.root)
        self.assertEqual(result.status, "failed")
        self.assertEqual(existing.read_text(), "previous")

    def test_output_open_failure_closes_and_marks_case_failed(self):
        with patch("src.video_results.VideoResults.append", side_effect=OSError("disk full")):
            _, summary = self.run_cases()
        self.assertEqual(summary["status"], "failed")
        self.assertTrue(all(s.released for s in self.sources))

    def test_effective_device_mismatch_aborts_before_processing(self):
        class WrongEngine(FakeEngine):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.device_resolution = DeviceResolution("cpu", None, "cpu")
        with patch.object(runner, "PersonTracker", WrongEngine):
            _, summary = self.run_cases(device="cuda:0")
        self.assertEqual(summary["status"], "failed")
        self.assertTrue(all(e.frames == 0 for e in FakeEngine.instances))

    def test_cli_modes_exit_codes_and_validation(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--directory", str(self.root), "--mode", "tracking", "--device", "cpu",
                                   "--output", str(self.root / "out")]), 0)
            FakeEngine.failure = KeyboardInterrupt()
            self.assertEqual(main(["--video", str(self.cases[0].path), "--mode", "detection", "--device", "cpu",
                                   "--output", str(self.root / "out")]), 130)
        with self.assertLogs(level="ERROR"):
            self.assertEqual(main(["--video", "missing.mp4", "--mode", "tracking", "--device", "cuda:bad"]), 1)

    def test_empty_and_unsafe_case_ids_rejected(self):
        from dataclasses import replace
        for cases in ([], [replace(self.cases[0], case_id="../escape")], [self.cases[0]] * 2):
            with self.subTest(cases=cases), self.assertRaises(ValueError):
                runner.run_cases(cases, runner.RunOptions("tracking", "cpu"), self.root)


class ExplicitDeviceTests(unittest.TestCase):
    def setUp(self):
        self.config = load_detection_config()
        self.model = MagicMock()
        self.model.names = {0: "person"}
        self.factory = MagicMock(return_value=self.model)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        local = self.stack.enter_context(temporary_directory())
        (Path(local) / "yolo26n.pt").write_bytes(b"mock weights; no inference")
        self.stack.enter_context(patch.object(detector, "PROJECT_ROOT", Path(local)))
        self.stack.enter_context(patch.object(detector, "_load_yolo", return_value=self.factory))

    def test_explicit_cpu_and_cuda_bypass_preference(self):
        for device in ("cpu", "cuda:0"):
            with self.subTest(device=device), patch.object(detector, "resolve_effective_device") as resolve, \
                    patch.object(detector, "validate_device") as validate:
                person = detector.PersonDetector(self.config, device_override=device)
                self.assertEqual(person.config["device"], device)
                validate.assert_called_once_with(device)
                resolve.assert_not_called()
        self.assertEqual(self.config["device"], "cpu")

    def test_default_preserves_shared_resolution(self):
        resolution = DeviceResolution("cpu", "cuda:0", "cpu", True)
        with patch.object(detector, "resolve_effective_device", return_value=resolution) as resolve:
            person = detector.PersonDetector(self.config)
        resolve.assert_called_once_with("cpu")
        self.assertIs(person.device_resolution, resolution)

    def test_unavailable_explicit_cuda_never_loads_model_or_fallback(self):
        with patch.object(detector, "validate_device", side_effect=RuntimeError("no CUDA")), \
                patch.object(detector, "resolve_effective_device") as resolve:
            with self.assertRaisesRegex(RuntimeError, "no CUDA"):
                detector.PersonDetector(self.config, device_override="cuda:0")
        self.factory.assert_not_called()
        resolve.assert_not_called()

    def test_explicit_device_with_missing_weights_never_invokes_yolo(self):
        with temporary_directory() as local, patch.object(detector, "PROJECT_ROOT", Path(local)):
            with self.assertRaisesRegex(RuntimeError, "No se descargarán"):
                detector.PersonDetector(self.config, device_override="cpu")
        self.factory.assert_not_called()

    def test_tracker_forwards_override_and_default_call_contract(self):
        for device in (None, "cpu", "cuda:0"):
            received = []
            def loader(config, **kwargs):
                received.append((dict(config), kwargs))
                return self.model, DeviceResolution("cpu", None, device or "cpu")
            with self.subTest(device=device), patch.object(tracker, "load_tracker_config", return_value=PARAMS), \
                    patch.object(tracker, "load_person_model", side_effect=loader) as load:
                tracker.PersonTracker(self.config, load_tracking_config(), device_override=device)
                self.assertEqual(load.call_count, 1)
                self.assertEqual(received, [(self.config, {} if device is None else {"device_override": device})])


class PreflightTests(unittest.TestCase):
    def test_missing_weights_blocks_imports_and_inference(self):
        with temporary_directory() as temp, patch.object(runner, "PROJECT_ROOT", Path(temp)), \
                patch.object(runner, "load_torch") as torch:
            with self.assertRaisesRegex(RuntimeError, "pesos locales"):
                runner.prepare_runtime(runner.RunOptions("detection", "cpu"))
        torch.assert_not_called()

    def test_light_import_and_help_do_not_load_ai_or_opencv(self):
        code = "import sys; import src.process_videos; assert not any(n in sys.modules for n in ('torch','cv2','ultralytics'))"
        result = subprocess.run([sys.executable, "-c", code], cwd=PROJECT_ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([sys.executable, "-m", "src.process_videos", "--help"],
                                cwd=PROJECT_ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--directory", result.stdout)

    def test_cuda_preflight_failure_precedes_any_model(self):
        with temporary_directory() as temp:
            root = Path(temp)
            (root / "yolo26n.pt").write_bytes(b"local fixture, not weights")
            with patch.object(runner, "PROJECT_ROOT", root), \
                    patch.object(runner, "load_torch", return_value=MagicMock()), \
                    patch.object(runner, "validate_device", side_effect=RuntimeError("CUDA unavailable")), \
                    patch.object(runner, "PersonDetector") as person:
                with self.assertRaisesRegex(RuntimeError, "CUDA unavailable"):
                    runner.prepare_runtime(runner.RunOptions("detection", "cuda:0"))
            person.assert_not_called()


class CameraTrackingContractTests(unittest.TestCase):
    def test_existing_tracking_camera_loop_releases_on_all_paths(self):
        import cv2
        import numpy as np
        from src import camera, track
        from src.config import load_config
        for scenario in ("q", "escape", "closed", "read", "load", "inference", "interrupt", "gui"):
            with self.subTest(scenario=scenario):
                capture = MagicMock()
                frame = np.zeros((48, 64, 3), dtype=np.uint8)
                capture.getBackendName.return_value = "mock"
                capture.read.return_value = (False, None)
                engine = MagicMock()
                engine.config = load_detection_config()
                engine.bytetrack_config = PARAMS
                engine.track.return_value = FrameTracks((), (), None, 1)
                ui = MagicMock()
                ui.error = cv2.error
                ui.waitKey.return_value = ord("q") if scenario == "q" else 27 if scenario == "escape" else -1
                ui.getWindowProperty.return_value = 0 if scenario == "closed" else 1
                load_error = RuntimeError("load") if scenario == "load" else None
                if scenario in ("inference", "interrupt"):
                    engine.track.side_effect = KeyboardInterrupt() if scenario == "interrupt" else RuntimeError("infer")
                if scenario == "gui":
                    ui.imshow.side_effect = cv2.error("gui")
                with patch.object(camera, "open_camera", return_value=(capture, frame)), \
                        patch.object(track, "PersonTracker", return_value=engine, side_effect=load_error):
                    if scenario in ("q", "escape", "closed"):
                        track.run_tracking(ui, load_config(), load_detection_config(), load_tracking_config())
                    else:
                        with self.assertRaises(KeyboardInterrupt if scenario == "interrupt" else (RuntimeError, cv2.error)):
                            track.run_tracking(ui, load_config(), load_detection_config(), load_tracking_config())
                capture.release.assert_called_once()
                ui.destroyAllWindows.assert_called_once()


class RealDecoderRunnerTests(unittest.TestCase):
    def test_two_actual_mp4_files_with_simulated_inference(self):
        import cv2
        import numpy as np
        with temporary_directory() as temp:
            root = Path(temp)
            for name in ("a.mp4", "b.mp4"):
                writer = cv2.VideoWriter(str(root / name), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
                if not writer.isOpened():
                    writer.release()
                    self.skipTest("Encoder MP4 no disponible; integración de lectura pendiente.")
                try:
                    for value in (10, 100):
                        writer.write(np.full((48, 64, 3), value, dtype=np.uint8))
                finally:
                    writer.release()
            FakeEngine.instances = []
            FakeEngine.failure = None
            cases = discover_cases(directory=root)
            with patch.object(runner, "prepare_runtime", return_value=prepared()), \
                    patch.object(runner, "PersonTracker", FakeEngine), \
                    patch.object(cv2, "imshow", side_effect=AssertionError("no GUI")), \
                    patch.object(cv2, "waitKey", side_effect=AssertionError("no GUI")):
                directory, summary = runner.run_cases(cases, runner.RunOptions("tracking", "cpu"), root / "out")
            self.assertEqual(summary["status"], "completed")
            self.assertEqual([e.frames for e in FakeEngine.instances], [2, 2])
            for case in cases:
                with (directory / case.case_id / "timings.csv").open(newline="") as stream:
                    self.assertEqual(len(list(csv.DictReader(stream))), 2)


if __name__ == "__main__":
    unittest.main()
