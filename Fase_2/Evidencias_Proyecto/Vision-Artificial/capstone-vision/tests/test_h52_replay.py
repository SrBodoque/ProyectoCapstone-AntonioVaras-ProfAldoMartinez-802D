"""Conteo sobre archivos sintéticos, sin cámara ni inferencia."""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from src import count_replay, count_mp4
from src.count_engine import TransitionCounter
from src.video_source import file_sha256
from src.video_zones import export_video_zones, load_video_zones
from src.zones import ZoneProfile
from h52_test_support import fixture
from video_test_support import temporary_directory


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp=temporary_directory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.video,self.case,self.zones=fixture(self.root)

    def count(self):
        return count_replay.run_count_replay(self.video,self.zones,self.case,self.root/"outputs")

    def mutate(self,name,callback):
        path=self.case/name
        data=json.loads(path.read_text(encoding="utf-8"))
        callback(data)
        path.write_text(json.dumps(data),encoding="utf-8")

    def rows(self,callback):
        path=self.case/"predictions.jsonl"
        rows=[json.loads(s) for s in path.read_text().splitlines()]
        callback(rows)
        path.write_text("".join(json.dumps(r)+"\n" for r in rows),encoding="utf-8")

    def test_replay_counts_once_preserves_inputs_and_records_sources(self):
        files=[self.video,self.zones,*self.case.iterdir()]
        before={p:file_sha256(p) for p in files}
        directory,summary=self.count()
        self.assertEqual((summary["status"],summary["entries"],summary["exits"]),("completed",1,0))
        self.assertFalse(summary["inference_repeated"])
        self.assertFalse(summary["accuracy_validated"])
        events=[json.loads(s) for s in (directory/"events.jsonl").read_text().splitlines()]
        self.assertEqual((events[0]["frame_index"],events[0]["timestamp"],events[0]["direction"]),(3,.6,"IN"))
        diagnostic_rows=[json.loads(s) for s in (directory/"diagnostics.jsonl").read_text().splitlines()]
        self.assertTrue(any("estabilidad_insuficiente" in r["reason"] for r in diagnostic_rows))
        self.assertTrue(any("confirmado_IN" in r["reason"] for r in diagnostic_rows))
        manifest=json.loads((directory/"run.json").read_text())
        self.assertEqual(manifest["predictions_hashes"]["predictions.jsonl"],before[self.case/"predictions.jsonl"])
        self.assertEqual(manifest["weights_used"][0]["sha256"],"a"*64)
        self.assertEqual(before,{p:file_sha256(p) for p in files})

    def test_repeat_creates_independent_results(self):
        first,_=self.count()
        before={p:file_sha256(p) for p in first.iterdir()}
        second,_=self.count()
        self.assertNotEqual(first,second)
        self.assertEqual(before,{p:file_sha256(p) for p in first.iterdir()})

    def test_out_of_order_rows_are_indexed_without_rewriting(self):
        self.rows(lambda rows:rows.reverse())
        original=file_sha256(self.case/"predictions.jsonl")
        self.assertEqual(self.count()[1]["entries"],1)
        self.assertEqual(file_sha256(self.case/"predictions.jsonl"),original)

    def test_missing_or_invalid_or_repeated_timestamps_use_one_fps_timeline(self):
        for value in (None,"bad",0):
            with self.subTest(value=value):
                self.rows(lambda rows:[r.update(timestamp_ms=value) for r in rows])
                directory,summary=self.count()
                self.assertEqual(summary["entries"],1)
                self.assertEqual(json.loads((directory/"run.json").read_text())["timestamp_source"],
                                 "frame_index/reported_fps")

    def test_no_usable_time_fails_instead_of_using_wall_clock(self):
        self.rows(lambda rows:[r.update(timestamp_ms=None) for r in rows])
        self.mutate("metadata.json",lambda m:m["video"].update(reported_fps=None))
        with self.assertRaisesRegex(ValueError,"FPS"):self.count()

    def test_incomplete_or_detection_results_are_rejected(self):
        for key,value in (("status","failed"),("status","interrupted"),("status","incomplete"),("mode","detection")):
            old=json.loads((self.case/"metadata.json").read_text())
            self.mutate("metadata.json",lambda m:m.update({key:value}))
            with self.assertRaisesRegex(ValueError,"completas"):self.count()
            (self.case/"metadata.json").write_text(json.dumps(old))

    def test_missing_rows_and_duplicate_indices_are_not_empty_frames(self):
        original=(self.case/"predictions.jsonl").read_text()
        self.rows(lambda rows:rows.pop(1))
        with self.assertRaises(ValueError):self.count()
        (self.case/"predictions.jsonl").write_text(original)
        self.rows(lambda rows:rows.append(rows[0]))
        with self.assertRaisesRegex(ValueError,"duplicado"):self.count()

    def test_corrupt_json_and_invalid_boxes_are_not_silent_zero_counts(self):
        path=self.case/"predictions.jsonl"
        original=path.read_text()
        path.write_text('{')
        with self.assertRaises(ValueError):self.count()
        path.write_text(original)
        self.rows(lambda rows:rows[0]["tracks"][0].update(x2=-1))
        with self.assertRaisesRegex(ValueError,"inconsistentes"):self.count()

    def test_wrong_video_or_unconfirmed_zones_or_native_camera_profile_fail(self):
        original=self.zones.read_text()
        data=json.loads(original)
        for change in ({"video_sha256":"b"*64},{"orientation_confirmed":False},{"orientation":{"A":"puerta","B":"exterior"}}):
            self.zones.write_text(json.dumps({**data,**change}))
            with self.assertRaises(ValueError):self.count()
        self.zones.write_text(json.dumps(data["profile"]))
        with self.assertRaises(ValueError):self.count()
        self.zones.write_text(original)
        self.mutate("metadata.json",lambda m:m["video"].update(width=320))
        with self.assertRaisesRegex(ValueError,"dimensiones"):self.count()

    def test_zone_export_never_overwrites_and_geometry_tampering_fails(self):
        data=json.loads(self.zones.read_text())
        with self.assertRaises(FileExistsError):
            export_video_zones(self.zones,self.video,ZoneProfile.from_dict(data["profile"]),0,"test")
        data["profile"]["profile_name"]="changed"
        self.zones.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,"cambió"):load_video_zones(self.zones,self.video)

    def test_source_change_during_count_marks_result_failed(self):
        original=TransitionCounter.update
        changed=[False]
        def update(counter,*args):
            if not changed[0]:
                with (self.case/"predictions.jsonl").open("a") as f:f.write("\n")
                changed[0]=True
            return original(counter,*args)
        with patch.object(TransitionCounter,"update",update):
            directory,summary=self.count()
        self.assertEqual(summary["status"],"failed")
        self.assertIn("cambió",summary["error"])
        self.assertTrue((directory/"summary.json").is_file())

    def test_interrupt_keeps_partial_results_without_claiming_completion(self):
        with patch.object(TransitionCounter,"update",side_effect=KeyboardInterrupt()):
            _,summary=self.count()
        self.assertEqual((summary["status"],summary["frames_processed"]),("interrupted",0))

    def test_count_cli_runs_without_torch_opencv_models_or_gpu(self):
        code = (
            "import sys; from src.count_mp4 import main; "
            "r=main(sys.argv[1:]); "
            "assert not any(x in sys.modules for x in ('torch','ultralytics','cv2')); "
            "raise SystemExit(r)"
        )
        result=subprocess.run([sys.executable,"-B","-c",code,"count","--video",str(self.video),
            "--zones",str(self.zones),"--predictions",str(self.case),"--output",str(self.root/"cli")],
            capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("IN: 1",result.stdout)

    def test_process_validates_zones_before_any_inference(self):
        with patch("src.video_runner.run_cases") as run,self.assertLogs(count_mp4.LOGGER,level="ERROR"):
            code=count_mp4.main(["process","--video",str(self.video),"--zones",str(self.root/"missing.json"),
                "--device","cpu","--output",str(self.root/"out")])
        self.assertEqual(code,1)
        run.assert_not_called()


if __name__ == "__main__":unittest.main()
