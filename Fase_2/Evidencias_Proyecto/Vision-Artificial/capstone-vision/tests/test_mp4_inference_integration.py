"""Inferencia REAL opt-in con MP4/pesos locales. Una omisión significa pendiente."""

import importlib.util
import json
import os
import unittest
from pathlib import Path

from src.config import PROJECT_ROOT
from src.video_runner import RunOptions, run_cases
from src.video_source import discover_cases
from video_test_support import temporary_directory


class LocalMp4InferenceTests(unittest.TestCase):
    def test_real_detection_and_tracking(self):
        missing = [name for name in ("cv2", "torch", "ultralytics", "yaml", "lap")
                   if importlib.util.find_spec(name) is None]
        if missing:
            self.skipTest("Inferencia REAL pendiente: faltan " + ", ".join(missing))
        if not (PROJECT_ROOT / "yolo26n.pt").is_file():
            self.skipTest("Inferencia REAL pendiente: falta yolo26n.pt local; no se descarga.")
        path = os.environ.get("LIMPIA_TEST_MP4")
        if not path:
            self.skipTest("Inferencia REAL pendiente: definir LIMPIA_TEST_MP4 con un MP4 local.")
        cases = discover_cases(video=path)
        device = os.environ.get("LIMPIA_TEST_DEVICE", "cpu")
        with temporary_directory() as temp:
            for mode in ("detection", "tracking"):
                with self.subTest(mode=mode, device=device):
                    directory, summary = run_cases(cases, RunOptions(mode, device), Path(temp))
                    self.assertEqual(summary["status"], "completed", summary)
                    metadata = json.loads((directory / cases[0].case_id / "metadata.json").read_text(encoding="utf-8"))
                    self.assertEqual(metadata["device_effective"], device)
                    self.assertGreater(metadata["frames_processed"], 0)
                    with (directory / cases[0].case_id / "predictions.jsonl").open(encoding="utf-8") as stream:
                        self.assertEqual(sum(1 for _ in stream), metadata["frames_processed"])


if __name__ == "__main__":
    unittest.main()
