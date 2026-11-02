"""Independent dataset audit tests: own synthetic data, no models or real inputs."""

import io
import json
import tarfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from src.dataset_annotations import (read_mot, read_oxford, read_caviar,
                                     ranges, scale_annotation, summarize)
from src.dataset_audit import (audit, annotations, evaluation_cases, main,
                               manifest_json, probe_video, snapshot, write_manifest)
from video_test_support import temporary_directory


class ReaderTests(unittest.TestCase):
    def test_mot17_frames_ids_coordinates_and_ignore(self):
        parsed = read_mot('1,3,1,2,10,20,1,1,0.5\n2,3,-2,2,10,20,0,7,0', version=17)
        a, b = parsed.records
        self.assertEqual((a.source_frame, a.frame_index, a.object_id), (1, 0, '3'))
        self.assertEqual(a.bbox_xyxy, (0., 1., 10., 21.))
        self.assertEqual(a.visibility, .5)
        self.assertFalse(a.ignored)
        self.assertTrue(b.ignored)
        self.assertEqual(b.bbox_xyxy[0], -3.)  # Legitimate amodal box: never clip here.

    def test_mot15_xyz_are_not_classes_or_visibility(self):
        p = read_mot('1,9,499,158,31.03,75.17,1,-4.15,-7.35,0', version=15)
        r = p.records[0]
        self.assertIsNone(r.source_class)
        self.assertIsNone(r.visibility)
        self.assertEqual(r.raw['world_xyz'], [-4.15, -7.35, 0])
        self.assertEqual(r.class_label, 'person')
        self.assertIn('person_from_MOT15_protocol_not_source_class', r.transformations)

    def test_mot_invalid_rows_are_not_silently_repaired(self):
        for row in ('1,1,1,1,2,3,1,1', '0,1,1,1,2,3,1,1,1',
                    '1.5,1,1,1,2,3,1,1,1', '1,-1,1,1,2,3,1,1,1',
                    '1,1,1,1,0,3,1,1,1', '1,1,nan,1,2,3,1,1,1',
                    '1,1,1,1,2,3,2,1,1', '1,1,1,1,2,3,1,14,1',
                    '1,1,1,1,2,3,1,1,1.5'):
            with self.subTest(row=row):
                p = read_mot(row, version=17)
                self.assertEqual(len(p.errors), 1)
                self.assertFalse(p.records)
        with self.assertRaises(ValueError):
            read_mot('', version=16)

    def test_oxford_zero_ids_body_flags_and_short_tail(self):
        p = read_oxford('0,0,1,1,2,3,4,5,1,2,10,20\n1,1,1,0,2,3,4,5,0,0,0,0\n139,3090,1,1,1,2,3,4,5,6,7')
        self.assertEqual(len(p.records), 2)
        self.assertEqual((p.records[0].object_id, p.records[0].frame_index), ('0', 0))
        self.assertEqual(p.records[0].bbox_xyxy, (1., 2., 10., 20.))
        self.assertTrue(p.records[1].ignored)
        self.assertIsNone(p.records[1].bbox_xyxy)
        self.assertEqual(p.errors[0]['line'], 3)
        self.assertIn('got 11', p.errors[0]['reason'])

    def test_caviar_individual_groups_empty_frames_and_unknown_visibility(self):
        text = '''<dataset name="toy"><frame number="0"><objectlist />
        <grouplist><group id="90"><box xc="1" yc="2" w="3" h="4"/></group></grouplist></frame>
        <frame number="1"><objectlist><object id="0"><box xc="10" yc="20" w="6" h="8"/>
        <appearance>occluded</appearance><hypothesislist><hypothesis><role>walker</role>
        </hypothesis></hypothesislist></object></objectlist></frame></dataset>'''
        p = read_caviar(text)
        self.assertEqual(p.explicit_frames, {0, 1})
        self.assertEqual(len(p.records), 1)
        a = p.records[0]
        self.assertEqual(a.object_id, '0')
        self.assertEqual(a.bbox_xyxy, (7., 16., 13., 24.))
        self.assertIsNone(a.visibility)
        self.assertIsNone(a.ignored)
        self.assertEqual(a.raw['appearance'], 'occluded')
        s = summarize(p, 3)
        self.assertEqual(s['explicit_empty_xml_frame_ranges'], [[0, 0]])
        self.assertEqual(s['missing_explicit_xml_frame_ranges'], [[2, 2]])

    def test_caviar_invalid_duplicate_frames_and_entities(self):
        p = read_caviar('<dataset><frame number="0"><objectlist><object id="0"/></objectlist></frame><frame number="0"/></dataset>')
        self.assertEqual(len(p.errors), 2)
        for text in ('<!DOCTYPE x><dataset/>', '<!ENTITY x "x"><dataset/>', '<other/>'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                read_caviar(text)

    def test_summary_duplicates_gaps_and_unknown_negative_frames(self):
        p = read_mot('1,1,1,1,2,3,1,1,1\n1,1,1,1,2,3,1,1,1\n3,1,1,1,2,3,1,1,1', version=17)
        s = summarize(p, 4)
        self.assertEqual(s['duplicate_frame_id_pairs'], 1)
        self.assertEqual(s['identity_gap_count'], 1)
        self.assertEqual(s['frames_without_rows_ranges'], [[1, 1], [3, 3]])
        self.assertEqual(s['explicit_empty_xml_frame_ranges'], [])
        self.assertEqual(ranges([4, 2, 1, 2]), [[1, 2], [4, 4]])

    def test_scale_is_explicit_and_original_is_preserved(self):
        r = read_mot('1,1,11,21,20,40,1,1,1', version=17).records[0]
        scaled = scale_annotation(r, .5, .5)
        self.assertEqual(scaled.bbox_xyxy, (5., 10., 15., 30.))
        self.assertEqual(r.bbox_xyxy, (10., 20., 30., 60.))
        self.assertEqual(scaled.raw, r.raw)
        with self.assertRaises(ValueError):
            scale_annotation(r, 0, 1)


class FileAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'datasets'
        self.root.mkdir()

    def make_mot(self, *, duplicate=False, divergent=False):
        p = self.root / 'annotations/MOT/MOT17Labels.zip'
        p.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(p, 'w') as z:
            for suffix in ('DPM', 'FRCNN', 'SDP'):
                name = 'MOT17-02-' + suffix
                raw = '1,1,1,1,2,3,1,1,1\n2,1,2,1,2,3,1,1,1\n'
                if divergent and suffix == 'SDP':
                    raw = raw.replace('2,1,2,1', '2,1,3,1')
                z.writestr(f'train/{name}/gt/gt.txt', raw)
                z.writestr(f'train/{name}/seqinfo.ini', f'[Sequence]\nname={name}\nimWidth=10\nimHeight=20\nframeRate=25\nseqLength=2\n')
                if duplicate and suffix == 'DPM':
                    with self.assertWarns(UserWarning):
                        z.writestr(f'train/{name}/gt/gt.txt', raw)
        return p

    def video_stub(self, *a, **kw):
        return dict(width=5., height=10., reported_fps=25., decoded_frames=2,
                    reported_frames=2, decode_status='completed')

    def test_zip_read_only_exact_member_gt_not_detections(self):
        p = self.make_mot()
        before = p.read_bytes()
        parsed, details = annotations(self.root, 'mot17', 'MOT17-02')
        self.assertEqual(len(parsed.records), 2)
        self.assertTrue(details['variant_ground_truth_identical'])
        self.assertEqual(len(details['variants']), 3)
        self.assertEqual(p.read_bytes(), before)
        self.assertEqual(list(p.parent.iterdir()), [p])

    def test_duplicate_zip_members_rejected(self):
        self.make_mot(duplicate=True)
        with self.assertRaises(ValueError):
            annotations(self.root, 'mot17', 'MOT17-02')

    def test_corrupt_zip_reports_problem_without_crashing_all_cases(self):
        p = self.root / 'annotations/MOT/MOT17Labels.zip'
        p.parent.mkdir(parents=True)
        p.write_bytes(b'not a ZIP')
        (self.root / 'dev').mkdir()
        (self.root / 'dev/MOT17-02.mp4').write_bytes(b'fake')
        with patch('src.dataset_audit.probe_video', side_effect=self.video_stub):
            m = audit(self.root)
        self.assertEqual(m['sequences'][0]['status'], 'NEEDS_VERIFICATION')
        self.assertIn('BadZipFile', ' '.join(m['sequences'][0]['issues']))

    def test_divergent_variants_are_reported(self):
        self.make_mot(divergent=True)
        _, d = annotations(self.root, 'mot17', 'MOT17-02')
        self.assertFalse(d['variant_ground_truth_identical'])

    def test_corrupt_xml_is_reported_and_other_cases_are_still_audited(self):
        p = self.root / 'annotations/CAVIAR/ceecp1gt.xml'
        p.parent.mkdir(parents=True)
        p.write_text('<dataset><frame', encoding='utf-8')
        v = self.root / 'dev/CAVIAR-EnterExitCrossingPaths1cor.mp4'
        v.parent.mkdir()
        v.write_bytes(b'fake')
        with patch('src.dataset_audit.probe_video', side_effect=self.video_stub):
            m = audit(self.root)
        self.assertEqual(len(m['sequences']), 7)
        self.assertIn('ParseError', ' '.join(m['sequences'][4]['issues']))

    def test_missing_videos_are_explicit_not_ready(self):
        m = audit(self.root)
        self.assertEqual(len(m['sequences']), 7)
        self.assertTrue(all(c['status'] == 'NOT_EVALUABLE' for c in m['sequences'][:-1]))
        self.assertEqual(m['sequences'][-1]['status'], 'EXPLORATORY')
        self.assertEqual(m['eligible_sequence_ids'], [])

    def test_missing_annotation_does_not_assume_gt(self):
        (self.root / 'dev').mkdir()
        (self.root / 'dev/PETS09-S2L1.mp4').write_bytes(b'fake')
        with patch('src.dataset_audit.probe_video', side_effect=self.video_stub):
            m = audit(self.root)
        self.assertEqual(m['sequences'][2]['status'], 'NOT_EVALUABLE')

    def test_real_inventory_is_deterministic_preserved_and_scales_are_candidates(self):
        self.make_mot()
        (self.root / 'dev').mkdir()
        (self.root / 'dev/MOT17-02.mp4').write_bytes(b'fake')
        (self.root / 'ignored.zip.part').write_bytes(b'incomplete; never parsed')
        before = snapshot(self.root)
        with patch('src.dataset_audit.probe_video', side_effect=self.video_stub):
            a, b = audit(self.root), audit(self.root)
        self.assertEqual(manifest_json(a), manifest_json(b))
        self.assertEqual(a['input_inventory'], before)
        self.assertEqual(snapshot(self.root), before)
        self.assertNotIn('ignored.zip.part', before)
        self.assertEqual(a['ignored_incomplete_downloads'], ['ignored.zip.part'])
        item = a['sequences'][0]
        self.assertEqual(item['annotations']['candidate_annotation_to_video_scale'], [.5, .5])
        self.assertEqual(item['status'], 'NEEDS_VERIFICATION')
        self.assertEqual(a['eligible_sequence_ids'], [])

    def test_input_changes_during_audit_are_detected(self):
        (self.root / 'exploratory').mkdir()
        video = self.root / 'exploratory/prueba_01.mp4'
        video.write_bytes(b'before')
        def mutate(*args, **kwargs):
            video.write_bytes(b'changed own synthetic fixture')
            return self.video_stub()
        with patch('src.dataset_audit.probe_video', side_effect=mutate), self.assertRaises(RuntimeError):
            audit(self.root)

    def test_prueba_never_eligible_even_with_ready_claim(self):
        item = {'id': 'prueba_01', 'kind': 'exploratory', 'status': 'READY', 'evaluation_ready': True,
                'verification': {'temporal_alignment_verified': True, 'evaluation_policy_verified': True}}
        self.assertEqual(evaluation_cases({'sequences': [item]}), [])
        item['kind'] = 'mot17'
        self.assertEqual(evaluation_cases({'sequences': [item]}), [])
        item['id'] = 'MOT17-02'
        self.assertEqual(evaluation_cases({'sequences': [item]}), [item])
        item['verification']['temporal_alignment_verified'] = False
        self.assertEqual(evaluation_cases({'sequences': [item]}), [])

    def test_output_is_new_outside_inputs_and_json_roundtrips(self):
        m = audit(self.root)
        output = self.base / 'output/manifest.json'
        write_manifest(output, m, self.root)
        self.assertEqual(json.loads(output.read_text(encoding='utf-8')), m)
        with self.assertRaises(FileExistsError):
            write_manifest(output, m, self.root)
        with self.assertRaises(ValueError):
            write_manifest(self.root / 'not_allowed.json', m, self.root)
        self.assertEqual(main(['--datasets', str(self.root), '--output', str(output)]), 1)

    def test_nonexistent_root_rejected(self):
        with self.assertRaises(ValueError):
            audit(self.root / 'missing')


class RealDecoderTests(unittest.TestCase):
    setUp = FileAuditTests.setUp
    def test_real_video_decode_and_tar_comparison(self):
        import cv2
        import numpy as np
        from src.video_source import file_sha256
        path = self.base / 'toy.mp4'
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), 25, (64, 48))
        self.assertTrue(writer.isOpened())
        images = [np.full((48, 64, 3), v, dtype=np.uint8) for v in (30, 100, 200)]
        try:
            for image in images:
                writer.write(image)
        finally:
            writer.release()
        archive = self.base / 'toy.tar.gz'
        with tarfile.open(archive, 'w:gz') as t:
            for i, image in enumerate(images):
                ok, encoded = cv2.imencode('.jpg', image)
                self.assertTrue(ok)
                payload = encoded.tobytes()
                info = tarfile.TarInfo(f'toy{i:04}.jpg')
                info.size = len(payload)
                t.addfile(info, io.BytesIO(payload))
        before = (file_sha256(path), file_sha256(archive))
        result = probe_video(path, reference_tar=archive, original='toy')
        self.assertEqual(result['decoded_frames'], 3)
        self.assertEqual(result['decode_status'], 'completed')
        self.assertEqual(result['source_image_comparison']['compared_frames'], 3)
        self.assertEqual(result['observed_dimensions'], [(64, 48)])
        self.assertEqual((file_sha256(path), file_sha256(archive)), before)
        self.assertEqual(sorted(p.name for p in self.base.iterdir()), ['datasets', 'toy.mp4', 'toy.tar.gz'])

    def test_corrupt_mp4_is_explicit_and_releases_capture(self):
        from unittest.mock import MagicMock
        import cv2
        capture = MagicMock()
        capture.isOpened.return_value = False
        with patch.object(cv2, 'VideoCapture', return_value=capture):
            with self.assertRaises(RuntimeError):
                probe_video(self.base / 'bad.mp4')
        capture.release.assert_called_once()

    def test_broken_reference_archive_does_not_prevent_video_decode(self):
        import cv2
        import numpy as np
        path = self.base / 'toy.mp4'
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), 25, (64, 48))
        self.assertTrue(writer.isOpened())
        try:
            writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
        finally:
            writer.release()
        archive = self.base / 'bad.tar.gz'
        archive.write_bytes(b'broken reference')
        result = probe_video(path, reference_tar=archive, original='toy')
        self.assertEqual(result['decoded_frames'], 1)
        self.assertIn('source_image_comparison_error', result)


if __name__ == '__main__':
    unittest.main()
