"""Pruebas H3 sin webcam, red ni carga de pesos; integración real en otro archivo."""
import dataclasses
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import yaml

from src import camera, detector, diagnostics, track, tracker
from src.config import (PROJECT_ROOT, load_config, load_detection_config, load_tracking_config,
                        resolve_tracker_path, load_bytetrack_config)
from src.detector import Detection
from src.tracker import Track, FrameTracks, PersonTracker, TrackHistory


class TrackingConfigTests(unittest.TestCase):
    def setUp(self):
        self.config = load_tracking_config()
        self.params = load_bytetrack_config(resolve_tracker_path(self.config['tracker_config']))

    def test_baseline_and_bom(self):
        self.assertEqual(self.params, dict(tracker_type='bytetrack', track_high_thresh=.25,
                         track_low_thresh=.1, new_track_thresh=.25, track_buffer=30,
                         match_thresh=.8, fuse_score=True))
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'tracking.json'
            p.write_text(json.dumps(self.config), encoding='utf-8-sig')
            self.assertEqual(load_tracking_config(p), self.config)

    def test_other_directory(self):
        original = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                self.assertEqual(load_tracking_config(), self.config)
                self.assertEqual(load_bytetrack_config(resolve_tracker_path(self.config['tracker_config'])), self.params)
            finally:
                os.chdir(original)

    def test_json_invalid_missing_and_extra(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'tracking.json'
            with self.assertRaises(ValueError):
                load_tracking_config(p)
            for content in ('{', '[]', '{}', json.dumps({**self.config, 'extra': 1})):
                p.write_text(content)
                with self.subTest(content=content), self.assertRaises(ValueError):
                    load_tracking_config(p)

    def test_invalid_fields(self):
        cases = {'tracker_config': ['', None, 42, '/tmp/abs.yaml', 'C:/foo.yaml', '../escape.yaml',
                                    'config/missing.yaml', 'config/camera.json', 'config\\bytetrack.yaml'],
                 'persist': [False, 1, 'true', None], 'show_track_id': [1, 'false', None],
                 'show_trail': [0, 'true', None], 'trail_length': [0, -1, 301, True, 1.5, '30']}
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'tracking.json'
            for field, values in cases.items():
                for value in values:
                    p.write_text(json.dumps({**self.config, field: value}))
                    with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, field):
                        load_tracking_config(p)

    def test_visual_flags_and_length_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'tracking.json'
            for length in (1, 300):
                p.write_text(json.dumps({**self.config, 'trail_length': length,
                                         'show_track_id': False, 'show_trail': False}))
                self.assertEqual(load_tracking_config(p)['trail_length'], length)

    def test_yaml_missing_malformed_extra(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'tracker.yaml'
            with self.assertRaises(ValueError):
                load_bytetrack_config(p)
            for content in ('[', '[]', '{}', yaml.safe_dump({**self.params, 'with_reid': True})):
                p.write_text(content)
                with self.subTest(content=content), self.assertRaises(ValueError):
                    load_bytetrack_config(p)

    def test_yaml_invalid_values(self):
        cases = {'tracker_type': ['botsort', None], 'track_buffer': [0, -1, True, 3001, 1.5],
                 'fuse_score': [1, 'true', None]}
        for key in ('track_low_thresh', 'track_high_thresh', 'new_track_thresh', 'match_thresh'):
            cases[key] = [-.1, 1.1, True, float('nan'), float('inf'), '.5']
        cases['track_low_thresh'] += [.25, .3]
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'tracker.yaml'
            for field, values in cases.items():
                for value in values:
                    p.write_text(yaml.safe_dump({**self.params, field: value}))
                    with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, field):
                        load_bytetrack_config(p)


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.config = load_detection_config()
        self.tracking = load_tracking_config()
        self.frame = MagicMock(shape=(720, 1280, 3), size=100)
        self.model = MagicMock()
        self.model.names = {0: 'person', 1: 'bicycle'}
        self.result = MagicMock()
        self.result.boxes.is_track = True
        self.result.boxes.data.cpu.return_value.tolist.return_value = [
            [10, 20, 100, 200, 7, .87, 0], [200, 20, 300, 200, 8, .91, 0],
            [50, 50, 60, 60, 9, .9, 1]]
        self.result.speed = {'inference': 12.5}
        self.model.track.return_value = [self.result]
        self.factory = MagicMock(return_value=self.model)
        self.loader = patch.object(detector, '_load_yolo', return_value=self.factory)
        self.loader.start()
        self.addCleanup(self.loader.stop)

    def test_model_once_one_track_call_per_frame_no_predict(self):
        instance = PersonTracker(self.config, self.tracking)
        first = instance.track(self.frame)
        second = instance.track(self.frame)
        self.factory.assert_called_once_with(str(PROJECT_ROOT / 'yolo26n.pt'), task='detect')
        self.assertEqual(self.model.track.call_count, 2)
        self.model.predict.assert_not_called()
        self.model.train.assert_not_called()
        self.assertEqual([t.track_id for t in first.tracks], [7, 8])
        self.assertEqual(first.tracks, second.tracks)
        for call in self.model.track.call_args_list:
            args = call.kwargs
            self.assertIs(args['source'], self.frame)
            self.assertIs(args['persist'], True)
            self.assertEqual(args['classes'], [0])
            self.assertEqual(args['tracker'], str(resolve_tracker_path(self.tracking['tracker_config'])))
            self.assertEqual(args['conf'], self.config['confidence_threshold'])
            self.assertEqual(args['device'], 'cpu')
            for key in ('save', 'save_txt', 'save_conf', 'save_crop', 'show', 'visualize', 'stream', 'augment'):
                self.assertIs(args[key], False)
        self.assertEqual(first.inference_ms, 12.5)
        self.assertGreaterEqual(first.processing_ms, 0)

    def test_missing_ids_remain_visible_as_untracked(self):
        self.result.boxes.is_track = False
        self.result.boxes.data.cpu.return_value.tolist.return_value = [[1, 2, 30, 40, .8, 0]]
        result = PersonTracker().track(self.frame)
        self.assertEqual(result.tracks, ())
        self.assertEqual(result.untracked_detections, (Detection(1, 2, 30, 40, .8, 0),))

    def test_empty_results_and_boxes(self):
        instance = PersonTracker()
        self.result.boxes = None
        self.assertEqual(instance.track(self.frame).tracks, ())
        self.model.track.return_value = []
        with self.assertRaisesRegex(RuntimeError, 'exactamente'):
            instance.track(self.frame)

    def test_bad_id_and_box_values(self):
        instance = PersonTracker()
        for row in ([1, 2, 3, 4, .5, .9, 0], [1, 2, 3, 4, 0, .9, 0],
                    [1, 2, 3, 4, -1, .9, 0], [1, 2, 3, 4, float('nan'), .9, 0],
                    [1, 2, 3, 4, 1, float('inf'), 0], [3, 2, 1, 4, 1, .9, 0],
                    [1, 2, 3, 4, 1, 1.2, 0], [1, 2, 3, 4, .9, 0]):
            self.result.boxes.data.cpu.return_value.tolist.return_value = [row]
            with self.subTest(row=row), self.assertRaises(RuntimeError):
                instance.track(self.frame)

    def test_duplicate_ids_rejected(self):
        row = [1, 2, 30, 40, 1, .9, 0]
        self.result.boxes.data.cpu.return_value.tolist.return_value = [row, row]
        with self.assertRaisesRegex(RuntimeError, 'repetido'):
            PersonTracker().track(self.frame)

    def test_invalid_time_is_unavailable(self):
        instance = PersonTracker()
        for value in (None, True, '10', -1, float('nan'), float('inf')):
            self.result.speed = {'inference': value}
            self.assertIsNone(instance.track(self.frame).inference_ms)

    def test_input_rejected_before_inference(self):
        instance = PersonTracker()
        for frame in (None, 'https://example.com', 0, MagicMock(shape=(0, 0, 3), size=0)):
            with self.assertRaises(ValueError):
                instance.track(frame)
        self.model.track.assert_not_called()

    def test_failed_track_has_clear_error(self):
        self.model.track.side_effect = ModuleNotFoundError('lap')
        with self.assertRaisesRegex(RuntimeError, 'requirements.txt'):
            PersonTracker().track(self.frame)

    def test_wrong_class_and_failed_load(self):
        self.model.names = {0: 'cat'}
        with self.assertRaisesRegex(RuntimeError, 'person_class_id'):
            PersonTracker()
        self.factory.side_effect = FileNotFoundError('weights')
        with self.assertRaisesRegex(RuntimeError, 'primera descarga'):
            PersonTracker()

    def test_false_persist_rejected_before_load(self):
        with self.assertRaisesRegex(ValueError, 'persist'):
            PersonTracker(self.config, {**self.tracking, 'persist': False})
        self.factory.assert_not_called()


