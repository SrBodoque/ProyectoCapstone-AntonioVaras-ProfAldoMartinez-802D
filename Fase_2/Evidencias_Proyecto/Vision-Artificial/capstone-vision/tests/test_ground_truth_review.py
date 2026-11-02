import copy
import sys
import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.dataset_annotations import read_mot
from src.dataset_review import (decode_frames, evaluable_interval, frame_boxes, gt_index,
    load_sequence, new_output, policy, relative_file, role, select_frames, spatial_transform, transform_record)
from src.view_ground_truth import group_records, prepare, render_frame, view
from ground_truth_test_support import ReviewFixture


class TransformPolicyTests(unittest.TestCase):
    def test_origin_then_scale_then_translation(self):
        r = read_mot('1,9,11,21,20,40,1,1,.5', version=17).records[0]
        t = spatial_transform([1920,1080], [960,540])
        self.assertEqual(transform_record(r,t), [5,10,15,30])
        self.assertEqual(r.raw['columns'][2:6], ['11','21','20','40'])
        t['translation_px'] = [2.,-3.]
        self.assertEqual(transform_record(r,t), [7,7,17,27])

    def test_amodal_extents_not_clipped(self):
        r = read_mot('1,1,-9,-19,30,40,1,1,0',version=17).records[0]
        self.assertEqual(transform_record(r,spatial_transform([2,2],[1,1])), [-5,-10,10,10])

    def test_invalid_transforms(self):
        for field,value in [('scale',[0,1]),('scale',[True,1]),('scale',[float('nan'),1]),
                            ('crop','center'),('source_origin',0),('translation_px',[1])]:
            t=spatial_transform([2,2],[1,1]);t[field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                transform_record(read_mot('1,1,1,1,2,2,1,1,1',version=17).records[0],t)

    def test_offset_sign_and_domains_no_wrapping_or_renumbering(self):
        self.assertEqual(gt_index(8,-2),6)
        self.assertEqual(gt_index(8,2),10)
        self.assertEqual(evaluable_interval(12,-2),[2,11])
        self.assertEqual(evaluable_interval(12,2),[0,9])
        self.assertEqual(evaluable_interval(12,0),[0,11])
        for o in (True,3,1.5):
            with self.assertRaises(ValueError):gt_index(0,o)

    def test_protocol_separates_mark0_distractors_and_other_classes(self):
        rows=read_mot('1,1,1,1,2,3,1,1,1\n1,2,1,1,2,3,0,1,1\n1,3,1,1,2,3,0,7,1\n1,4,1,1,2,3,1,3,1',version=17).records
        self.assertEqual([role(r,'mot17') for r in rows],['active_person','ignored_mark0','distractor','other_class'])
        self.assertEqual(policy('mot17')['distractor_classes'],[2,7,8,12])
        self.assertEqual(policy('mot15')['distractor_classes'],[])
        self.assertEqual(policy('mot17')['crowd_ignore_regions'],[])
        car=read_mot('1,8,1,1,2,3,0,3,1',version=17).records[0]
        self.assertEqual(role(car,'mot17'),'other_class')


class ReviewIOTests(ReviewFixture,unittest.TestCase):
    def test_portable_loading_ignores_stale_absolute_root(self):
        c,r=load_sequence(self.manifest,self.root,'MOT17-02')
        self.assertEqual(c['spatial_transform']['scale'],[.5,.5])
        self.assertEqual(c['recording_group'],'MOT17-02')
        self.assertNotIn(str(self.base),str(c))
        self.assertEqual(len(r),36)

    def test_path_escape_and_absolute_paths_rejected(self):
        for v in ('../audit.json','/absolute','C:/user/video.mp4','C:\\video.mp4','dev/../dev/MOT17-02.mp4'):
            with self.subTest(v=v),self.assertRaises(ValueError):relative_file(self.root,v)
        with self.assertRaises(ValueError):new_output(self.root/'bad',self.root)

    def test_unsupported_sources_are_not_opened(self):
        for s in ('OxfordTownCentre','CAVIAR-one','prueba_01'):
            with self.subTest(s=s),self.assertRaises(ValueError):load_sequence(self.manifest,self.root,s)

    def test_gt_out_of_domain_distinct_from_empty(self):
        c,r=load_sequence(self.manifest,self.root,'PETS09-S2L1');g=group_records(r)
        self.assertFalse(frame_boxes(g,0,-1,c)['in_domain'])
        self.assertEqual(frame_boxes(g,0,1,c)['source_frame'],2)
        self.assertEqual(frame_boxes(g,0,1,c)['boxes'][0]['source_frame'],2)

    def test_sampling_and_exact_sequential_decode(self):
        c,r=load_sequence(self.manifest,self.root,'PETS09-S2L1');s=select_frames(r,12)
        self.assertTrue({0,2,6,9,11}.issubset({x['video_index'] for x in s}))
        self.assertTrue(any('geometric_overlap_candidate_neighborhood' in x['reasons'] for x in s))
        images=decode_frames(self.root/c['video']['path'],[0,6,11],[64,48])
        self.assertEqual(sorted(images),[0,6,11])
        self.assertLess(images[0].mean(),images[11].mean())
        with self.assertRaises(ValueError):decode_frames(self.root/c['video']['path'],[12],[64,48])
        with self.assertRaises(ValueError):decode_frames(self.root/c['video']['path'],[1],[65,48])

    def test_export_is_pending_and_never_overwrites(self):
        from src.dataset_review import read_json
        folder=prepare(self.manifest,self.root,'PETS09-S2L1',self.base/'review')
        self.assertEqual(read_json(folder/'review.json')['status'],'PENDING_HUMAN_REVIEW')
        self.assertEqual(read_json(folder/'decision.pending.json')['decision'],'PENDING')
        html=(folder/'review.html').read_text(encoding='utf-8')
        self.assertNotIn('__REVIEW_DATA__',html)
        self.assertNotIn('fetch(',html)
        self.assertIn('data:image/jpeg;base64,',html)
        with self.assertRaises(FileExistsError):prepare(self.manifest,self.root,'PETS09-S2L1',folder)

    def test_native_viewer_keyboard_offsets_and_cleanup_with_mock_gui(self):
        cv=MagicMock();cv.WINDOW_NORMAL=0;cv.WND_PROP_VISIBLE=0
        cv.waitKey.side_effect=[ord('d'),ord('a'),ord('n'),ord('p'),ord('.'),ord(','),ord('o'),ord('q')]
        cv.getWindowProperty.return_value=1
        with patch('src.view_ground_truth.render_frame',wraps=render_frame) as render:
            view(self.manifest,self.root,'PETS09-S2L1',cv2_module=cv)
        self.assertEqual(render.call_args_list[0].args[3],0)
        self.assertEqual(render.call_args_list[1].args[3],1)
        cv.destroyWindow.assert_called_once()

    def test_native_viewer_exception_cleans_window(self):
        cv=MagicMock();cv.WINDOW_NORMAL=0;cv.imshow.side_effect=RuntimeError('owned mock failure')
        with self.assertRaises(RuntimeError):view(self.manifest,self.root,'PETS09-S2L1',cv2_module=cv)
        cv.destroyWindow.assert_called_once()

    def test_imports_do_not_load_inference_or_gui(self):
        r=Path(__file__).resolve().parent.parent
        code="import sys; import src.view_ground_truth,src.dataset_review,src.dataset_approval; assert not any(n in sys.modules for n in ['cv2','torch','ultralytics','src.detector','src.tracker'])"
        p=subprocess.run([sys.executable,'-B','-c',code],cwd=r,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
