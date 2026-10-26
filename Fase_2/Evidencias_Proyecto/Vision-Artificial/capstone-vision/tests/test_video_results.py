"""Escritura incremental, formatos y protección contra sobrescrituras."""

import csv
import json
import unittest
from pathlib import Path

from src.detector import Detection, FrameDetections
from src.tracker import FrameTracks, Track
from src.video_results import VideoResults, create_run, write_json
from src.video_source import FramePacket
from video_test_support import temporary_directory


class ResultsTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_unique_runs_and_exclusive_case(self):
        first, a = create_run(self.root)
        second, b = create_run(self.root)
        self.assertNotEqual(first, second)
        self.assertNotEqual(a, b)
        with VideoResults(a / "case"):
            pass
        with self.assertRaises(FileExistsError), VideoResults(a / "case"):
            pass

    def test_predictions_and_timings_are_visible_per_frame(self):
        directory = self.root / "case"
        detection = Detection(1, 2, 3, 4, .9, 0)
        track = Track(1, 2, 3, 4, .9, 0, 9)
        with VideoResults(directory) as output:
            for i, result in enumerate((FrameDetections((), None, 1),
                                        FrameDetections((detection,), 2, 3),
                                        FrameTracks((track,), (detection,), 2, 3))):
                output.append(FramePacket(i, None, "unavailable", None, .5), result, 4)
                self.assertEqual(len((directory / "predictions.jsonl").read_text().splitlines()), i + 1)
                with (directory / "timings.csv").open(newline="") as stream:
                    self.assertEqual(len(list(csv.DictReader(stream))), i + 1)
        rows = [json.loads(line) for line in (directory / "predictions.jsonl").read_text().splitlines()]
        self.assertEqual(rows[0]["detections"], [])
        self.assertEqual(rows[1]["detections"][0]["confidence"], .9)
        self.assertEqual(rows[2]["tracks"][0]["track_id"], 9)
        self.assertEqual(len(rows[2]["untracked_detections"]), 1)

    def test_atomic_metadata_and_existing_temporary_preserved(self):
        path = self.root / "metadata.json"
        write_json(path, {"state": "running"})
        write_json(path, {"state": "completed"})
        self.assertEqual(json.loads(path.read_text()), {"state": "completed"})
        temporary = self.root / "metadata.json.tmp"
        temporary.write_text("existing")
        with self.assertRaises(FileExistsError):
            write_json(path, {})
        self.assertEqual(temporary.read_text(), "existing")
        self.assertEqual(json.loads(path.read_text()), {"state": "completed"})

    def test_nonfinite_metadata_rejected_without_destroying_prior_result(self):
        path = self.root / "metadata.json"
        write_json(path, {"valid": True})
        with self.assertRaises(ValueError):
            write_json(path, {"value": float("nan")})
        self.assertEqual(json.loads(path.read_text()), {"valid": True})
        self.assertFalse(path.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