class HistoryTests(unittest.TestCase):
    def make_track(self, identifier=1, x=10):
        return Track(x, 20, x + 20, 40, .9, 0, identifier)

    def test_track_structure_and_geometry(self):
        self.assertEqual({f.name for f in dataclasses.fields(Track)},
                         {'track_id', 'x1', 'y1', 'x2', 'y2', 'confidence', 'class_id'})
        self.assertEqual(self.make_track().center, (20, 30))
        for identifier in (0, -1, True, 1.5, '1'):
            with self.assertRaises(ValueError):
                self.make_track(identifier)

    def test_bounded_and_recovered_history(self):
        history = TrackHistory(3, 5)
        for x in range(20):
            history.update((self.make_track(x=x),))
        self.assertEqual(len(history.points[1]), 3)
        previous = list(history.points[1])
        for _ in range(4):
            history.update(())
        self.assertEqual(list(history.points[1]), previous)
        history.update((self.make_track(x=21),))
        self.assertEqual(len(history.points[1]), 3)
        for _ in range(7):
            history.update(())
        self.assertEqual(history.points, {})
        self.assertEqual(history._last_seen, {})

    def test_many_disappearing_tracks_do_not_accumulate(self):
        history = TrackHistory(30, 30)
        for identifier in range(1, 10001):
            history.update((self.make_track(identifier),))
            self.assertLessEqual(len(history.points), 32)
        for _ in range(32):
            history.update(())
        self.assertEqual(history.points, {})

    def test_invalid_history_limits(self):
        for length, buffer in ((0, 30), (301, 30), (True, 30), (30, 0), (30, 3001)):
            with self.assertRaises(ValueError):
                TrackHistory(length, buffer)


