"""MP4 sintético real y dibujo OpenCV; interfaz gráfica simulada, sin inferencia."""

import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from src import view_count_results as viewer
from src.count_replay import run_count_replay
from src.saved_results import ResultsError
from src.video_source import file_sha256
from h52_test_support import fixture
from video_test_support import temporary_directory


class UI:
    def __init__(self, keys=()):
        self.keys = iter(keys)
        self.images = []
        self.closed = False
        self.now = 0

    def __getattr__(self, name):
        return getattr(cv2, name)

    def namedWindow(self, *args):
        pass

    def imshow(self, window, image):
        self.images.append(image.copy())

    def waitKey(self, delay):
        self.now += delay/1000
        return next(self.keys, -1)

    def getWindowProperty(self, *args):
        return 1

    def destroyWindow(self, *args):
        self.closed = True


class CountViewerTests(unittest.TestCase):
    def setUp(self):
        temp = temporary_directory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.video, self.case, self.zones = fixture(self.root, real_video=True)
        self.directory, summary = run_count_replay(self.video, self.zones, self.case, self.root/"outputs")
        self.assertEqual((summary["status"], summary["entries"]), ("completed", 1))

    def load(self):
        return viewer.load_view(self.video, self.directory)

    def mutate_json(self, name, callback):
        path = self.directory/name
        data = json.loads(path.read_text())
        callback(data)
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_frame_indexed_totals_rewind_pause_and_reasons(self):
        view = self.load()
        annotations = viewer.Annotations(view)
        for index, expected in ((0,0),(2,0),(3,1),(3,1),(0,0),(3,1)):
            lines = annotations.lines(view.case.frame(index))
            self.assertIn(f"IN: {expected} | OUT: 0", lines[0])
        self.assertTrue(any("estabilidad insuficiente" in s for s in annotations.lines(view.case.frame(0))))
        self.assertTrue(any("confirmado IN" in s for s in annotations.lines(view.case.frame(3))))

    def test_opencv_layers_keep_original_pixels_and_show_zone_labels(self):
        view = self.load()
        frame = np.zeros((160,160,3), dtype=np.uint8)
        text = []
        original = cv2.putText
        def put(*args, **kwargs):
            text.append(args[1])
            return original(*args, **kwargs)
        with patch.object(cv2,"putText",side_effect=put):
            result = viewer.render_count_overlay(cv2,frame,view.case.frame(3),viewer.Annotations(view))
        self.assertFalse(frame.any())
        self.assertGreater(result.shape[0],160)
        self.assertEqual(result.shape[1],960)
        self.assertTrue(result[:160,:160].any())
        for label in ("A exterior","B puerta","IN: 1","ID 1","confirmado IN"):
            self.assertTrue(any(label in line for line in text), label)

    def test_reader_does_not_import_inference_or_decoder(self):
        code = ("import sys; from src.view_count_results import load_view; "
                "load_view(sys.argv[1],sys.argv[2]); "
                "assert not any(n in sys.modules for n in ('torch','ultralytics','cv2'))")
        result = subprocess.run([sys.executable,"-B","-c",code,str(self.video),str(self.directory)],
                                capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_both_directions_are_cumulative_only_from_their_event_frame(self):
        view = self.load()
        # Trace-layer unit fixture; does not assert a physical transition.
        view.events = [dict(frame_index=1,direction="IN",track_id=1,timestamp=.2),
                       dict(frame_index=3,direction="OUT",track_id=1,timestamp=.6)]
        annotations = viewer.Annotations(view)
        self.assertIn("IN: 0 | OUT: 0",annotations.lines(view.case.frame(0))[0])
        self.assertIn("IN: 1 | OUT: 0",annotations.lines(view.case.frame(2))[0])
        self.assertIn("IN: 1 | OUT: 1",annotations.lines(view.case.frame(3))[0])

    def test_real_decoder_full_playback_no_writes_and_no_counter(self):
        view = self.load()
        before = {p:file_sha256(p) for p in self.root.rglob("*") if p.is_file()}
        ui = UI()
        with patch("src.count_engine.TransitionCounter.update", side_effect=AssertionError("No recount")):
            self.assertEqual(viewer.play_count(ui, view, clock=lambda:ui.now),4)
        self.assertEqual(len(ui.images),4)
        self.assertTrue(ui.closed)
        self.assertEqual(before,{p:file_sha256(p) for p in self.root.rglob("*") if p.is_file()})

    def test_pause_steps_and_quit_reuse_player_controls(self):
        ui = UI((ord(" "),ord("n"),ord("."),ord("q")))
        view = self.load()
        self.assertEqual(viewer.play_count(ui,view,clock=lambda:ui.now),3)
        self.assertEqual(len(ui.images),4)  # frame 0 is redrawn paused, not counted twice
        self.assertTrue(ui.closed)

    def test_gui_error_and_interrupt_release_capture_and_window(self):
        from src.video_source import VideoSource
        for exception in (cv2.error("GUI fixture"), KeyboardInterrupt()):
            with self.subTest(error=type(exception)):
                source = VideoSource(self.video)
                ui = UI()
                with patch("src.view_results.VideoSource", return_value=source), \
                        patch.object(ui,"imshow",side_effect=exception), self.assertRaises(type(exception)):
                    viewer.play_count(ui,self.load())
                self.assertFalse(source.capture.isOpened())
                self.assertTrue(ui.closed)

    def test_invalid_status_summary_and_source_hash_stop_before_gui(self):
        original = (self.directory/"run.json").read_bytes()
        for callback in (lambda d:d.update(status="failed"),
                         lambda d:d.update(zones_file_sha256="0"*64),
                         lambda d:d.update(predictions_hashes={}),
                         lambda d:d.update(orientation={"A":"puerta","B":"exterior"})):
            with self.subTest(callback=callback):
                self.mutate_json("run.json",callback)
                with self.assertRaises(ResultsError):
                    self.load()
                (self.directory/"run.json").write_bytes(original)
        self.mutate_json("summary.json",lambda d:d.update(entries=2))
        with self.assertRaises(ResultsError):
            self.load()

    def test_corrupt_events_and_diagnostics_are_rejected(self):
        for name, updates in (("events.jsonl",dict(direction="OUT")),
                              ("events.jsonl",dict(frame_index=4)),
                              ("diagnostics.jsonl",dict(phase="INVENTADA")),
                              ("diagnostics.jsonl",dict(timestamp=float("inf")))):
            with self.subTest(name=name, updates=updates):
                path = self.directory/name
                original = path.read_bytes()
                rows = [json.loads(s) for s in path.read_text().splitlines()]
                rows[0].update(updates)
                path.write_text("\n".join(json.dumps(r) for r in rows)+"\n",encoding="utf-8")
                with self.assertRaises(ResultsError):
                    self.load()
                path.write_bytes(original)

    def test_changed_resource_during_display_is_reported(self):
        view = self.load()
        with (self.directory/"events.jsonl").open("a",encoding="utf-8") as stream:
            stream.write("\n")
        with self.assertRaises(ResultsError):
            view.verify_unchanged()

    def test_network_video_is_rejected_before_loading_profile(self):
        for value in ("https://example.invalid/video.mp4", r"\\server\share\video.mp4"):
            with self.subTest(value=value), patch.object(viewer,"load_video_zones") as zones:
                with self.assertRaises(ResultsError):
                    viewer.load_view(value,self.directory)
                zones.assert_not_called()

    def test_cli_success_interrupt_and_invalid_result(self):
        args = ["--video",str(self.video),"--count-results",str(self.directory)]
        with patch.object(viewer,"play_count",return_value=4) as play:
            self.assertEqual(viewer.main(args),0)
            play.assert_called_once()
        with patch.object(viewer,"play_count",side_effect=KeyboardInterrupt()):
            self.assertEqual(viewer.main(args),130)
        self.mutate_json("summary.json",lambda d:d.update(status="interrupted"))
        with patch.object(viewer,"play_count") as play:
            self.assertEqual(viewer.main(args),1)
            play.assert_not_called()


if __name__ == "__main__":
    unittest.main()
