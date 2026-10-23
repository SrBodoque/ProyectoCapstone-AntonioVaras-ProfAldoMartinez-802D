"""ByteTrack real 8.4.163 con cajas sintéticas; sin modelo, webcam ni GPU.

Requiere las dependencias del proyecto. Una dependencia ausente es un error
visible de entorno, no un test aprobado ni una simulación del motor.
"""

import unittest
from importlib.metadata import version
from types import SimpleNamespace

from src.config import load_tracker_config, resolve_tracker_path
from src.track_recovery import RECOVERY_CONFIG


class RecoveryByteTrackIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.detector import _load_yolo
        _load_yolo()
        import numpy as np
        import torch
        from ultralytics.engine.results import Boxes
        from ultralytics.trackers.byte_tracker import BYTETracker
        from ultralytics.trackers.track import TRACKER_MAP, on_predict_start
        cls.np, cls.Boxes, cls.BYTETracker, cls.torch = np, Boxes, BYTETracker, torch
        cls.mapping = TRACKER_MAP
        cls.start_predictor = staticmethod(on_predict_start)
        cls.path = resolve_tracker_path(RECOVERY_CONFIG)
        cls.params = load_tracker_config(cls.path)

    def setUp(self):
        self.engine = self.BYTETracker(SimpleNamespace(**self.params))

    def update(self, rows):
        boxes = self.Boxes(self.np.array(rows, dtype=self.np.float32).reshape(-1, 6), (720, 1280))
        return self.engine.update(boxes)

    def box(self, score, x=10):
        return [x, 20, x + 90, 200, score, 0]

    def test_exact_version_and_real_callback_initialize_bytetrack_without_reid(self):
        self.assertEqual(version("ultralytics"), "8.4.163")
        self.assertIs(self.mapping["bytetrack"], self.BYTETracker)
        predictor = SimpleNamespace(args=SimpleNamespace(task="detect", tracker=str(self.path)),
                                    device=self.torch.device("cpu"), dataset=SimpleNamespace(bs=1, mode="image"))
        self.start_predictor(predictor, persist=True)
        self.assertIs(type(predictor.trackers[0]), self.BYTETracker)
        self.assertEqual(predictor.trackers[0].args.new_track_thresh, .65)
        self.assertFalse(hasattr(predictor.trackers[0], "encoder"))
        first = predictor.trackers[0]
        self.start_predictor(predictor, persist=True)
        self.assertIs(predictor.trackers[0], first)

    def test_weak_detections_alone_never_start_tracks(self):
        for score in (.15, .25, .35, .45, .55, .60, .649):
            for _ in range(3):
                self.assertEqual(len(self.update([self.box(score)])), 0)
                self.assertEqual(self.engine.tracked_stracks, [])
                self.assertEqual(self.engine.lost_stracks, [])

    def test_weak_detection_continues_active_id_without_new_weak_track(self):
        identifier = self.update([self.box(.90)])[0, 4]
        for offset, score in enumerate((.35, .15, .60, .25), 1):
            output = self.update([self.box(score, 10 + offset), self.box(.40, 500)])
            self.assertEqual(len(output), 1)
            self.assertEqual(output[0, 4], identifier)
            self.assertAlmostEqual(float(output[0, 5]), score, places=5)
            self.assertEqual(len(self.engine.tracked_stracks), 1)

    def test_lost_track_not_reactivated_by_low_confidence_but_high_can_match(self):
        identifier = self.update([self.box(.90)])[0, 4]
        self.assertEqual(len(self.update([])), 0)
        self.assertEqual(len(self.update([self.box(.35)])), 0)
        self.assertEqual([t.track_id for t in self.engine.lost_stracks], [identifier])
        restored = self.update([self.box(.90)])
        self.assertEqual(restored[0, 4], identifier)

    def test_equal_low_threshold_is_not_in_second_association(self):
        self.update([self.box(.90)])
        self.assertEqual(len(self.update([self.box(.10)])), 0)
        self.assertEqual(len(self.engine.lost_stracks), 1)

    def test_equal_high_threshold_can_start_a_track(self):
        output = self.update([self.box(.65)])
        self.assertEqual(len(output), 1)
        self.assertGreater(output[0, 4], 0)

    def test_unconfirmed_new_track_is_not_confirmed_by_low_detection(self):
        self.update([])
        self.assertEqual(len(self.update([self.box(.90)])), 0)
        self.assertEqual(len(self.engine.tracked_stracks), 1)
        self.assertFalse(self.engine.tracked_stracks[0].is_activated)
        self.assertEqual(len(self.update([self.box(.35)])), 0)
        self.assertEqual(self.engine.tracked_stracks, [])

    def test_high_confidence_static_box_is_not_artificially_removed(self):
        identifier = self.update([self.box(.90)])[0, 4]
        for _ in range(5):
            self.assertEqual(self.update([self.box(.90)])[0, 4], identifier)
        # Caja sintética: no demuestra que YOLO distinga personas y objetos.


if __name__ == "__main__":
    unittest.main()