class TrackingResourceTests(unittest.TestCase):
    def setUp(self):
        self.config = load_tracking_config()
        self.detection = load_detection_config()
        self.frame = MagicMock(shape=(720, 1280, 3), size=100)
        self.capture = MagicMock()
        self.capture.read.return_value = (True, self.frame)
        self.capture.getBackendName.return_value = 'MOCK'
        self.ui = MagicMock()
        self.ui.error = cv2.error
        self.ui.waitKey.return_value = ord('q')
        self.ui.getWindowProperty.return_value = 1
        self.tracker = MagicMock()
        self.tracker.bytetrack_config = {'track_buffer': 30}
        self.tracker.track.return_value = FrameTracks((Track(10, 20, 100, 200, .87, 0, 7),), (), 10, 15)

    def run_app(self, error=None, load_error=None):
        with patch.object(camera.cv2, 'VideoCapture', return_value=self.capture), \
             patch.object(track, 'PersonTracker', return_value=self.tracker, side_effect=load_error):
            if error:
                with self.assertRaises(error):
                    track.run_tracking(self.ui, load_config(), self.detection, self.config)
            else:
                track.run_tracking(self.ui, load_config(), self.detection, self.config)
        self.capture.release.assert_called_once()
        self.ui.destroyAllWindows.assert_called_once()

    def test_q_and_labels(self):
        self.run_app()
        labels = [c.args[1] for c in self.ui.putText.call_args_list]
        self.assertIn('ID 7 | person | 0.87', labels)
        self.assertTrue(any('Tracks activos: 1' in label for label in labels))
        self.assertTrue(any('YOLO + tracking: 15.0 ms' in label for label in labels))

    def test_escape(self):
        self.ui.waitKey.return_value = 27
        self.run_app()

    def test_window_close(self):
        self.ui.waitKey.return_value = -1
        self.ui.getWindowProperty.return_value = 0
        self.run_app()

    def test_ctrl_c(self):
        self.tracker.track.side_effect = KeyboardInterrupt()
        self.run_app(KeyboardInterrupt)

    def test_load_error(self):
        self.run_app(RuntimeError, RuntimeError('model'))

    def test_load_ctrl_c(self):
        self.run_app(KeyboardInterrupt, KeyboardInterrupt())

    def test_inference_error(self):
        self.tracker.track.side_effect = RuntimeError('track')
        self.run_app(RuntimeError)

    def test_ui_error(self):
        self.ui.imshow.side_effect = cv2.error('UI')
        self.run_app(cv2.error)

    def test_read_error(self):
        self.ui.waitKey.return_value = -1
        self.capture.read.side_effect = [(True, self.frame), (False, None)]
        self.run_app(RuntimeError)

    def test_open_error(self):
        self.capture.open.return_value = False
        with patch.object(camera, 'backend_candidates', return_value=[('mock', 0)]):
            self.run_app(RuntimeError)

    def test_hidden_flags_no_history(self):
        self.config = {**self.config, 'show_trail': False, 'show_track_id': False}
        self.detection = {**self.detection, 'show_confidence': False}
        with patch.object(track, 'TrackHistory') as histories:
            self.run_app()
            histories.assert_not_called()
        labels = [c.args[1] for c in self.ui.putText.call_args_list]
        self.assertIn('person', labels)
        self.assertNotIn('ID 7 | person | 0.87', labels)

    def test_no_id_label_and_trail(self):
        self.tracker.track.return_value = FrameTracks((), (Detection(1, 2, 3, 4, .8, 0),), None, 5)
        self.run_app()
        labels = [c.args[1] for c in self.ui.putText.call_args_list]
        self.assertIn('person | sin ID | 0.80', labels)
        self.ui.line.assert_not_called()

    def test_fps_excludes_initialization_and_trail_draws(self):
        self.ui.waitKey.side_effect = [-1, -1, ord('q')]
        with patch.object(track.time, 'perf_counter', side_effect=[1000, 1000.5, 1001]):
            self.run_app()
        labels = [c.args[1] for c in self.ui.putText.call_args_list]
        self.assertTrue(any('FPS pipeline: 2.0' in label for label in labels))
        self.assertEqual(self.tracker.track.call_count, 3)
        self.assertEqual(self.ui.line.call_count, 3)


