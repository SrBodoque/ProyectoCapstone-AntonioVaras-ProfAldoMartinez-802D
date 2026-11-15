"""Selección real de configuración; modelo simulado, sin instalar ni descargar."""

import io
import json
import socket
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

from src import count_mp4, tracker_runtime, video_runner
from src.devices import DeviceResolution
from src.tracker import FrameTracks, Track
from src.video_source import file_sha256
from h52_test_support import fixture
from video_test_support import temporary_directory


class SelectionTests(unittest.TestCase):
    def test_runner_rejects_network_weights_before_resolving_or_loading_torch(self):
        with patch.object(video_runner,"load_torch") as torch:
            for mode in ("detection","tracking"):
                for root in ("https://example.invalid/weights",r"\\server\weights"):
                    with self.subTest(mode=mode,root=root),self.assertRaisesRegex(ValueError,"local"):
                        video_runner.prepare_runtime(video_runner.RunOptions(mode,"cpu","bytetrack",root))
        torch.assert_not_called()

    def setUp(self):
        self.temp=temporary_directory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.weights=self.root/"weights"
        self.weights.mkdir()
        (self.weights/"yolo26n.pt").write_bytes(b"synthetic detector fixture, not model weights")
        self.torch=NS(version=NS(cuda=None),cuda=MagicMock())

    def prepare(self,name):
        options=video_runner.RunOptions("tracking","cpu",name,str(self.weights))
        with patch.object(video_runner,"load_torch",return_value=self.torch), \
             patch.object(video_runner,"validate_device"), \
             patch.object(video_runner,"check_backend",return_value="SIMULATED_BACKEND"):
            return video_runner.prepare_runtime(options)

    def test_defaults_keep_legacy_bytetrack_and_alias_reuses_existing_yaml(self):
        self.assertEqual(video_runner.RunOptions("tracking","cpu").tracker,"bytetrack")
        selection,weights=tracker_runtime.resolve_resources("fasttrack",self.weights,"yolo26n.pt")
        self.assertEqual(selection.name,"fasttracker")
        self.assertEqual(selection.tracker_params["tracker_type"],"fasttrack")
        self.assertEqual(weights[0]["sha256"],file_sha256(self.weights/"yolo26n.pt"))

    def test_all_backends_record_exact_configs_and_only_recovery_override(self):
        (self.weights/"yolo26n-cls.pt").write_bytes(b"synthetic appearance fixture")
        for name,backend,override in (("bytetrack","bytetrack",None),("fasttrack","fasttrack",None),
                                      ("botsort_reid","botsort",None),("recovery","bytetrack",.1)):
            with self.subTest(name=name):
                prepared=self.prepare(name)
                self.assertEqual(prepared.provenance["tracker_parameters"]["tracker_type"],backend)
                self.assertEqual(prepared.confidence_override,override)
                self.assertEqual(Path(prepared.detection["model"]).parent,self.weights)
                self.assertIn("config_files",prepared.provenance)
                self.assertEqual(len(prepared.weights),2 if name=="botsort_reid" else 1)

    def test_reid_missing_blocks_torch_before_inference_without_fallback(self):
        with patch.object(video_runner,"load_torch") as torch:
            with self.assertRaisesRegex(RuntimeError,"yolo26n-cls.pt"):
                video_runner.prepare_runtime(video_runner.RunOptions("tracking","cpu","botsort_reid",str(self.weights)))
        torch.assert_not_called()

    def test_unknown_and_network_weight_roots_are_rejected(self):
        for name,path in (("unknown",self.weights),("bytetrack","https://example.invalid/weights"),
                          ("bytetrack",r"\\server\weights")):
            with self.assertRaises(ValueError):tracker_runtime.resolve_resources(name,path,"yolo26n.pt")

    def test_backend_absence_is_not_a_fallback(self):
        with patch.object(tracker_runtime,"_load_yolo"), \
             patch.dict(sys.modules,{"ultralytics.trackers.track":NS(TRACKER_MAP={})}):
            with self.assertRaisesRegex(RuntimeError,"no disponible"):
                tracker_runtime.check_backend("fasttrack")

    def test_network_and_weight_mutations_blocked_only_inside_scope(self):
        weight=self.weights/"yolo26n.pt"
        before=weight.read_bytes()
        with tracker_runtime.local_processing([weight]):
            with self.assertRaisesRegex(RuntimeError,"Red bloqueada"):
                socket.getaddrinfo("example.invalid",443)
            with self.assertRaises(RuntimeError):weight.write_bytes(b"must never happen")
            with self.assertRaises(RuntimeError):weight.unlink()
            with tracker_runtime.local_processing([]):
                with self.assertRaises(RuntimeError):weight.write_bytes(b"nested scope")
        self.assertEqual(weight.read_bytes(),before)
        # Emitir el evento sin abrir conexión prueba que el guard ya está desactivado.
        sys.audit("socket.connect",None,None)

    def test_model_scope_restores_cwd_after_error(self):
        before=Path.cwd()
        with self.assertRaisesRegex(ValueError,"own failure"):
            with tracker_runtime.local_processing([],self.weights):
                self.assertEqual(Path.cwd(),self.weights)
                raise ValueError("own failure")
        self.assertEqual(Path.cwd(),before)

    def test_unsupported_device_never_initializes_backend(self):
        with patch.object(video_runner,"load_torch",return_value=self.torch), \
             patch.object(video_runner,"validate_device",side_effect=RuntimeError("CUDA unavailable")), \
             patch.object(video_runner,"check_backend") as backend:
            with self.assertRaisesRegex(RuntimeError,"CUDA unavailable"):
                video_runner.prepare_runtime(video_runner.RunOptions("tracking","cuda:0","bytetrack",str(self.weights)))
        backend.assert_not_called()


