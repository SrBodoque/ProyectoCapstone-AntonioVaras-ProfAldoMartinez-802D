"""Confirmaciones nuevas sobre fixtures; nunca modifica perfiles personales."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from src.count_orientation import confirm_orientation, load_orientation, main, profile_hash
from src.count_engine import EntryCounter
from src import track_count
from src.counting_config import select_tracker
from count_test_support import A, B, ENTRY, profile, run_path
from video_test_support import temporary_directory


class OrientationTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "counting.local.json"

    def confirm(self, p=None, role="exterior"):
        p = profile() if p is None else p
        confirm_orientation(p, role, "test sintetico", self.path, confirmed=True)
        return load_orientation(self.path, p)

    def test_explicit_current_roles_preserve_profile(self):
        p = profile()
        before = p.to_dict()
        selected = self.confirm(p)
        self.assertEqual(selected.profile, p)
        self.assertEqual(p.to_dict(), before)
        self.assertIn("Conteo A=H4 A", selected.description)

    def test_h4_old_roles_mapped_explicitly_without_changing_original(self):
        p = profile(a=B, b=A)
        before = p.to_dict()
        selected = self.confirm(p, "puerta")
        self.assertEqual(p.to_dict(), before)
        self.assertEqual(selected.profile.a, A)
        self.assertIn("Conteo A=H4 B", selected.description)
        c = EntryCounter(selected.profile)
        run_path(c, ENTRY[:6])
        self.assertEqual(c.total_entries, 1)

    def test_missing_confirmation_cannot_silently_assume_roles(self):
        with self.assertRaisesRegex(ValueError, "orientacion"):
            load_orientation(self.path, profile())

    def test_changed_geometry_or_camera_invalidates_confirmation(self):
        self.confirm()
        for p in (profile(a=((.1,.3),(.3,.3),(.3,.7),(.1,.7))),
                  profile(width=640,height=480)):
            with self.assertRaisesRegex(ValueError, "cambio"):
                load_orientation(self.path, p)

    def test_confirmation_is_exclusive_and_requires_human_flag(self):
        for kwargs in (dict(role="auto",reviewer="test",confirmed=True),
                       dict(role="exterior",reviewer="",confirmed=True),
                       dict(role="exterior",reviewer="test",confirmed=False)):
            with self.assertRaises(ValueError):
                confirm_orientation(profile(), output=self.path, **kwargs)
        self.confirm()
        before = self.path.read_bytes()
        with self.assertRaises(FileExistsError):
            confirm_orientation(profile(),"puerta","test",self.path,confirmed=True)
        self.assertEqual(self.path.read_bytes(),before)

    def test_tampered_or_duplicate_json_does_not_load(self):
        self.confirm()
        record=json.loads(self.path.read_text(encoding="utf-8"))
        record["confirmed"]=False
        self.path.write_text(json.dumps(record),encoding="utf-8")
        with self.assertRaises(ValueError):load_orientation(self.path,profile())
        self.path.write_text('{"schema_version":1,"schema_version":1}',encoding="utf-8")
        with self.assertRaises(ValueError):load_orientation(self.path,profile())

    def test_cli_reads_active_and_creates_only_new_confirmation(self):
        with patch("src.count_orientation.ZoneStore") as store:
            store.return_value.load_active.return_value=profile()
            self.assertEqual(main(["--h4-a-role","exterior","--reviewer","test",
                                   "--confirm-exterior-door","--output",str(self.path)]),0)
            store.return_value.save_and_activate.assert_not_called()
            store.return_value.activate.assert_not_called()
        self.assertEqual(load_orientation(self.path,profile()).source_hash,profile_hash(profile()))

    def test_application_blocks_before_camera_if_orientation_missing(self):
        with patch.object(track_count,"ZoneStore") as store,patch.object(track_count,"run_count") as run:
            store.return_value.load_active.return_value=profile()
            with self.assertLogs(track_count.LOGGER,level="ERROR"):
                self.assertEqual(track_count.main(["--orientation",str(self.path)]),1)
            run.assert_not_called()

    def test_local_weight_preflight_never_downloads_or_changes_tracker(self):
        cfg={"model":"yolo26n.pt"}
        with patch.object(track_count,"PROJECT_ROOT",self.root):
            with self.assertRaisesRegex(ValueError,"pesos locales"):
                track_count.ensure_local_models(cfg,select_tracker("bytetrack"))
            (self.root/"yolo26n.pt").write_bytes(b"own fixture, not a model")
            track_count.ensure_local_models(cfg,select_tracker("bytetrack"))
            with self.assertRaisesRegex(ValueError,"yolo26n-cls.pt"):
                track_count.ensure_local_models(cfg,select_tracker("botsort_reid"))
            (self.root/"yolo26n-cls.pt").write_bytes(b"own fixture, not a model")
            track_count.ensure_local_models(cfg,select_tracker("botsort_reid"))


if __name__ == "__main__":
    unittest.main()