class DependencyAndDiagnosticsTests(unittest.TestCase):
    def test_light_imports(self):
        code = ('import sys; import src.main, src.detect, src.track, src.tracker; '
                'assert all(x not in sys.modules for x in ("torch", "ultralytics", "cv2", "lap", "yaml"))')
        result = subprocess.run([sys.executable, '-c', code], cwd=PROJECT_ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_external_bytetrack_package(self):
        requirements = (PROJECT_ROOT / 'requirements.txt').read_text().lower()
        self.assertNotIn('bytetrack', requirements)
        self.assertNotIn('git+', requirements)
        self.assertIn('ultralytics==8.4.163', requirements)
        self.assertIn('lap==0.5.12', requirements)

    def test_diagnostics_no_weights(self):
        with patch.object(detector, '_load_yolo') as factory, \
             patch.object(diagnostics, 'import_module'), patch.object(diagnostics, 'version', return_value='0.5.12'), \
             redirect_stdout(StringIO()) as output:
            self.assertTrue(diagnostics.report_tracking())
        factory.return_value.assert_not_called()
        for text in ('ByteTrack', 'tracker_type', 'persist', 'trail_length', 'track_buffer', 'fuse_score'):
            self.assertIn(text, output.getvalue())

    def test_diagnostics_missing_lap_and_bad_config(self):
        with patch.object(diagnostics, 'version', side_effect=diagnostics.PackageNotFoundError), \
             patch.object(diagnostics, 'load_tracking_config', side_effect=ValueError('JSON inválido')), \
             redirect_stdout(StringIO()) as output:
            self.assertFalse(diagnostics.report_tracking())
        self.assertIn('JSON inválido', output.getvalue())
        self.assertIn('requirements.txt', output.getvalue())


if __name__ == '__main__':
    unittest.main()
