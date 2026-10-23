"""Integración REAL 8.4.163. No instala dependencias, no usa webcam ni guarda imágenes.

Motor: cajas/features sintéticas con BoT-SORT real (no evidencia de extracción IA).
Inferencia: pesos oficiales locales y bus.jpg distribuida por Ultralytics.
La ausencia de dependencias/pesos se registra como omitida, nunca como aprobada.
"""

import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from src.config import PROJECT_ROOT, load_detection_config, load_tracking_config, load_tracker_config, resolve_tracker_path
from src.track_botsort_reid import BOTSORT_CONFIG


def require_runtime():
    missing = [name for name in ("cv2", "torch", "torchvision", "ultralytics", "lap")
               if importlib.util.find_spec(name) is None]
    if missing:
        raise unittest.SkipTest("Integración real pendiente: faltan " + ", ".join(missing))
    from src.detector import _load_yolo
    _load_yolo()
    from src.reid_diagnostics import _runtime
    return _runtime()  # Una versión incorrecta es un error visible, no un skip.


class RealBOTSORTTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.BOTSORT = require_runtime()
        import numpy as np
        import torch
        from ultralytics.engine.results import Boxes
        cls.np, cls.torch, cls.Boxes = np, torch, Boxes
        cls.path = resolve_tracker_path(BOTSORT_CONFIG)
        cls.params = load_tracker_config(cls.path)

    def setUp(self):
        self.engine = self.BOTSORT(NS(**self.params, device="cpu"))

    def boxes(self, x=10):
        return self.Boxes(self.np.array([[x, 20, x + 90, 200, .9, 0]], dtype=self.np.float32), (240, 640))

    def features(self):
        return self.torch.tensor([[1., 0., 0., 0.]])

    def test_official_yaml_loader_and_real_type(self):
        from ultralytics.utils import YAML
        from ultralytics.trackers.track import TRACKER_MAP
        self.assertEqual(YAML.load(str(self.path)), self.params)
        self.assertIs(type(self.engine), TRACKER_MAP["botsort"])
        self.assertIs(self.engine.args.with_reid, True)
        self.assertTrue(callable(self.engine.encoder))

    def test_gmc_none_is_accepted_and_identity(self):
        warp = self.engine.gmc.apply(self.np.zeros((240, 640, 3), dtype=self.np.uint8))
        self.np.testing.assert_allclose(warp, self.np.eye(2, 3))

    def test_native_encoder_transfers_synthetic_features_to_botracks(self):
        from src.reid_diagnostics import _check_features
        items = self.engine.init_track(self.boxes(), self.features())
        self.assertEqual(len(items), 1); _check_features(items)
        self.np.testing.assert_allclose(items[0].curr_feat, [1, 0, 0, 0])

    def test_real_embedding_distance_participates_and_changes_cost(self):
        from ultralytics.trackers.utils import matching
        a = self.engine.init_track(self.boxes(), self.features())
        b = self.engine.init_track(self.boxes(15), self.features())
        with patch.object(matching, "embedding_distance", wraps=matching.embedding_distance) as observed:
            with_appearance = self.engine.get_dists(a, b)
        observed.assert_called_once()
        self.engine.args.with_reid = False  # Solo control matemático del test, nunca YAML/app.
        without_appearance = self.engine.get_dists(a, b)
        self.assertLess(float(with_appearance[0, 0]), float(without_appearance[0, 0]))

    def test_proximity_still_blocks_distant_identical_features(self):
        a = self.engine.init_track(self.boxes(), self.features())
        b = self.engine.init_track(self.boxes(500), self.features())
        self.assertEqual(float(self.engine.get_dists(a, b)[0, 0]), 1.)

    def test_real_update_preserves_id_with_synthetic_features(self):
        frame = self.np.zeros((240, 640, 3), dtype=self.np.uint8)
        first = self.engine.update(self.boxes(), frame, feats=self.features())
        second = self.engine.update(self.boxes(12), frame, feats=self.features())
        self.assertEqual(first[0, 4], second[0, 4])
        self.assertIsNotNone(self.engine.tracked_stracks[0].curr_feat)

    def test_reset_clears_tracker_session_state(self):
        frame = self.np.zeros((240, 640, 3), dtype=self.np.uint8)
        self.engine.update(self.boxes(), frame, feats=self.features())
        self.engine.reset()
        self.assertEqual(self.engine.tracked_stracks, [])
        self.assertEqual(self.engine.lost_stracks, [])
        self.assertEqual(self.engine.removed_stracks, [])


class RealInferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.BOTSORT = require_runtime()
        missing = [p for p in (PROJECT_ROOT / "yolo26n.pt", PROJECT_ROOT / "yolo26n-cls.pt") if not p.is_file()]
        if missing:
            raise unittest.SkipTest("Inferencia real pendiente: requiere pesos oficiales locales yolo26n.pt y yolo26n-cls.pt en la raíz.")
        if Path.cwd().resolve() != PROJECT_ROOT:
            raise unittest.SkipTest("Ejecuta desde capstone-vision para resolver los pesos locales de apariencia.")
        import cv2
        import numpy as np
        from ultralytics.utils import ASSETS
        cls.np = np
        cls.sample = cv2.imread(str(ASSETS / "bus.jpg"))
        if cls.sample is None:
            raise unittest.SkipTest("Falta bus.jpg de ejemplo oficial; no se descargan fotografías personales.")
        from src.tracker import PersonTracker
        with patch("src.devices.load_device_preference", return_value="cpu"):
            cls.person = PersonTracker(load_detection_config(),
                                       {**load_tracking_config(), "tracker_config": BOTSORT_CONFIG})
        cls.person.track(np.zeros((240, 640, 3), dtype=np.uint8))

    def test_real_auto_resolution_encoder_and_device(self):
        diagnostics = self.person.reid_diagnostics
        self.assertIs(type(diagnostics.engine), self.BOTSORT)
        self.assertEqual(diagnostics.effective_model, "yolo26n-cls.pt")
        self.assertTrue(callable(diagnostics.engine.encoder))
        self.assertEqual(str(diagnostics.engine.encoder.model.predictor.device), "cpu")
        self.assertEqual(self.person.tracking_confidence, .65)

    def test_real_detection_extraction_and_association_on_two_frames(self):
        from ultralytics.trackers.utils import matching
        from src.reid_diagnostics import _check_features
        with patch.object(matching, "embedding_distance", wraps=matching.embedding_distance) as observed:
            self.person.track(self.sample.copy())
            output = self.person.track(self.sample.copy())
        self.assertGreater(len(output.tracks), 0, "La muestra no produjo personas con conf=0.65.")
        guard = self.person.reid_diagnostics
        self.assertTrue(guard.features_verified); self.assertTrue(guard.association_verified)
        self.assertTrue(any(len(c.args[0]) and len(c.args[1]) for c in observed.call_args_list))
        _check_features(guard.engine.tracked_stracks)

    def test_real_empty_frame_does_not_raise_extraction_failure(self):
        self.person.track(self.np.zeros((240, 640, 3), dtype=self.np.uint8))


if __name__ == "__main__":
    unittest.main()
