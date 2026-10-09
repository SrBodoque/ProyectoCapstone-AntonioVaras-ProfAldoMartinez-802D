"""FastTracker integrado REAL: API y cajas sintéticas, sin cámaras ni pesos."""

import unittest
from types import SimpleNamespace

from src.config import load_tracker_config, resolve_tracker_path
from src.track_fast import FASTTRACK_CONFIG


class FastTrackerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.detector import _load_yolo
        _load_yolo()
        import numpy as np
        import torch
        from ultralytics.engine.results import Boxes
        from ultralytics.trackers.fast_tracker import FASTTracker
        from ultralytics.trackers.track import TRACKER_MAP, on_predict_start
        cls.np, cls.Boxes, cls.FASTTracker, cls.torch = np, Boxes, FASTTracker, torch
        cls.TRACKER_MAP = TRACKER_MAP
        cls.start_predictor = staticmethod(on_predict_start)
        cls.path = resolve_tracker_path(FASTTRACK_CONFIG)
        cls.params = load_tracker_config(cls.path)

    def setUp(self):
        self.engine = self.FASTTracker(SimpleNamespace(**self.params))

    def update(self, rows):
        boxes = self.Boxes(self.np.array(rows, dtype=self.np.float32).reshape(-1, 6), (720, 1280))
        return self.engine.update(boxes)

    def test_real_api_registers_and_initializes_fasttrack_without_reid(self):
        self.assertIs(self.TRACKER_MAP["fasttrack"], self.FASTTracker)
        predictor = SimpleNamespace(args=SimpleNamespace(task="detect", tracker=str(self.path)),
                                    device=self.torch.device("cpu"), dataset=SimpleNamespace(bs=1, mode="image"))
        self.start_predictor(predictor, persist=True)
        self.assertIs(type(predictor.trackers[0]), self.FASTTracker)
        self.assertFalse(hasattr(predictor.trackers[0], "encoder"))
        self.assertFalse(hasattr(predictor, "_hook"))
        first = predictor.trackers[0]
        self.start_predictor(predictor, persist=True)
        self.assertIs(predictor.trackers[0], first)

    def test_two_tracks_keep_ids_in_synthetic_motion(self):
        first = self.update([[10, 20, 100, 200, .9, 0], [300, 20, 390, 200, .9, 0]])
        ids = first[:, 4].tolist()
        self.assertEqual(len(set(ids)), 2)
        for x in range(1, 8):
            result = self.update([[10 + x, 20, 100 + x, 200, .9, 0], [300 + x, 20, 390 + x, 200, .9, 0]])
            self.assertEqual(result[:, 4].tolist(), ids)

    def test_empty_frame_and_reappearance_are_supported(self):
        identifier = self.update([[10, 20, 100, 200, .9, 0]])[0, 4]
        self.assertEqual(len(self.update([])), 0)
        result = self.update([[11, 20, 101, 200, .9, 0]])
        self.assertEqual(result[0, 4], identifier)

    def test_sessions_start_with_independent_state(self):
        self.update([[10, 20, 100, 200, .9, 0]])
        other = self.FASTTracker(SimpleNamespace(**self.params))
        self.assertEqual(other.frame_id, 0)
        self.assertEqual(other.tracked_stracks, [])
        self.assertIsNot(self.engine.tracked_stracks, other.tracked_stracks)

    def test_rollback_history_is_bounded(self):
        for x in range(100):
            self.update([[10 + x, 20, 100 + x, 200, .9, 0]])
        history = self.engine.tracked_stracks[0].mean_history
        self.assertLessEqual(len(history), self.engine._history_len)
        self.assertEqual(history.maxlen, self.engine._history_len)


if __name__ == "__main__":
    unittest.main()
