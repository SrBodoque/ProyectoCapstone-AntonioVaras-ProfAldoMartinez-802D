"""Launcher-only autosave: real schema/geometry, simulated editor inputs."""
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
import cv2
import numpy as np
from src import launcher,launcher_calibration as cal,launcher_autosave as autosave
from src.video_source import file_sha256
from src.video_zones import load_video_zones
from src.zones import ZoneProfile,ZoneStore
import test_launcher as existing
from h52_test_support import profile


class AutoCalibrationTests(unittest.TestCase):
    setUp=existing.LauncherTests.setUp
    tearDown=existing.LauncherTests.tearDown
    args=existing.LauncherTests.args

    def save(self,output=None,source='video'):
        return autosave.save_calibration(profile(),source,self.video,self.camera,'msmf',0,'TEST',output,[(self.zones,'video3v4')])

    def test_valid_version_increment_hash_geometry_and_original_unchanged(self):
        original=self.zones.read_bytes()
        with patch.object(autosave,'PROJECT_ROOT',self.root):
            a=self.save();b=self.save()
        self.assertEqual(a.name,'synthetic.zones.v5.json');self.assertEqual(b.name,'synthetic.zones.v6.json')
        data=load_video_zones(a,self.video)
        self.assertEqual(data.video_sha256,file_sha256(self.video));self.assertEqual(data.profile,profile())
        self.assertEqual(original,self.zones.read_bytes());self.assertEqual(a.read_bytes(),b.read_bytes())

    def test_explicit_output_and_no_overwrite(self):
        target=self.root/'explicit.json';self.assertEqual(self.save(target),target)
        before=target.read_bytes()
        with self.assertRaises(ValueError):self.save(target)
        self.assertEqual(before,target.read_bytes())

    def test_publish_collision_uses_next_version_without_clobber(self):
        link=autosave.os.link;collision=[]
        def race(src,dst):
            if not collision:
                collision.append(Path(dst));Path(dst).write_text('concurrent existing file');raise FileExistsError()
            return link(src,dst)
        with patch.object(autosave,'PROJECT_ROOT',self.root),patch.object(autosave.os,'link',side_effect=race):result=self.save()
        self.assertEqual(result.name,'synthetic.zones.v6.json')
        self.assertEqual(collision[0].read_text(),'concurrent existing file')

    def test_failed_publish_has_no_empty_target_and_retry_works(self):
        target=self.root/'retry.json'
        with patch.object(autosave.os,'link',side_effect=OSError('disk error')),self.assertRaises(OSError):self.save(target)
        self.assertFalse(target.exists());self.assertEqual(self.save(target),target)

    def test_camera_automatic_profile_and_provenance(self):
        with patch.object(autosave,'PROJECT_ROOT',self.root):target=self.save(source='camera')
        self.assertEqual(cal.load_profile(target,'camera',confirmed=True),profile())
        data=json.loads(target.with_name(target.stem+'.provenance.json').read_text())
        self.assertFalse(data['physical_count_validated']);self.assertEqual(data['reference_size'],[160,160])
        self.assertEqual(data['frame_storage'],'not_saved')

    def test_direct_editor_without_save_dialog_and_immediate_viewer_options(self):
        self.ui.choose.side_effect=[str(self.video),'new']
        def edit(*args,**kw):
            self.ui.save_json.assert_not_called();self.ui.text.assert_not_called();self.ui.integer.assert_not_called()
            kw['on_save'](profile(),False)
            return profile()
        with patch.object(autosave,'PROJECT_ROOT',self.root),patch.object(cal,'edit_profile',side_effect=edit),patch.object(launcher.resources,'videos',return_value=[self.video]):
            result=self.controller.prepare(self.args('--calibrar','--mp4'))
        self.assertEqual(cal.load_profile(result.zones,'video',result.video),profile())
        self.assertEqual((result.source,result.video),('video',self.video));self.ui.save_json.assert_not_called()
        self.ui.confirm.assert_called_once();self.assertIn(str(result.zones),self.ui.confirm.call_args.args[1])

    def test_cancel_editor_does_not_generate_profile_even_with_seed(self):
        args=self.args('--mp4','--video',str(self.video))
        with patch.object(autosave,'PROJECT_ROOT',self.root),patch.object(cal,'edit_profile',side_effect=cal.Cancelled),self.assertRaises(cal.Cancelled):
            self.controller.calibrate(args,self.video,None,seed=profile())
        self.assertFalse((self.root/'results_testing').exists());self.ui.save_json.assert_not_called()

    def test_advanced_save_as_only_when_requested_in_editor(self):
        target=self.root/'chosen.json';self.ui.save_json.side_effect=None;self.ui.save_json.return_value=target
        def edit(*a,**kw):kw['on_save'](profile(),True);return profile()
        with patch.object(cal,'edit_profile',side_effect=edit):result=self.controller.calibrate(self.args('--mp4'),self.video,None)
        self.assertEqual(result,target);self.ui.save_json.assert_called_once()

    def editor(self,keys,save):
        store=ZoneStore(self.root/'editor');store.save_and_activate(profile())
        with patch.object(cv2,'namedWindow'),patch.object(cv2,'setMouseCallback'),patch.object(cv2,'imshow'),patch.object(cv2,'destroyWindow'),patch.object(cv2,'getWindowProperty',return_value=1),patch.object(cv2,'waitKey',side_effect=keys):
            return cal.edit_camera_frame(cv2,np.zeros((160,160,3),np.uint8),store,0,on_save=save)

    def test_real_editor_s_saves_without_name_prompt(self):
        saved=[]
        self.assertEqual(self.editor([ord('s')],lambda p,a:saved.append((p,a))),profile())
        self.assertEqual(saved,[(profile(),False)])

    def test_real_editor_retains_geometry_after_save_error(self):
        attempts=[]
        def save(p,a):
            attempts.append(p)
            if len(attempts)==1:raise OSError('retryable disk error')
        self.assertEqual(self.editor([ord('s'),ord('s')],save),profile())
        self.assertEqual(attempts,[profile(),profile()])

    def test_real_editor_seed_cancel_does_not_export(self):
        with self.assertRaises(cal.Cancelled):self.editor([ord('q')],lambda *a:self.fail('cancel must not save'))

    def test_invalid_profile_never_published(self):
        with patch.object(autosave,'PROJECT_ROOT',self.root),self.assertRaises(ValueError):
            autosave.save_calibration(NS(to_dict=lambda:{}),'video',self.video,None,'msmf',0,'TEST')
        self.assertFalse((self.root/'results_testing').exists())

    def test_camera_publish_failure_removes_only_new_sidecar(self):
        link=autosave.os.link
        def fail_profile(src,dst):
            if Path(src).name=='profile.json':raise OSError('profile publication failed')
            return link(src,dst)
        target=self.root/'camera.json'
        with patch.object(autosave.os,'link',side_effect=fail_profile),self.assertRaises(OSError):
            autosave.save_calibration(profile(),'camera',None,self.camera,'msmf',0,'TEST',target)
        self.assertFalse(target.exists());self.assertFalse(target.with_name('camera.provenance.json').exists())

    def test_editor_cancel_save_prompt_retains_geometry_for_retry(self):
        attempts=[]
        def save(p,a):
            attempts.append(p)
            if len(attempts)==1:raise cal.Cancelled()
        self.assertEqual(self.editor([ord('w'),ord('s')],save),profile())
        self.assertEqual(attempts,[profile(),profile()])

    def test_changed_video_at_s_is_rejected_before_publication(self):
        def edit(*a,**kw):
            self.video.write_bytes(b'changed fixture')
            kw['on_save'](profile(),False)
        with patch.object(cal,'edit_profile',side_effect=edit),self.assertRaises(RuntimeError):
            self.controller.calibrate(self.args('--mp4'),self.video,None,seed=profile())
        self.ui.text.assert_not_called()
