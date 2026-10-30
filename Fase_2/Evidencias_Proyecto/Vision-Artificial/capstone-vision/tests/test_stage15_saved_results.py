"""Indexación offline, compatibilidad, entradas parciales y rutas trasladadas."""

import json
import unittest
from pathlib import Path

from src.saved_results import ResultsError, load_case, select_case, validate_video
from stage15_test_support import box, row, write_case
from video_test_support import temporary_directory


class SavedResultsTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.video = self.root / "video.mp4"
        self.video.write_bytes(b"synthetic hash fixture, not a real video")

    def case(self, rows=None, **changes):
        return write_case(self.root / "case", self.video, rows, **changes)

    def test_out_of_order_missing_and_empty_frames_are_distinct(self):
        case = load_case(self.case([row(3, [box(2)]), row(0)]))
        self.assertEqual(case.frame(3).tracks[0].track_id, 2)
        self.assertTrue(case.frame(0).available)
        self.assertEqual(case.frame(0).tracks, ())
        self.assertFalse(case.frame(1).available)
        self.assertTrue(any("desordenado" in n for n in case.notices.messages))
        self.assertTrue(any("Faltan registros" in n for n in case.notices.messages))

    def test_multiple_ids_and_optional_values(self):
        missing = dict(x1=3, y1=4, x2=30, y2=40)
        path = self.case([row(0, [box(1, None), box(2), missing])])
        case = load_case(path)
        self.assertEqual([o.track_id for o in case.frame(0).tracks], [1, 2])
        self.assertIsNone(case.frame(0).tracks[0].confidence)
        self.assertEqual(len(case.frame(0).untracked), 1)

    def test_invalid_coordinates_are_skipped_and_invalid_confidence_is_optional(self):
        invalid = dict(x1=30, y1=0, x2=2, y2=20)
        data = row(0, [invalid, box(2, -1), dict(x1=-20, y1=-10, x2=200, y2=170, track_id=3)])
        case = load_case(self.case([data]))
        self.assertEqual([o.track_id for o in case.frame(0).tracks], [2, 3])
        self.assertIsNone(case.frame(0).tracks[0].confidence)
        self.assertEqual(case.frame(0).tracks[1].x1, -20)
        self.assertGreater(case.notices.count, 0)

    def test_jsonl_corrupt_truncated_or_wrong_shape_rejected(self):
        for i, text in enumerate(('{"frame_index":', '{"frame_index":0}\n{', '[]',
                                  '{"frame_index":true}', '{"frame_index":-1}',
                                  '{"frame_index":0,"tracks":{}}', '{"frame_index":0,"x":NaN}',
                                  '{"frame_index":0,"frame_index":1}')):
            with self.subTest(text=text):
                path = write_case(self.root / str(i), self.video)
                (path / "predictions.jsonl").write_text(text, encoding="utf-8")
                with self.assertRaises(ResultsError):
                    load_case(path)

    def test_duplicate_frame_or_id_is_ambiguous(self):
        for i, rows in enumerate(([row(0), row(0)], [row(0, [box(1), box(1)])])):
            with self.subTest(rows=rows), self.assertRaises(ResultsError):
                load_case(write_case(self.root / str(i), self.video, rows))

    def test_large_index_does_not_allocate_missing_frame_range(self):
        case = load_case(self.case([row(10**20)]))
        self.assertEqual(len(case.frames), 1)
        with self.assertRaises(ResultsError):
            validate_video(case, dict(width=160, height=160, reported_frames=20, reported_fps=25))

    def test_valid_final_line_without_newline_and_blank_lines(self):
        path = self.case()
        (path / "predictions.jsonl").write_text('\n{"frame_index":0}\n\n{"frame_index":1}', encoding="utf-8")
        self.assertEqual(sorted(load_case(path).frames), [0, 1])

    def test_empty_or_partial_results_warn(self):
        case = load_case(self.case([], status="interrupted"))
        self.assertFalse(case.frame(0).available)
        self.assertTrue(any("parcial" in n for n in case.notices.messages))

    def test_historical_absolute_path_ignored_when_hash_matches(self):
        path = self.case(input_path="Z:\\deleted\\old.mp4")
        renamed = self.root / "renamed.mp4"
        renamed.write_bytes(self.video.read_bytes())
        video, case = select_case(path, renamed)
        self.assertEqual(video, renamed.resolve())
        self.assertEqual(case.directory, path.resolve())

    def test_run_directory_selection_is_explicit_and_unique(self):
        directory = self.root / "run"
        path = write_case(directory / "a", self.video)
        other_video = self.root / "other.mp4"
        other_video.write_bytes(b"other fixture")
        write_case(directory / "b", other_video)
        self.assertEqual(select_case(directory, self.video)[1].directory, path.resolve())
        write_case(directory / "duplicate", self.video)
        with self.assertRaisesRegex(ResultsError, "único"):
            select_case(directory, self.video)

    def test_wrong_hash_missing_video_missing_results_and_invalid_hash_fail(self):
        path = self.case()
        self.video.write_bytes(b"changed fixture")
        with self.assertRaises(ResultsError):
            select_case(path, self.video)
        with self.assertRaises(ResultsError):
            select_case(path, self.root / "missing.mp4")
        with self.assertRaises(ResultsError):
            select_case(self.root / "missing", self.video)
        metadata = json.loads((path / "metadata.json").read_text())
        metadata["input_sha256"] = "invalid"
        (path / "metadata.json").write_text(json.dumps(metadata))
        with self.assertRaises(ResultsError):
            load_case(path)

    def test_missing_hash_requires_verifiable_geometry_and_warns(self):
        path = self.case(input_sha256=None)
        _, case = select_case(path, self.video)
        actual = dict(width=160, height=160, reported_frames=1, reported_fps=25)
        self.assertEqual(validate_video(case, actual), 25)
        self.assertTrue(any("Sin hash" in n for n in case.notices.messages))
        with self.assertRaises(ResultsError):
            validate_video(case, {**actual, "width": None})

    def test_dimensions_frame_count_fps_and_schema_validation(self):
        case = load_case(self.case())
        actual = dict(width=160, height=160, reported_frames=1, reported_fps=25)
        for changes in (dict(width=320), dict(height=80), dict(reported_frames=2)):
            with self.subTest(changes=changes), self.assertRaises(ResultsError):
                validate_video(case, {**actual, **changes})
        self.assertEqual(validate_video(case, {**actual, "reported_fps": 24}), 24)
        case.metadata["video"]["reported_fps"] = None
        with self.assertRaises(ResultsError):
            validate_video(case, {**actual, "reported_fps": None})
        data = json.loads((case.directory / "metadata.json").read_text())
        data["schema_version"] = 2
        (case.directory / "metadata.json").write_text(json.dumps(data))
        with self.assertRaises(ResultsError):
            load_case(case.directory)

    def test_no_ai_or_gui_imports_in_viewer_and_report_cli(self):
        import subprocess
        import sys
        code = "import sys; import src.view_results,src.processing_report; assert not any(n in sys.modules for n in ('torch','ultralytics','src.detector','src.tracker','cv2'))"
        result = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([sys.executable, "-B", "-m", "src.view_results", "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--results", result.stdout)


if __name__ == "__main__":
    unittest.main()
