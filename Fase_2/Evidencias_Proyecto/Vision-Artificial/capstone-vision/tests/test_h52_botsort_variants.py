"""Contratos BoT-SORT y matriz dinámica con MP4 sintético; IA/CUDA simuladas."""

import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import MagicMock, patch

from src import compare_mp4_trackers as compare, count_mp4, tracker, video_runner
from src.config import load_detection_config, load_tracker_config, load_tracking_config, resolve_tracker_path
from src.tracker_runtime import resolve_resources, select_mp4_tracker
from src.video_source import file_sha256
from src.view_count_results import load_view
from h52_test_support import fixture
from video_test_support import temporary_directory


class VariantsTests(unittest.TestCase):
    def setUp(self):
        temp = temporary_directory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.weights = self.root/"weights"
        self.weights.mkdir()
        (self.weights/"yolo26n.pt").write_bytes(b"fake weight; never loaded")
        self.video,self.case,self.zones = fixture(self.root,real_video=True)

    def backend(self):
        model = MagicMock()
        index = 0
        def track(**kwargs):
            nonlocal index
            x = 20 if index < 2 else 100
            index += 1
            data = MagicMock()
            data.cpu.return_value.tolist.return_value = [[x,30,x+40,80,1,.9,0]]
            return [NS(boxes=NS(is_track=True,data=data),speed={"inference":.1})]
        model.track.side_effect = track
        return model, NS(effective_device="cuda:0",fallback=False)

    def simulated_runtime(self):
        from contextlib import ExitStack
        stack = ExitStack()
        self.addCleanup(stack.close)
        torch = MagicMock()
        torch.version.cuda = "SIMULATED"
        torch.cuda.get_device_name.return_value = "SIMULATED CUDA; not acceptance"
        stack.enter_context(patch.object(video_runner,"load_torch",return_value=torch))
        stack.enter_context(patch.object(video_runner,"validate_device"))
        stack.enter_context(patch.object(video_runner,"check_backend",return_value="BOTSORT"))
        stack.enter_context(patch.object(tracker,"load_person_model",side_effect=lambda *a,**kw:self.backend()))
        stack.enter_context(patch.object(tracker,"ReIDDiagnostics",return_value=MagicMock(effective_model="auto")))

    def test_no_reid_yaml_requires_optin_and_reuses_same_backend(self):
        selection = select_mp4_tracker("botsort")
        path = resolve_tracker_path(selection.tracking_config["tracker_config"])
        with self.assertRaisesRegex(ValueError,"with_reid"):
            load_tracker_config(path)
        self.assertFalse(load_tracker_config(path,allow_botsort_no_reid=True)["with_reid"])
        original = select_mp4_tracker("botsort_reid").tracker_params
        self.assertEqual(selection.tracker_params,{**original,"with_reid":False})

    def test_false_reid_rejects_nonboolean_even_when_opted_in(self):
        params = select_mp4_tracker("botsort").tracker_params
        path = self.root/"arbitrary.yaml"
        for value in (0,1,"false",None):
            path.write_text(json.dumps({**params,"with_reid":value}),encoding="utf-8")
            with self.assertRaises(ValueError):
                load_tracker_config(path,allow_botsort_no_reid=True)

    def test_no_reid_uses_detector_only_and_no_appearance_callbacks(self):
        selection,weights = resolve_resources("botsort",self.weights,"yolo26n.pt")
        self.assertEqual([w["role"] for w in weights],["detector"])
        model,resolution = self.backend()
        with patch.object(tracker,"load_person_model",return_value=(model,resolution)), \
                patch.object(tracker,"ReIDDiagnostics") as reid:
            engine = tracker.PersonTracker(load_detection_config(),selection.tracking_config,
                tracking_confidence_override=.25,experimental_botsort=True,device_override="cuda:0")
            import numpy as np
            engine.track(np.zeros((160,160,3),dtype=np.uint8))
        self.assertIsNone(engine.reid_diagnostics)
        reid.assert_not_called()
        self.assertEqual(model.track.call_args.kwargs["conf"],.25)

    def test_legacy_reid_guard_remains_but_explicit_experiment_is_supported(self):
        config = {**load_detection_config(),"confidence_threshold":.65}
        selection = select_mp4_tracker("botsort_reid")
        with self.assertRaisesRegex(ValueError,"0.65"):
            tracker.PersonTracker(config,selection.tracking_config,tracking_confidence_override=.25)
        with patch.object(tracker,"load_person_model",return_value=self.backend()), \
                patch.object(tracker,"ReIDDiagnostics") as reid:
            tracker.PersonTracker(config,selection.tracking_config,tracking_confidence_override=.25,
                                  experimental_botsort=True)
            reid.assert_called_once()

    def test_missing_reid_weights_block_before_torch_no_fallback(self):
        with patch.object(video_runner,"load_torch") as torch:
            with self.assertRaisesRegex(RuntimeError,"yolo26n-cls.pt"):
                video_runner.prepare_runtime(video_runner.RunOptions("tracking","cuda:0","botsort_reid",str(self.weights),.25))
        torch.assert_not_called()

    def test_invalid_confidence_rejected_without_loading_torch(self):
        for name,value in (("botsort",float("nan")),("botsort",True),("botsort",1.1),("bytetrack",.25)):
            with self.subTest(name=name,value=value), patch.object(video_runner,"load_torch") as torch:
                with self.assertRaisesRegex(ValueError,"confidence"):
                    video_runner.prepare_runtime(video_runner.RunOptions("tracking","cuda:0",name,str(self.weights),value))
                torch.assert_not_called()

    def test_dynamic_pair_names_and_bad_hash_are_validated_before_inference(self):
        video = self.video.rename(self.root/"access west arbitrary name.mp4")
        zones = self.zones.rename(self.root/"review custom polygon.json")
        checked = compare.validate_pairs([(video,zones)])
        self.assertEqual(checked[0]["status"],"valid")
        data = json.loads(zones.read_text())
        data["video_sha256"] = "f"*64
        zones.write_text(json.dumps(data),encoding="utf-8")
        with patch.object(compare,"run_cases") as run:
            _,rows = compare.run_comparison([(video,zones)],self.weights,self.root/"out")
            run.assert_not_called()
        self.assertTrue(all(r["status"] == "invalid_input" for r in rows))

    def test_full_matrix_both_variants_provenance_counts_and_viewer_compatibility(self):
        (self.weights/"yolo26n-cls.pt").write_bytes(b"fake; not loaded")
        self.simulated_runtime()
        before = {p:file_sha256(p) for p in self.root.rglob("*") if p.is_file()}
        directory,rows = compare.run_comparison([(self.video,self.zones)],self.weights,self.root/"out")
        self.assertEqual([r["status"] for r in rows],["completed","completed"],rows)
        self.assertEqual(len({r["tracking_directory"] for r in rows}),2)
        self.assertEqual(len({r["counting_directory"] for r in rows}),2)
        for row in rows:
            self.assertEqual((row["frames"],row["entries"],row["exits"],row["events"]),(4,1,0,1))
            self.assertEqual(row["configuration_effective"]["confidence"],.25)
            self.assertEqual(row["configuration_effective"]["tracker_parameters"]["with_reid"],row["tracker"]=="botsort_reid")
            self.assertGreater(row["processing_fps"],0)
            self.assertEqual(len(load_view(self.video,row["counting_directory"]).events),1)
        for name in ("comparison.json","comparison.csv","comparison.md"):
            self.assertTrue((directory/name).is_file())
        self.assertEqual(before,{p:file_sha256(p) for p in before})

    def test_missing_reid_continues_with_available_variant(self):
        self.simulated_runtime()
        _,rows = compare.run_comparison([(self.video,self.zones)],self.weights,self.root/"out",
                                       ("botsort_reid","botsort"))
        self.assertEqual([r["status"] for r in rows],["pending","completed"])
        self.assertNotIn("entries",rows[0])
        self.assertIn("yolo26n-cls.pt",rows[0]["error"])

    def test_repeated_matrix_keeps_previous_outputs_unchanged(self):
        self.simulated_runtime()
        first,_ = compare.run_comparison([(self.video,self.zones)],self.weights,self.root/"out",("botsort",))
        before = {p:file_sha256(p) for p in first.rglob("*") if p.is_file()}
        second,_ = compare.run_comparison([(self.video,self.zones)],self.weights,self.root/"out",("botsort",))
        self.assertNotEqual(first,second)
        self.assertEqual(before,{p:file_sha256(p) for p in before})

    def test_multiple_arbitrarily_named_pairs_have_independent_sessions(self):
        self.simulated_runtime()
        pairs = []
        for name in ("north gate", "different scene", "another recording"):
            folder = self.root/name
            folder.mkdir()
            video,_,zones = fixture(folder,real_video=True)
            video = video.rename(folder/(name+".mp4"))
            zones = zones.rename(folder/"independent profile.json")
            pairs.append((video,zones))
        _,rows = compare.run_comparison(pairs,self.weights,self.root/"out",("botsort",))
        self.assertEqual(len(rows),3)
        self.assertTrue(all(r["status"] == "completed" for r in rows))
        self.assertEqual(len({r["tracking_directory"] for r in rows}),3)
        self.assertEqual(len({r["counting_directory"] for r in rows}),3)
        self.assertEqual([Path(r["video"]).stem for r in rows],[p.stem for p,_ in pairs])

    def test_cli_selection_is_explicit_and_video_profile_names_are_dynamic(self):
        with patch.object(count_mp4,"run_count_replay",return_value=(self.root,dict(status="completed",frames_processed=4,expected_frames=4,entries=1,exits=0,events=1))), \
                patch.object(video_runner,"run_cases",return_value=(self.root,dict(status="completed",results=[]))) as run:
            for variant in ("botsort","botsort_reid"):
                self.assertEqual(count_mp4.main(["process","--video",str(self.video),"--zones",str(self.zones),
                    "--tracker",variant,"--device","cuda:0","--confidence","0.25","--weights-dir",str(self.weights)]),0)
                options = run.call_args.args[1]
                self.assertEqual((options.tracker,options.confidence),(variant,.25))
        with patch.object(compare,"run_comparison",return_value=(self.root,[])) as run:
            self.assertEqual(compare.main(["--case",str(self.video),str(self.zones),"--tracker","botsort","--weights-dir",str(self.weights)]),0)
            self.assertEqual(run.call_args.args[0],[[str(self.video),str(self.zones)]])

    def test_interruption_preserves_partial_report_and_does_not_start_other_jobs(self):
        with patch.object(compare,"run_cases",return_value=(self.root,dict(status="interrupted",results=[],error="fixture interrupt"))) as run:
            directory,rows = compare.run_comparison([(self.video,self.zones),(self.video,self.zones)],
                                                    self.weights,self.root/"out")
        run.assert_called_once()
        self.assertEqual([r["status"] for r in rows],["interrupted","pending","pending","pending"])
        self.assertTrue((directory/"comparison.json").is_file())


if __name__ == "__main__":
    unittest.main()
