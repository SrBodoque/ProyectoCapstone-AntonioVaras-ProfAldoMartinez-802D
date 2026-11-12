import json
import subprocess
import sys
import unittest
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

from src import counting_config, tracker
from src.config import PROJECT_ROOT, load_detection_config, load_tracking_config, load_tracker_config, resolve_tracker_path
from src.count_engine import CountSettings
from src.counting_config import TRACKERS, load_counting_config, select_tracker
from src.track_botsort_reid import BOTSORT_CONFIG
from src.track_fast import FASTTRACK_CONFIG
from src.track_recovery import RECOVERY_CONFIG, RECOVERY_CONFIDENCE
from video_test_support import temporary_directory


class SelectionTests(unittest.TestCase):
    def test_default_is_botsort_and_settings_valid(self):
        config = load_counting_config()
        self.assertEqual(config.tracker, 'botsort_reid')
        self.assertEqual(config.thresholds, CountSettings())

    def test_all_four_reuse_existing_paths_and_original_yaml(self):
        expected = {'botsort_reid': (BOTSORT_CONFIG, 'botsort', None),
                    'fasttracker': (FASTTRACK_CONFIG, 'fasttrack', None),
                    'bytetrack': (load_tracking_config()['tracker_config'], 'bytetrack', None),
                    'recovery': (RECOVERY_CONFIG, 'bytetrack', RECOVERY_CONFIDENCE)}
        before = {str(p): p.read_bytes() for p in (PROJECT_ROOT/'config').glob('*') if p.is_file()}
        for name, (path, kind, override) in expected.items():
            selected = select_tracker(name)
            self.assertEqual(selected.tracking_config['tracker_config'], path)
            self.assertEqual(selected.tracker_params, load_tracker_config(resolve_tracker_path(path)))
            self.assertEqual(selected.tracker_params['tracker_type'], kind)
            self.assertEqual(selected.confidence_override, override)
            self.assertEqual(selected.tracking_config['trail_length'], load_tracking_config()['trail_length'])
        self.assertEqual(before, {str(p): p.read_bytes() for p in (PROJECT_ROOT/'config').glob('*') if p.is_file()})

    def test_actual_persontracker_receives_yaml_confidence_and_device_for_each_selection(self):
        # Motor común REAL del proyecto; modelo/IA y diagnóstico ReID simulados.
        for name in TRACKERS:
            with self.subTest(name=name):
                model = MagicMock()
                model.track.return_value = [NS(boxes=None, speed={'inference': 2.})]
                selected = select_tracker(name)
                with patch.object(tracker, 'load_person_model', return_value=(model, NS(effective_device='cuda:0'))) as loader, \
                     patch.object(tracker, 'ReIDDiagnostics') as reid:
                    # Fixture del contrato histórico, independiente del tuning local del usuario.
                    detection = {**load_detection_config(), 'confidence_threshold': .65}
                    engine = tracker.PersonTracker(detection, selected.tracking_config,
                                                   **selected.constructor_options())
                    import numpy as np
                    engine.track(np.zeros((48, 64, 3), dtype=np.uint8))
                loader.assert_called_once()
                args = model.track.call_args.kwargs
                self.assertEqual(args['tracker'], str(resolve_tracker_path(selected.tracking_config['tracker_config'])))
                self.assertEqual(args['conf'], .1 if name == 'recovery' else .65)
                self.assertEqual(args['device'], 'cuda:0')
                self.assertEqual(reid.call_count, 1 if name == 'botsort_reid' else 0)
                for key in ('save', 'save_txt', 'save_crop', 'show'): self.assertFalse(args[key])

    def test_missing_or_wrong_backend_is_error_without_fallback(self):
        with patch.object(counting_config, 'resolve_tracker_path', side_effect=ValueError('no YAML')):
            with self.assertRaisesRegex(ValueError, 'no YAML'): select_tracker('fasttracker')
        params = select_tracker('bytetrack').tracker_params
        with patch.object(counting_config, 'load_tracker_config', return_value=params):
            with self.assertRaisesRegex(ValueError, 'backend'): select_tracker('botsort_reid')

    def test_baseline_cannot_silently_use_recovery_without_override(self):
        base = {**load_tracking_config(), 'tracker_config': RECOVERY_CONFIG}
        with patch.object(counting_config, 'load_tracking_config', return_value=base):
            with self.assertRaisesRegex(ValueError, 'Recovery'): select_tracker('bytetrack')

    def test_invalid_tracker_names_rejected(self):
        for name in ('', 'auto', 'fasttrack', '../../a.yaml', True, None, {}, ['bytetrack']):
            with self.subTest(name=name), self.assertRaises(ValueError): select_tracker(name)

    def test_config_values_can_be_changed_without_python(self):
        with temporary_directory() as directory:
            p = Path(directory)/'counting.json'
            for name in TRACKERS:
                p.write_text(json.dumps({'tracker':name, 'thresholds':asdict(CountSettings())}))
                self.assertEqual(load_counting_config(p).tracker, name)

    def test_missing_invalid_and_duplicate_json_keys_fail(self):
        with temporary_directory() as directory:
            p = Path(directory)/'counting.json'
            with self.assertRaises(ValueError): load_counting_config(p)
            valid = {'tracker':'botsort_reid', 'thresholds':asdict(CountSettings())}
            cases = ['{', '[]', '{"tracker":"bytetrack","tracker":"recovery"}', '['*1200+']'*1200,
                     json.dumps({**valid, 'extra':1}), json.dumps({**valid, 'tracker':'unknown'}),
                     json.dumps({**valid, 'thresholds': {}}), json.dumps({**valid, 'thresholds': {**valid['thresholds'],'min_observations':1}})]
            for data in cases:
                p.write_text(data)
                with self.subTest(data=data[:60]), self.assertRaises(ValueError): load_counting_config(p)

    def test_imports_are_light_and_do_not_create_files(self):
        code = '''import sys
from pathlib import Path
before={str(p) for p in Path('config').rglob('*')}
import src.count_engine, src.count_geometry, src.counting_config, src.track_count
assert not any(n in sys.modules for n in ('cv2','numpy','torch','ultralytics','src.camera'))
assert before=={str(p) for p in Path('config').rglob('*')}
'''
        p = subprocess.run([sys.executable,'-c',code],cwd=PROJECT_ROOT,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)


if __name__ == '__main__': unittest.main()
