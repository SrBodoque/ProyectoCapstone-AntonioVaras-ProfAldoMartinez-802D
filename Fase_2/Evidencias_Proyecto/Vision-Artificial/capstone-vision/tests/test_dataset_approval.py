import copy
import json
import shutil
import unittest
from pathlib import Path

from src.dataset_approval import (decision_template, register_approval, validate_approval,
                                  validate_decision, validate_packet, verified_manifest)
from src.dataset_review import read_json, write_new_json
from src.video_source import file_sha256
from src.view_ground_truth import prepare
from ground_truth_test_support import ReviewFixture


class ApprovalTests(ReviewFixture,unittest.TestCase):
    def packet(self):
        folder=prepare(self.manifest,self.root,'PETS09-S2L1',self.base/'review')
        return folder/'review.json'

    def register(self,packet,decision=None,output='approval.json'):
        d=decision if decision is not None else self.approved_fixture_decision(packet)
        path=self.base/(output+'.decision.json');write_new_json(path,d)
        return register_approval(packet,path,self.manifest,self.root,self.base/output)

    def test_pending_template_cannot_approve(self):
        p=self.packet()
        with self.assertRaises(ValueError):self.register(p,decision_template(p))
        self.assertFalse((self.base/'approval.json').exists())

    def test_explicit_synthetic_decision_is_validated_and_sources_preserved(self):
        p=self.packet();video=self.root/'dev/PETS09-S2L1.mp4';source=self.root/'annotations/MOT/MOT15Labels.zip'
        before=(file_sha256(video),file_sha256(source),file_sha256(self.manifest))
        self.register(p)
        a=validate_approval(self.base/'approval.json',p,self.manifest,self.root)
        self.assertEqual(a['decision']['offset'],0)
        self.assertIn('SYNTHETIC',a['decision']['reviewer'])
        self.assertEqual((file_sha256(video),file_sha256(source),file_sha256(self.manifest)),before)
        with self.assertRaises(FileExistsError):self.register(p,output='approval.json')

    def test_single_flag_cannot_replace_review_record(self):
        p=self.packet();d=self.approved_fixture_decision(p)
        for key,value in [('reviewer',''),('approval_date',''),('notes',''),('reviewed_video_indices',[]),
                          ('confirmations',{'all':True}),('review_sha256','0'*64)]:
            trial=copy.deepcopy(d);trial[key]=value
            with self.subTest(key=key),self.assertRaises((ValueError,KeyError)):
                validate_decision(trial,read_json(p),file_sha256(p))

    def test_offset_sign_and_boundary_interval_must_be_approved(self):
        p=self.packet();d=self.approved_fixture_decision(p);d['offset']=2
        with self.assertRaises(ValueError):self.register(p,d)
        d['interval_video_indices_inclusive']=[0,9]
        self.register(p,d,output='positive.json')
        self.assertEqual(validate_approval(self.base/'positive.json',p,self.manifest,self.root)['decision']['offset'],2)

    def test_changed_transform_requires_new_packet_not_decision_edit(self):
        p=self.packet();d=self.approved_fixture_decision(p);d['spatial_transform']['scale']=[.5,.5]
        with self.assertRaises(ValueError):self.register(p,d)

    def test_source_video_change_rejected(self):
        p=self.packet();self.register(p)
        with (self.root/'dev/PETS09-S2L1.mp4').open('ab') as f:f.write(b'owned synthetic mutation')
        with self.assertRaises(ValueError):validate_approval(self.base/'approval.json',p,self.manifest,self.root)

    def test_source_zip_change_rejected(self):
        p=self.packet();self.register(p)
        with (self.root/'annotations/MOT/MOT15Labels.zip').open('ab') as f:f.write(b'owned synthetic mutation')
        with self.assertRaises(ValueError):validate_approval(self.base/'approval.json',p,self.manifest,self.root)

    def test_evidence_change_rejected(self):
        p=self.packet();self.register(p)
        with (p.parent/'review.html').open('a',encoding='utf-8') as f:f.write('\n<!-- owned synthetic mutation -->')
        with self.assertRaises(ValueError):validate_approval(self.base/'approval.json',p,self.manifest,self.root)

    def test_packet_transform_tamper_rejected_by_existing_approval(self):
        p=self.packet();self.register(p)
        value=read_json(p);value['context']['spatial_transform']['translation_px']=[1.,0.]
        p.write_text(json.dumps(value),encoding='utf-8')
        with self.assertRaises(ValueError):validate_approval(self.base/'approval.json',p,self.manifest,self.root)

    def test_policy_tamper_and_unknown_ignore_mask_rejected(self):
        p=self.packet();d=self.approved_fixture_decision(p);d['policy']['crowd_ignore_regions']=[[0,0,64,48]]
        with self.assertRaises(ValueError):self.register(p,d)

    def test_requested_transform_offset_policy_must_match_approval(self):
        p=self.packet();self.register(p)
        t=copy.deepcopy(read_json(p)['context']['spatial_transform']);t['translation_px']=[1.,0.]
        for kw in ({'expected_transform':t},{'expected_offset':-1},{'expected_policy':{'all_ignored':True}}):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                validate_approval(self.base/'approval.json',p,self.manifest,self.root,**kw)

    def test_relocation_keeps_same_valid_approval(self):
        p=self.packet();self.register(p)
        new_root=self.base/'relocated-inputs';shutil.copytree(self.root,new_root)
        a=validate_approval(self.base/'approval.json',p,self.manifest,new_root)
        self.assertEqual(a['context']['video']['path'],'dev/PETS09-S2L1.mp4')

    def test_portable_status_never_trusts_a_ready_bit(self):
        data=read_json(self.manifest)
        for c in data['sequences']:
            c['status']='READY';c['evaluation_ready']=True
        self.manifest.write_text(json.dumps(data),encoding='utf-8')
        m=verified_manifest(self.manifest,self.root)
        self.assertEqual(m['eligible_sequence_ids'],[])
        self.assertEqual(m['dataset_root'],'.')
        self.assertTrue(all(not c['evaluation_ready'] for c in m['sequences']))

    def test_validated_registry_promotes_only_bound_sequence(self):
        p=self.packet();self.register(p)
        m=verified_manifest(self.manifest,self.root,[(self.base/'approval.json',p)])
        self.assertEqual(m['eligible_sequence_ids'],['PETS09-S2L1'])
        c=next(c for c in m['sequences'] if c['id']=='PETS09-S2L1')
        self.assertEqual(c['status'],'READY')
        self.assertEqual(c['approved_configuration']['interval_video_indices_inclusive'],[0,11])
        with self.assertRaises(ValueError):verified_manifest(self.manifest,self.root,[(self.base/'approval.json',p)]*2)

    def test_changed_approval_offset_not_accepted_as_unchanged_decision(self):
        p=self.packet();self.register(p);ap=self.base/'approval.json'
        a=read_json(ap);a['decision']['offset']=1
        ap.write_text(json.dumps(a),encoding='utf-8')
        with self.assertRaises(ValueError):validate_approval(ap,p,self.manifest,self.root)

    def test_packet_requires_all_offsets(self):
        p=self.packet();a=read_json(p);a['offset_candidates']=[0]
        p.write_text(json.dumps(a),encoding='utf-8')
        with self.assertRaises(ValueError):validate_packet(p,self.manifest,self.root)

    def test_implementation_drift_invalidates_packet(self):
        p=self.packet();a=read_json(p);a['context']['implementation_sha256']['dataset_review.py']='0'*64
        p.write_text(json.dumps(a),encoding='utf-8')
        with self.assertRaises(ValueError):validate_packet(p,self.manifest,self.root)
