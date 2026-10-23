"""Contrato BoT-SORT y controles ReID con dobles explícitos; NO es inferencia real."""

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

import numpy as np

from src import detector, devices, reid_diagnostics as rd, track, tracker, track_botsort_reid as entry
from src.config import (PROJECT_ROOT, load_config, load_detection_config, load_tracking_config,
                        load_tracker_config, load_bytetrack_config, resolve_tracker_path)
from test_recovery import simulated_cv2, ui_and_capture


def configuration():
    return {**load_tracking_config(), "tracker_config": entry.BOTSORT_CONFIG}


def parameters():
    return load_tracker_config(resolve_tracker_path(entry.BOTSORT_CONFIG))


class ConfigTests(unittest.TestCase):
    def load(self, data, loader=load_tracker_config):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.yaml"
            path.write_text(json.dumps(data), encoding="utf-8")
            return loader(path)

    def test_exact_yaml_values(self):
        self.assertEqual(parameters(), dict(tracker_type="botsort", track_high_thresh=.25,
                         track_low_thresh=.10, new_track_thresh=.25, track_buffer=30,
                         match_thresh=.80, fuse_score=True, gmc_method="none",
                         proximity_thresh=.50, appearance_thresh=.80, with_reid=True, model="auto"))

    def test_missing_and_extra_fields_rejected(self):
        for key in parameters():
            data = parameters(); del data[key]
            with self.subTest(key=key), self.assertRaises(ValueError): self.load(data)
        with self.assertRaises(ValueError): self.load({**parameters(), "device": "cpu"})

    def test_threshold_types_ranges_and_finiteness(self):
        for key in ("track_high_thresh", "track_low_thresh", "new_track_thresh", "match_thresh",
                    "proximity_thresh", "appearance_thresh"):
            for value in (True, False, None, [], {}, "0.5", -.1, 1.1, float("nan"), float("inf")):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.load({**parameters(), key: value})

    def test_appearance_and_proximity_boundaries(self):
        for key in ("proximity_thresh", "appearance_thresh"):
            for value in (0, 1, .5):
                self.assertEqual(self.load({**parameters(), key: value})[key], value)

    def test_threshold_order(self):
        for changes in ({"track_low_thresh": .25}, {"track_low_thresh": .30}, {"new_track_thresh": .20}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.load({**parameters(), **changes})

    def test_reid_must_be_true_boolean(self):
        for value in (False, 0, 1, "true", None):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "with_reid"):
                self.load({**parameters(), "with_reid": value})

    def test_model_only_auto(self):
        for value in (None, True, [], "/tmp/model.pt", "../x.pt", "https://a/b.pt", "yolo26n-cls.pt", "x.onnx"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "model"):
                self.load({**parameters(), "model": value})

    def test_gmc_supported_values(self):
        for method in ("none", "sparseOptFlow", "orb", "sift", "ecc"):
            self.assertEqual(self.load({**parameters(), "gmc_method": method})["gmc_method"], method)
        for method in (None, False, {}, "auto", "unknown"):
            with self.assertRaisesRegex(ValueError, "gmc_method"):
                self.load({**parameters(), "gmc_method": method})

    def test_common_buffer_and_bool_remain_strict(self):
        for key, value in (("track_buffer", 0), ("track_buffer", True), ("track_buffer", 1.5),
                           ("track_buffer", 3001), ("fuse_score", 1), ("fuse_score", "true")):
            with self.assertRaises(ValueError): self.load({**parameters(), key: value})

    def test_old_trackers_reject_botsort_fields_and_wrapper_remains_byte_only(self):
        for filename in ("bytetrack_capstone.yaml", "fasttrack_capstone.yaml", "bytetrack_recovery_capstone.yaml"):
            original = load_tracker_config(resolve_tracker_path("config/" + filename))
            self.assertEqual(self.load(original), original)
            with self.assertRaises(ValueError): self.load({**original, "with_reid": True})
        with self.assertRaises(ValueError): self.load(parameters(), load_bytetrack_config)

    def test_paths_remain_project_local(self):
        for path in ("/tmp/tracker.yaml", "../outside.yaml", "C:/x.yaml", "http://example/x.yaml"):
            with self.assertRaises(ValueError): resolve_tracker_path(path)
        self.assertEqual(resolve_tracker_path(entry.BOTSORT_CONFIG), PROJECT_ROOT / entry.BOTSORT_CONFIG)

    def test_entrypoint_delegates_without_recovery_override(self):
        with patch.object(track, "main", return_value=0) as main:
            self.assertEqual(entry.main(), 0)
        main.assert_called_once_with(tracker_config=entry.BOTSORT_CONFIG, tracker_label="BoT-SORT + ReID")

    def test_light_imports_no_prompt_ai_or_preference_writes(self):
        code = '''
import sys
sys.dont_write_bytecode = True
from pathlib import Path
from unittest.mock import patch
before = {p: p.read_bytes() for p in Path("config").iterdir() if p.is_file()}
with patch("builtins.input", side_effect=AssertionError("input")), patch("os.replace", side_effect=AssertionError("write")):
    import src.track, src.track_fast, src.track_recovery, src.track_botsort_reid
assert not any(m in sys.modules for m in ("torch", "ultralytics", "cv2", "yaml", "numpy"))
assert before == {p: p.read_bytes() for p in Path("config").iterdir() if p.is_file()}
'''
        result = subprocess.run([sys.executable, "-c", code], cwd=PROJECT_ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.model = MagicMock(names={0: "person"})
        self.result = MagicMock()
        self.result.boxes.is_track = True
        self.result.boxes.data.cpu.return_value.tolist.return_value = [[10, 20, 100, 200, 7, .9, 0]]
        self.result.speed = {"inference": 10}
        self.model.track.return_value = [self.result]
        self.factory = MagicMock(return_value=self.model)
        for replacement in (patch.object(detector, "_load_yolo", return_value=self.factory),
                            patch.object(devices, "load_device_preference", return_value=None),
                            patch.object(tracker, "ReIDDiagnostics")):
            replacement.start(); self.addCleanup(replacement.stop)
        self.guard = tracker.ReIDDiagnostics.return_value
        self.frame = NS(shape=(720, 1280, 3), size=100)

    def make(self, **kwargs):
        return tracker.PersonTracker(load_detection_config(), configuration(), **kwargs)

    def test_confidence_model_class_and_single_detector_call_per_frame(self):
        instance = self.make()
        for _ in range(3): instance.track(self.frame)
        self.factory.assert_called_once_with(str(PROJECT_ROOT / "yolo26n.pt"), task="detect")
        self.assertEqual(self.model.track.call_count, 3)
        self.model.predict.assert_not_called()
        args = self.model.track.call_args.kwargs
        self.assertEqual((args["conf"], args["classes"], args["iou"], args["imgsz"]), (.65, [0], .7, 640))
        self.assertEqual(args["tracker"], str(PROJECT_ROOT / entry.BOTSORT_CONFIG))
        self.assertIs(args["persist"], True)
        self.assertEqual(self.guard.after_frame.call_count, 3)

    def test_save_and_export_flags_off(self):
        self.make().track(self.frame)
        for key in ("save", "save_txt", "save_conf", "save_crop", "show", "visualize", "augment", "stream"):
            self.assertIs(self.model.track.call_args.kwargs[key], False)
        self.assertNotIn("half", self.model.track.call_args.kwargs)

    def test_track_and_untracked_formats_and_alias_preserved(self):
        instance = self.make(); result = instance.track(self.frame)
        self.assertIs(instance.bytetrack_config, instance.tracker_params)
        self.assertEqual(instance.tracker_label, entry.BOTSORT_LABEL)
        self.assertEqual(result.tracks[0].track_id, 7)
        self.assertEqual(result.tracks[0].center, (55, 110))
        self.result.boxes.is_track = False
        self.result.boxes.data.cpu.return_value.tolist.return_value = [[10, 20, 100, 200, .9, 0]]
        result = instance.track(self.frame)
        self.assertFalse(result.tracks)
        self.assertEqual(len(result.untracked_detections), 1)

    def test_recovery_override_rejected_only_in_new_mode(self):
        for value in (.10, .65):
            with self.assertRaisesRegex(ValueError, "ningún override"):
                self.make(tracking_confidence_override=value)
        self.factory.assert_not_called()
        with self.assertRaisesRegex(ValueError, "confianza general 0.65"):
            tracker.PersonTracker({**load_detection_config(), "confidence_threshold": .10}, configuration())

    def test_cpu_and_cuda_preferences_use_shared_resolver(self):
        for preference, available, expected in ((None, False, "cpu"), ("cpu", True, "cpu"),
                                                ("cuda:0", True, "cuda:0"), ("cuda:0", False, "cpu")):
            torch = MagicMock(); torch.version.cuda = "13.2" if available else None
            torch.cuda.is_available.return_value = available
            torch.cuda.device_count.return_value = int(available)
            torch.ones.return_value.item.return_value = 2
            with self.subTest(preference=preference, available=available), \
                    patch.object(devices, "load_device_preference", return_value=preference), \
                    patch.object(devices, "load_torch", return_value=torch), \
                    patch.object(detector, "resolve_effective_device", wraps=devices.resolve_effective_device) as resolve:
                self.make().track(self.frame)
                resolve.assert_called_once_with("cpu")
                self.assertEqual(self.model.track.call_args.kwargs["device"], expected)
                tracker.ReIDDiagnostics.assert_called_with(self.model, expected)

    def test_diagnostic_error_stops_tracking(self):
        self.guard.after_frame.side_effect = RuntimeError("ReID no produjo características")
        with self.assertRaisesRegex(RuntimeError, "ReID no produjo"):
            self.make().track(self.frame)

    def test_prior_modes_never_attach_reid_and_keep_confidence(self):
        from src import track_fast, track_recovery
        for config, override, confidence in ((load_tracking_config(), None, .65),
                ({**load_tracking_config(), "tracker_config": track_fast.FASTTRACK_CONFIG}, None, .65),
                ({**load_tracking_config(), "tracker_config": track_recovery.RECOVERY_CONFIG}, .10, .10)):
            tracker.PersonTracker(load_detection_config(), config,
                                  tracking_confidence_override=override).track(self.frame)
            self.assertEqual(self.model.track.call_args.kwargs["conf"], confidence)
        tracker.ReIDDiagnostics.assert_not_called()
        self.model.predict.return_value = [NS(boxes=None, speed={})]
        detector.PersonDetector(load_detection_config()).detect(self.frame)
        self.assertEqual(self.model.predict.call_args.kwargs["conf"], .65)

    def test_selected_camera_and_in_memory_config(self):
        before = {p: p.read_bytes() for p in (PROJECT_ROOT / "config").iterdir() if p.is_file()}
        ui, _, _ = ui_and_capture()
        with patch.dict(sys.modules, {"cv2": ui}), patch.object(track.sys, "platform", "win32"), \
                patch.object(track, "run_tracking") as run, patch("builtins.input", side_effect=AssertionError):
            self.assertEqual(entry.main(), 0)
        self.assertEqual(run.call_args.args[1:4], (load_config(), load_detection_config(), configuration()))
        self.assertEqual(run.call_args.kwargs, {"tracker_label": entry.BOTSORT_LABEL})
        self.assertEqual(before, {p: p.read_bytes() for p in (PROJECT_ROOT / "config").iterdir() if p.is_file()})

    def test_all_exit_paths_release_camera_and_windows(self):
        for scenario in ("q", "esc", "close", "ctrl_c", "load", "reid", "read", "ui"):
            with self.subTest(scenario=scenario):
                ui, capture, frame = ui_and_capture()
                self.model.track.side_effect = None; self.factory.side_effect = None
                self.guard.after_frame.side_effect = None
                expected = None
                if scenario == "esc": ui.waitKey.return_value = 27
                if scenario == "close":
                    ui.waitKey.return_value = -1; ui.getWindowProperty.return_value = 0
                if scenario == "ctrl_c":
                    self.model.track.side_effect = KeyboardInterrupt(); expected = KeyboardInterrupt
                if scenario == "load":
                    self.factory.side_effect = RuntimeError("modelo"); expected = RuntimeError
                if scenario == "reid":
                    self.guard.after_frame.side_effect = RuntimeError("encoder"); expected = RuntimeError
                if scenario == "read":
                    ui.waitKey.return_value = -1; capture.read.side_effect = [(True, frame), (False, None)]
                    expected = RuntimeError
                if scenario == "ui": ui.imshow.side_effect = ui.error("GUI"); expected = ui.error
                with simulated_cv2(ui):
                    args = (ui, load_config(), load_detection_config(), configuration())
                    if expected:
                        with self.assertRaises(expected): track.run_tracking(*args, tracker_label=entry.BOTSORT_LABEL)
                    else: track.run_tracking(*args, tracker_label=entry.BOTSORT_LABEL)
                capture.release.assert_called_once(); ui.destroyAllWindows.assert_called_once()

    def test_new_label_metrics_colors_and_trails(self):
        ui, _, _ = ui_and_capture(); ui.waitKey.side_effect = [-1, ord("q")]
        with simulated_cv2(ui):
            track.run_tracking(ui, load_config(), load_detection_config(), configuration(), tracker_label=entry.BOTSORT_LABEL)
        self.assertIn(entry.BOTSORT_LABEL, ui.namedWindow.call_args.args[0])
        labels = [c.args[1] for c in ui.putText.call_args_list]
        for metric in ("Tracks activos:", "FPS pipeline:", "Inferencia YOLO:", "YOLO + tracking:", "Cajas sin ID:"):
            self.assertTrue(any(metric in label for label in labels))
        self.assertEqual(ui.rectangle.call_args.args[-2:], ((0, 220, 0), 2))
        self.assertGreater(ui.line.call_count, 0)


def feature_track():
    return NS(curr_feat=np.array([1., 0.], dtype=np.float32),
              smooth_feat=np.array([1., 0.], dtype=np.float32), frame_id=1)


class SimulatedBOTSORT:
    """Doble del contrato, deliberadamente separado de las pruebas de integración."""
    def __init__(self):
        self.args = NS(**parameters()); self.args.model = "yolo26n-cls.pt"
        self.encoder = MagicMock(model=NS(task="classify", ckpt_path="/weights/yolo26n-cls.pt",
                                          predictor=NS(device="cpu")))
        self.tracked_stracks = []; self.lost_stracks = []; self.frame_id = 1
        self.init_calls = self.distance_calls = 0

    def init_track(self, results, img=None):
        self.init_calls += 1
        return [feature_track() for _ in results]

    def get_dists(self, tracks, detections):
        self.distance_calls += 1
        return np.zeros((len(tracks), len(detections)))


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.model = MagicMock(predictor=None)
        with patch.object(rd, "_runtime", return_value=SimulatedBOTSORT):
            self.guard = rd.ReIDDiagnostics(self.model, "cpu")
        self.engine = SimulatedBOTSORT()
        self.predictor = NS(device="cpu", trackers=[self.engine],
                            results=[NS(boxes=NS(is_track=False, conf=np.array([.9])))])

    def begin(self):
        self.guard.on_batch_start(self.predictor); self.guard.before_association(self.predictor)

    def test_version_mismatch_rejected(self):
        modules = {"ultralytics": NS(__version__="8.0.0"),
                   "ultralytics.trackers.bot_sort": NS(BOTSORT=SimulatedBOTSORT)}
        with patch.dict(sys.modules, modules), self.assertRaisesRegex(RuntimeError, "8.4.163"):
            rd._runtime()

    def test_exact_version_loads_actual_import_contract(self):
        with patch.dict(sys.modules, {"ultralytics": NS(__version__="8.4.163"),
                       "ultralytics.trackers.bot_sort": NS(BOTSORT=SimulatedBOTSORT)}):
            self.assertIs(rd._runtime(), SimulatedBOTSORT)

    def test_callbacks_only_on_fresh_session(self):
        self.assertEqual([c.args[0] for c in self.model.add_callback.call_args_list],
                         ["on_predict_batch_start", "on_predict_postprocess_end"])
        with patch.object(rd, "_runtime", return_value=SimulatedBOTSORT), self.assertRaisesRegex(RuntimeError, "modelo nuevo"):
            rd.ReIDDiagnostics(MagicMock(predictor=NS()), "cpu")

    def test_wrong_tracker_or_multiple_streams_rejected(self):
        for engines in ([], [NS()], [self.engine, self.engine]):
            self.predictor.trackers = engines
            with self.assertRaisesRegex(RuntimeError, "BoT-SORT"): self.guard.on_batch_start(self.predictor)

    def test_reid_disabled_rejected(self):
        self.engine.args.with_reid = False
        with self.assertRaisesRegex(RuntimeError, "activado"): self.begin()

    def test_encoder_missing_rejected(self):
        self.engine.encoder = None
        with self.assertRaisesRegex(RuntimeError, "encoder"): self.begin()

    def test_effective_model_logged_only_after_initialization(self):
        with self.assertLogs(rd.LOGGER, level="INFO") as logs: self.begin()
        self.assertEqual(self.guard.effective_model, "yolo26n-cls.pt")
        self.assertIn("Encoder ReID inicializado", "\n".join(logs.output))
        self.assertFalse(self.guard.features_verified); self.assertFalse(self.guard.association_verified)

    def test_native_features_require_hook(self):
        self.engine.args.model = "auto"
        with self.assertRaisesRegex(RuntimeError, "hook"): self.begin()
        self.predictor._hook = object(); self.begin()
        self.assertEqual(self.guard.effective_model, "auto")

    def test_external_or_uninitialized_appearance_rejected(self):
        for field, value in (("task", "detect"), ("ckpt_path", "other.pt"), ("predictor", None)):
            original = getattr(self.engine.encoder.model, field)
            setattr(self.engine.encoder.model, field, value)
            with self.assertRaisesRegex(RuntimeError, "extractor de clasificación"): self.begin()
            setattr(self.engine.encoder.model, field, original)
        self.engine.args.model = "other.pt"
        with self.assertRaisesRegex(RuntimeError, "no admitido"): self.begin()

    def test_detector_and_encoder_devices_must_match_selection(self):
        self.predictor.device = "cuda:0"
        with self.assertRaisesRegex(RuntimeError, "detector"): self.begin()
        self.predictor.device = "cpu"; self.engine.encoder.model.predictor.device = "cuda:0"
        with self.assertRaisesRegex(RuntimeError, "encoder ReID"): self.begin()
        self.guard.expected_device = "cuda:1"; self.predictor.device = "cuda:1"
        self.engine.encoder.model.predictor.device = "cuda:1"; self.begin()

    def test_empty_frame_is_not_extraction_failure(self):
        self.predictor.results[0].boxes.conf = np.array([])
        self.begin(); self.engine.init_track([]); self.guard.after_frame()
        self.assertFalse(self.guard.features_verified); self.assertFalse(self.guard.association_verified)

    def test_features_and_association_have_separate_evidence(self):
        self.begin(); new = self.engine.init_track([1])
        self.engine.get_dists([], new); self.guard.after_frame()
        self.assertTrue(self.guard.features_verified); self.assertFalse(self.guard.association_verified)
        self.begin(); new = self.engine.init_track([1]); self.engine.get_dists([feature_track()], new)
        with self.assertLogs(rd.LOGGER, level="INFO") as logs: self.guard.after_frame()
        self.assertTrue(self.guard.association_verified)
        self.assertIn("ReID activo verificado", "\n".join(logs.output))
        self.assertEqual((self.engine.init_calls, self.engine.distance_calls), (2, 2))

    def test_missing_or_zero_nan_empty_features_fail(self):
        for value in (None, [], np.array([]), np.array([0., 0.]), np.array([np.nan]), np.array([np.inf]),
                      np.array([[1., 0.]]), np.array([1, 0]), np.array(["secret"])):
            with self.subTest(shape=getattr(value, "shape", None)), self.assertRaisesRegex(RuntimeError, "características válidas"):
                rd._check_features([NS(curr_feat=value, smooth_feat=value)])

    def test_invalid_encoder_output_detected_before_association(self):
        self.begin()
        with patch(__name__ + ".feature_track", return_value=NS(curr_feat=None, smooth_feat=None)):
            with self.assertRaisesRegex(RuntimeError, "características válidas"): self.engine.init_track([1])

    def test_missing_extraction_despite_detections_fails(self):
        self.begin()
        with self.assertRaisesRegex(RuntimeError, "no llegaron"): self.guard.after_frame()

    def test_missing_association_when_tracks_and_detections_exist_fails(self):
        self.engine.tracked_stracks = [feature_track()]
        self.begin(); self.engine.init_track([1])
        with self.assertRaisesRegex(RuntimeError, "no se verificó su asociación"): self.guard.after_frame()

    def test_callbacks_missing_or_wrong_order_fail(self):
        with self.assertRaisesRegex(RuntimeError, "controles ReID"): self.guard.after_frame()
        self.guard.on_batch_start(self.predictor)
        with self.assertRaisesRegex(RuntimeError, "antes de extraer"): self.engine.init_track([1])
        self.predictor.results[0].boxes.is_track = True
        with self.assertRaisesRegex(RuntimeError, "orden de callbacks"): self.guard.before_association(self.predictor)

    def test_observed_tracks_with_invalid_features_fail(self):
        self.begin(); self.engine.init_track([1])
        self.engine.tracked_stracks = [NS(frame_id=1, curr_feat=None, smooth_feat=None)]
        with self.assertRaisesRegex(RuntimeError, "características válidas"): self.guard.after_frame()

    def test_session_engine_replacement_rejected(self):
        self.begin(); self.engine.init_track([1]); self.guard.after_frame()
        self.predictor.trackers = [SimulatedBOTSORT()]
        with self.assertRaisesRegex(RuntimeError, "cambió"): self.guard.on_batch_start(self.predictor)

    def test_no_vectors_are_logged_or_copied_to_diagnostic_state(self):
        self.begin(); new = self.engine.init_track([1])
        self.engine.get_dists([feature_track()], new)
        with self.assertLogs(rd.LOGGER, level="INFO") as logs: self.guard.after_frame()
        self.assertNotIn("[1.", "\n".join(logs.output))
        self.assertFalse(any(isinstance(v, np.ndarray) for v in vars(self.guard).values()))


if __name__ == "__main__":
    unittest.main()
