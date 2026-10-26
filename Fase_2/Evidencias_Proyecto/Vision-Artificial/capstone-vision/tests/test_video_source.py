"""Lectura real de MP4 sintético y errores con capturas simuladas; sin YOLO."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.video_source import VideoSource, discover_cases, file_sha256
from video_test_support import temporary_directory


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_single_hash_and_stable_nonrecursive_directory(self):
        (self.root / "z.MP4").write_bytes(b"z")
        (self.root / "A.mp4").write_bytes(b"a")
        (self.root / "ignored.mov").touch()
        (self.root / "nested").mkdir()
        (self.root / "nested/other.mp4").touch()
        cases = discover_cases(directory=self.root)
        self.assertEqual([c.path.name for c in cases], ["A.mp4", "z.MP4"])
        self.assertEqual(cases, discover_cases(directory=self.root))
        self.assertEqual(cases[0].sha256, file_sha256(cases[0].path))
        self.assertEqual(len(discover_cases(video=cases[1].path)), 1)

    def test_invalid_sources(self):
        for kwargs in ({}, {"video": "x", "directory": "x"},
                       {"video": "https://example.org/a.mp4"},
                       {"video": "\\\\server\\a.mp4"},
                       {"video": self.root / "missing.mp4"}, {"directory": self.root}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                discover_cases(**kwargs)

    def test_identical_content_has_distinct_case_ids(self):
        for name in ("a.mp4", "b.mp4"):
            (self.root / name).write_bytes(b"same")
        cases = discover_cases(directory=self.root)
        self.assertEqual(cases[0].sha256, cases[1].sha256)
        self.assertNotEqual(cases[0].case_id, cases[1].case_id)


class SourceTests(unittest.TestCase):
    def run_source(self, rows, expected, *, raises=None):
        import cv2
        capture = MagicMock()
        capture.isOpened.return_value = True
        capture.getBackendName.return_value = "mock"
        capture.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FRAME_COUNT: expected, cv2.CAP_PROP_FPS: 25,
            cv2.CAP_PROP_FRAME_WIDTH: 64, cv2.CAP_PROP_FRAME_HEIGHT: 48,
        }.get(prop, 0)
        capture.read.side_effect = rows
        source = VideoSource(Path("mock.mp4"))
        with patch.object(cv2, "VideoCapture", return_value=capture):
            if raises:
                with self.assertRaises(raises), source:
                    list(source)
                packets = []
            else:
                with source:
                    packets = list(source)
        capture.release.assert_called_once()
        return source, packets

    def test_completion_empty_early_unknown_excess(self):
        import numpy as np
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        cases = ((2, 2, "completed"), (0, 2, "failed"), (1, 2, "failed"),
                 (2, 0, "incomplete"), (2, 1, "incomplete"))
        for count, expected, status in cases:
            with self.subTest(count=count, expected=expected):
                source, packets = self.run_source([(True, frame)] * count + [(False, None)], expected)
                self.assertEqual(source.status, status)
                self.assertEqual([p.index for p in packets], list(range(count)))
                if count > 1:
                    self.assertEqual(packets[1].timestamp_source, "index/reported_fps")
                    self.assertEqual(packets[1].timestamp_ms, 40)

    def test_invalid_frame_and_exception_release(self):
        self.run_source([(True, None)], 1, raises=RuntimeError)
        self.run_source([RuntimeError("decoder")], 1, raises=RuntimeError)
        self.run_source([KeyboardInterrupt()], 1, raises=KeyboardInterrupt)

    def test_open_failure_release(self):
        import cv2
        capture = MagicMock()
        capture.isOpened.return_value = False
        with patch.object(cv2, "VideoCapture", return_value=capture):
            with self.assertRaises(RuntimeError), VideoSource(Path("bad.mp4")):
                pass
        capture.release.assert_called_once()


class RealMp4Tests(unittest.TestCase):
    def test_actual_decoder_preserves_frame_order_and_end(self):
        import cv2
        import numpy as np
        with temporary_directory() as temp:
            path = Path(temp) / "synthetic.mp4"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
            if not writer.isOpened():
                writer.release()
                self.skipTest("No hay encoder MP4 local: integración de codec pendiente.")
            try:
                for value in (10, 80, 160):
                    writer.write(np.full((48, 64, 3), value, dtype=np.uint8))
            finally:
                writer.release()
            with VideoSource(path) as source:
                packets = list(source)
            self.assertEqual(source.status, "completed")
            self.assertEqual(len(packets), 3)
            self.assertEqual([p.index for p in packets], [0, 1, 2])
            self.assertEqual(sorted(float(p.frame.mean()) for p in packets),
                             [float(p.frame.mean()) for p in packets])


if __name__ == "__main__":
    unittest.main()
