"""Owned synthetic review inputs. No academic recordings or human approvals."""
import json
import zipfile
from pathlib import Path

from src.dataset_audit import annotations
from src.dataset_approval import CONFIRMATIONS
from src.dataset_review import write_new_json
from src.video_source import file_sha256
from video_test_support import temporary_directory


class ReviewFixture:
    def setUp(self):
        self.temp = temporary_directory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base/'inputs'
        (self.root/'dev').mkdir(parents=True)
        (self.root/'annotations/MOT').mkdir(parents=True)
        import cv2
        import numpy as np
        n = 12
        for name, fps in [('PETS09-S2L1', 7), ('MOT17-02', 30), ('MOT17-04', 30)]:
            writer = cv2.VideoWriter(str(self.root/'dev'/f'{name}.mp4'), cv2.VideoWriter_fourcc(*'mp4v'), fps, (64, 48))
            if not writer.isOpened():
                raise RuntimeError('Synthetic MP4 writer unavailable')
            try:
                for i in range(n):
                    frame = np.full((48, 64, 3), 20+i*10, dtype=np.uint8)
                    cv2.rectangle(frame, (8+i*2, 10), (20+i*2, 32), (250, 250, 250), -1)
                    writer.write(frame)
            finally:
                writer.release()
        for version in (15, 17):
            with zipfile.ZipFile(self.root/f'annotations/MOT/MOT{version}Labels.zip', 'w') as z:
                names = ['PETS09-S2L1'] if version == 15 else ['MOT17-02-'+s for s in ('DPM','FRCNN','SDP')] + ['MOT17-04-'+s for s in ('DPM','FRCNN','SDP')]
                for name in names:
                    rows = []
                    scale = 1 if version == 15 else 2
                    for i in range(n):
                        for ident, x in [(1, 8+i*2), (2, 36-i*2)]:
                            base = [i+1,ident,x*scale+1,10*scale+1,12*scale,22*scale,1]
                            rows.append(','.join(map(str, base+([-1,-1,-1] if version==15 else [1,.5]))))
                        ignored = [i+1,3,2*scale+1,2*scale+1,5*scale,5*scale,0]
                        rows.append(','.join(map(str, ignored+([-1,-1,-1] if version==15 else [7,1]))))
                    prefix = 'MOT15Labels/train/' if version == 15 else 'train/'
                    z.writestr(prefix+name+'/gt/gt.txt', '\n'.join(rows)+'\n')
                    fps = 7 if version == 15 else 30
                    z.writestr(prefix+name+'/seqinfo.ini', f'[Sequence]\nname={name}\nimWidth={64*scale}\nimHeight={48*scale}\nframeRate={fps}\nseqLength={n}\n')
        manifest = {'schema_version': 1, 'dataset_root': 'Z:/unavailable/personal/path', 'input_inventory': {}, 'sequences': []}
        for sid, kind in [('PETS09-S2L1','mot15'), ('MOT17-02','mot17'), ('MOT17-04','mot17')]:
            _, details = annotations(self.root, kind, sid)
            vp = f'dev/{sid}.mp4'
            for path in (vp, details['path']):
                manifest['input_inventory'][path] = {'sha256': file_sha256(self.root/path), 'bytes': (self.root/path).stat().st_size}
            manifest['sequences'].append({'id': sid, 'original_sequence': sid, 'recording_group': sid,
                'kind': kind, 'video_path': vp, 'annotations': details,
                'video': {'decoded_frames': n, 'reported_frames': n, 'reported_fps': 7 if kind=='mot15' else 30,
                          'width': 64, 'height': 48, 'decode_status': 'completed'},
                'status': 'NEEDS_VERIFICATION', 'evaluation_ready': False})
        for sid in ('OxfordTownCentre', 'CAVIAR-one'):
            manifest['sequences'].append({'id': sid, 'kind': 'unsupported', 'status': 'NEEDS_VERIFICATION', 'evaluation_ready': False})
        self.manifest = self.base/'audit.json'
        write_new_json(self.manifest, manifest)

    def approved_fixture_decision(self, packet_path):
        from src.dataset_approval import decision_template
        from src.dataset_review import read_json
        d = decision_template(packet_path)
        p = read_json(packet_path)
        d.update(decision='APPROVE', offset=0,
                 reviewed_video_indices=[s['video_index'] for s in p['selected_frames']],
                 reviewer='AUTOMATED SYNTHETIC FIXTURE - not a real reviewer', approval_date='2026-11-02',
                 notes='Synthetic test only; no real dataset has human approval.',
                 confirmations={k: True for k in CONFIRMATIONS})
        return d
