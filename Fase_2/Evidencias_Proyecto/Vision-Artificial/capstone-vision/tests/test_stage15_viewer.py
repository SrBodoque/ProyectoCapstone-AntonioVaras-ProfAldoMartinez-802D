"""Dibujo OpenCV sobre arrays y controles simulados; no abre ventanas ni usa IA."""

import io
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

from src import view_results
from src.result_overlay import TrailHistory, render_frame, track_color
from src.saved_results import Observation, ResultsError, SavedFrame, load_case, select_case
from src.video_source import FramePacket, file_sha256
from stage15_test_support import box, row, write_case
from video_test_support import temporary_directory


def observation(identifier=1, x=20):
    return Observation(x, 80, x + 30, 130, .9, identifier)


class OverlayTests(unittest.TestCase):
    def test_multiple_ids_colors_confidence_and_untracked_differ(self):
        saved = SavedFrame(0, (observation(1), observation(2, 80)), (), (observation(None, 120),))
        history = TrailHistory()
        history.update(saved)
        frame = np.zeros((180, 180, 3), dtype=np.uint8)
        result = render_frame(cv2, frame, saved, history, total=1, timestamp_ms=0)
        self.assertFalse(np.any(frame))
        self.assertTrue(np.any(result[80:135]))
        self.assertNotEqual(track_color(1), track_color(2))
        self.assertEqual(track_color(1), track_color(1))
        fake = MagicMock()
        render_frame(fake, frame, saved, history)
        labels = [call.args[1] for call in fake.putText.call_args_list]
        self.assertTrue(any("ID 1 | 0.90" in label for label in labels))
        self.assertTrue(any("sin ID" in label for label in labels))
        self.assertTrue(any("tracks: 2" in label for label in labels))

    def test_absent_confidence_and_clipped_coordinates(self):
        saved = SavedFrame(0, (), (Observation(-20, -30, 300, 300), Observation(400, 400, 500, 500)), ())
        fake = MagicMock()
        frame = np.zeros((160, 160, 3), dtype=np.uint8)
        render_frame(fake, frame, saved, TrailHistory())
        fake.rectangle.assert_called_once()
        self.assertEqual(fake.rectangle.call_args.args[1:3], ((0, 0), (159, 159)))
        self.assertFalse(any("0.90" in call.args[1] for call in fake.putText.call_args_list))

    def test_missing_predictions_are_visible_and_future_overlays_are_separate(self):
        fake, overlay = MagicMock(), MagicMock()
        frame = np.zeros((160, 160, 3), dtype=np.uint8)
        render_frame(fake, frame, SavedFrame(0, available=False), TrailHistory(), overlays=(overlay,))
        self.assertTrue(any("SIN PREDICCION" in c.args[1] for c in fake.putText.call_args_list))
        overlay.assert_called_once()
        self.assertIsNot(overlay.call_args.args[1], frame)

    def test_history_limited_by_frames_and_disappearance_does_not_join_gap(self):
        history = TrailHistory(3)
        history.update(SavedFrame(0, (observation(1), observation(2))))
        history.update(SavedFrame(1))
        history.update(SavedFrame(2, (observation(1, 25),)))
        fake = MagicMock()
        render_frame(fake, np.zeros((160, 160, 3), dtype=np.uint8), SavedFrame(2, (observation(1, 25),)), history)
        fake.line.assert_not_called()
        history.update(SavedFrame(3, (observation(1, 26),)))
        self.assertNotIn(2, history.points)
        self.assertEqual([p[0] for p in history.points[1]], [2, 3])
        history.update(SavedFrame(4, (observation(1, 27),)))
        history.update(SavedFrame(5, (observation(1, 28),)))
        self.assertEqual([p[0] for p in history.points[1]], [3, 4, 5])

    def test_missing_frame_or_index_discontinuity_resets_history(self):
        history = TrailHistory()
        history.update(SavedFrame(0, (observation(),)))
        history.update(SavedFrame(1, available=False))
        self.assertFalse(history.points)
        history.update(SavedFrame(2, (observation(),)))
        history.update(SavedFrame(0, (observation(2),)))
        self.assertEqual(list(history.points), [2])

    def test_history_options(self):
        for value in (0, 301, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                TrailHistory(value)


class ControlsTests(unittest.TestCase):
    def test_pause_single_step_resume_quit(self):
        controls = view_results.PlaybackControls()
        self.assertEqual(controls.handle(ord("n")), "wait")
        self.assertEqual(controls.handle(ord(" ")), "redraw")
        self.assertTrue(controls.paused)
        self.assertEqual(controls.handle(ord("n")), "next")
        self.assertTrue(controls.paused)
        self.assertEqual(controls.handle(ord(".")), "next")
        controls.handle(ord(" "))
        self.assertFalse(controls.paused)
        self.assertEqual(controls.handle(ord("q")), "quit")
        self.assertEqual(controls.handle(27), "quit")


class FakeSource:
    def __init__(self, count=3, fps=25):
        self.metadata = dict(width=160, height=160, reported_frames=count, reported_fps=fps)
        self.count = count
        self.frames_read = 0
        self.status, self.reason = "completed", "test"
        self.released = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.released = True

    def __iter__(self):
        for index in range(self.count):
            self.frames_read += 1
            yield FramePacket(index, index * 40, "mock", np.zeros((160, 160, 3), dtype=np.uint8), .1)


class PlayerTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.video = self.root / "video.mp4"
        self.video.write_bytes(b"player fixture")
        self.path = write_case(self.root / "case", self.video, [row(i, [box()]) for i in range(3)])
        self.case = load_case(self.path)
        self.ui = MagicMock()
        self.ui.error = cv2.error
        self.ui.getWindowProperty.return_value = 1
        self.now = 0

    def wait(self, delay):
        self.now += delay / 1000
        return -1

    def clock(self):
        return self.now

    def test_full_playback_waits_for_original_fps_and_releases(self):
        source = FakeSource()
        self.ui.waitKey.side_effect = self.wait
        with patch.object(view_results, "VideoSource", return_value=source):
            self.assertEqual(view_results.play(self.ui, self.video, self.case, clock=self.clock), 3)
        self.assertTrue(source.released)
        self.assertGreaterEqual(self.now, .12)
        self.assertLess(self.now, .15)
        self.ui.destroyWindow.assert_called_once()

    def test_paused_steps_decode_exactly_one_frame_each(self):
        source = FakeSource(5)
        self.case.metadata["video"]["reported_frames"] = 5
        self.ui.waitKey.side_effect = [ord(" "), ord("n"), ord("."), ord("q")]
        seen = []
        def render(cv, frame, saved, history, **kwargs):
            seen.append((saved.index, kwargs["paused"]))
            return frame.copy()
        with patch.object(view_results, "VideoSource", return_value=source), \
                patch.object(view_results, "render_frame", side_effect=render):
            self.assertEqual(view_results.play(self.ui, self.video, self.case, clock=self.clock), 3)
        self.assertEqual(seen, [(0, False), (0, True), (1, True), (2, True)])
        self.assertEqual(source.frames_read, 3)
        self.assertTrue(source.released)

    def test_closed_window_and_escape_release(self):
        for key, visible in ((27, 1), (-1, 0)):
            with self.subTest(key=key):
                self.ui.reset_mock()
                self.ui.waitKey.return_value = key
                self.ui.getWindowProperty.return_value = visible
                source = FakeSource()
                with patch.object(view_results, "VideoSource", return_value=source):
                    self.assertEqual(view_results.play(self.ui, self.video, self.case), 1)
                self.assertTrue(source.released)
                self.ui.destroyWindow.assert_called_once()

    def test_render_window_and_interrupt_errors_release_resources(self):
        for method, error in (("imshow", cv2.error("draw")), ("namedWindow", cv2.error("gui")), ("waitKey", KeyboardInterrupt())):
            with self.subTest(method=method):
                ui = MagicMock(error=cv2.error)
                getattr(ui, method).side_effect = error
                source = FakeSource()
                with patch.object(view_results, "VideoSource", return_value=source), self.assertRaises(type(error)):
                    view_results.play(ui, self.video, self.case)
                self.assertTrue(source.released)
                ui.destroyWindow.assert_called_once()

    def test_incompatible_geometry_stops_before_opening_window(self):
        source = FakeSource()
        source.metadata["width"] = 320
        with patch.object(view_results, "VideoSource", return_value=source), self.assertRaises(ResultsError):
            view_results.play(self.ui, self.video, self.case)
        self.ui.namedWindow.assert_not_called()
        self.assertTrue(source.released)

    def test_failed_read_is_not_success(self):
        source = FakeSource()
        source.status, source.reason = "failed", "decoder"
        self.ui.waitKey.side_effect = self.wait
        with patch.object(view_results, "VideoSource", return_value=source), self.assertRaisesRegex(ResultsError, "decoder"):
            view_results.play(self.ui, self.video, self.case, clock=self.clock)
        self.assertTrue(source.released)

    def test_cli_exit_codes_for_normal_interrupt_and_missing_video(self):
        with patch.object(view_results, "play", return_value=3):
            self.assertEqual(view_results.main(["--video", str(self.video), "--results", str(self.path)]), 0)
        with patch.object(view_results, "play", side_effect=KeyboardInterrupt()):
            self.assertEqual(view_results.main(["--video", str(self.video), "--results", str(self.path)]), 130)
        with self.assertLogs(view_results.LOGGER, level="ERROR"):
            self.assertEqual(view_results.main(["--video", "missing.mp4", "--results", str(self.path)]), 1)


class RealDecoderOfflineTests(unittest.TestCase):
    def test_actual_video_decoder_with_saved_predictions_and_fake_window(self):
        with temporary_directory() as temp:
            root = Path(temp)
            video = root / "synthetic.mp4"
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 25, (160, 160))
            if not writer.isOpened():
                writer.release()
                self.skipTest("Encoder MP4 no disponible; no equivale a validación aprobada.")
            try:
                for value in (10, 80, 160):
                    writer.write(np.full((160, 160, 3), value, dtype=np.uint8))
            finally:
                writer.release()
            directory = write_case(root / "case", video, [row(2, [box(2)]), row(0, [box(1)])],
                video=dict(width=160, height=160, reported_frames=3, reported_fps=25))
            _, case = select_case(directory, video)
            before = {p.name: file_sha256(p) for p in directory.iterdir()}
            ui = MagicMock(error=cv2.error)
            ui.getWindowProperty.return_value = 1
            now = [0]
            def wait(delay):
                now[0] += delay / 1000
                return -1
            ui.waitKey.side_effect = wait
            with self.assertLogs(view_results.LOGGER, level="WARNING"):
                self.assertEqual(view_results.play(ui, video, case, clock=lambda: now[0]), 3)
            self.assertEqual(before, {p.name: file_sha256(p) for p in directory.iterdir()})
            ui.destroyWindow.assert_called_once()


if __name__ == "__main__":
    unittest.main()