class PipelineTests(unittest.TestCase):
    def test_real_mp4_decoder_simulated_tracker_then_replay_without_second_inference(self):
        with temporary_directory() as temp:
            root=Path(temp)
            video,_,zones=fixture(root,real_video=True)
            weights=root/"weights";weights.mkdir()
            (weights/"yolo26n.pt").write_bytes(b"not a model; simulated inference only")
            calls=[]
            class Engine:
                reid_diagnostics=None
                def __init__(self,config,tracking,**kwargs):
                    self.config={**config,"device":kwargs["device_override"]}
                    self.device_resolution=DeviceResolution(config["device"],None,kwargs["device_override"])
                    self.frames=0
                    self.tracking=tracking
                    calls.append(self)
                def track(self,frame):
                    i=self.frames;self.frames+=1
                    return FrameTracks((Track(20 if i<2 else 100,30,60 if i<2 else 140,80,.9,0,1),),(),1.,2.)
            before=file_sha256(video)
            torch=NS(version=NS(cuda=None),cuda=MagicMock())
            with patch.object(video_runner,"load_torch",return_value=torch), \
                 patch.object(video_runner,"validate_device"), \
                 patch.object(video_runner,"check_backend",return_value="SIMULATED_BACKEND"), \
                 patch.object(video_runner,"PersonTracker",Engine),redirect_stdout(io.StringIO()):
                result=count_mp4.main(["process","--video",str(video),"--zones",str(zones),
                    "--tracker","bytetrack","--device","cpu","--weights-dir",str(weights),
                    "--output",str(root/"results")])
            self.assertEqual(result,0)
            self.assertEqual((len(calls),calls[0].frames),(1,4))
            self.assertEqual(file_sha256(video),before)
            counts=list((root/"results/counting").glob("*/summary.json"))
            self.assertEqual(json.loads(counts[0].read_text())["entries"],1)
            tracking=[p for p in (root/"results").iterdir() if (p/"summary.json").is_file()][0]
            meta_path=next(tracking.glob("*/metadata.json"))
            metadata=json.loads(meta_path.read_text())
            self.assertEqual(metadata["configuration"]["backend_class"],"SIMULATED_BACKEND")
            self.assertEqual(metadata["weights_used"][0]["sha256"],file_sha256(weights/"yolo26n.pt"))
            with patch.object(video_runner,"run_cases",side_effect=AssertionError("Repeated inference")), \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(count_mp4.main(["count","--video",str(video),"--zones",str(zones),
                    "--predictions",str(tracking),"--output",str(root/"results")]),0)
            self.assertEqual(len(list((root/"results/counting").glob("*/summary.json"))),2)

    def test_track_cli_needs_no_zones_and_passes_explicit_selection(self):
        with temporary_directory() as temp:
            video=Path(temp)/"sample.mp4";video.write_bytes(b"hash fixture")
            summary=dict(status="completed",results=[],not_processed=[])
            with patch.object(video_runner,"run_cases",return_value=(Path(temp),summary)) as run, \
                 redirect_stdout(io.StringIO()):
                code=count_mp4.main(["track","--video",str(video),"--device","cuda:0",
                    "--tracker","fasttrack","--output",temp])
            self.assertEqual(code,0)
            options=run.call_args.args[1]
            self.assertEqual((options.tracker,options.device),("fasttrack","cuda:0"))


if __name__ == "__main__":unittest.main()
