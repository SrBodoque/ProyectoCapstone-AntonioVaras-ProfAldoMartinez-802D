"""ByteTrack REAL con cajas sintéticas: sin modelo, webcam, descargas o imágenes."""
import unittest
from types import SimpleNamespace

from src.config import load_tracking_config, load_bytetrack_config, resolve_tracker_path


class ByteTrackIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.detector import _load_yolo
        _load_yolo()  # Privacidad antes del import de Ultralytics; no instancia un modelo.
        import numpy as np
        from ultralytics.engine.results import Boxes
        from ultralytics.trackers.byte_tracker import BYTETracker
        cls.np, cls.Boxes, cls.BYTETracker = np, Boxes, BYTETracker
        cls.params = load_bytetrack_config(resolve_tracker_path(load_tracking_config()['tracker_config']))

    def setUp(self):
        self.tracker = self.BYTETracker(SimpleNamespace(**self.params))

    def update(self, rows):
        boxes = self.Boxes(self.np.array(rows, dtype=self.np.float32).reshape(-1, 6), (720, 1280))
        return self.tracker.update(boxes)

    def test_two_moving_tracks_and_brief_occlusion(self):
        first = self.update([[10, 20, 100, 200, .9, 0], [300, 20, 390, 200, .9, 0]])
        ids = first[:, 4].tolist()
        self.assertEqual(len(set(ids)), 2)
        for x in range(1, 8):
            current = self.update([[10+x, 20, 100+x, 200, .9, 0], [300+x, 20, 390+x, 200, .9, 0]])
            self.assertEqual(current[:, 4].tolist(), ids)
        self.assertEqual(len(self.update([])), 0)
        recovered = self.update([[18, 20, 108, 200, .9, 0], [308, 20, 398, 200, .9, 0]])
        self.assertEqual(recovered[:, 4].tolist(), ids)

    def test_second_association_can_use_low_score_boxes(self):
        # Prueba del motor, NO del filtro YOLO configurado a .65.
        first = self.update([[10, 20, 100, 200, .9, 0]])
        low = self.update([[11, 20, 101, 200, .2, 0]])
        self.assertEqual(first[0, 4], low[0, 4])
        self.assertAlmostEqual(float(low[0, 5]), .2, places=5)

    def test_lost_track_expires_and_reentry_gets_new_id(self):
        first = self.update([[10, 20, 100, 200, .9, 0]])[0, 4]
        for _ in range(self.params['track_buffer'] + 3):
            self.update([])
        self.update([[10, 20, 100, 200, .9, 0]])  # Nuevo track sin confirmar.
        confirmed = self.update([[10, 20, 100, 200, .9, 0]])
        self.assertNotEqual(first, confirmed[0, 4])

    def test_static_false_detection_is_not_artificially_removed(self):
        # Una caja sintética persistente NO demuestra reconocimiento de una cama.
        first = self.update([[50, 50, 200, 300, .8, 0]])[0, 4]
        for _ in range(100):
            self.assertEqual(self.update([[50, 50, 200, 300, .8, 0]])[0, 4], first)


if __name__ == '__main__':
    unittest.main()
