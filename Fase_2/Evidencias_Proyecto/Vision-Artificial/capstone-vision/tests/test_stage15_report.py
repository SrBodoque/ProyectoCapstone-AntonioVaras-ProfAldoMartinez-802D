"""Presentación de resultados en detección/tracking/lotes; sin inferencia."""

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from src.processing_report import format_processing_report, print_processing_report
from src.video_source import file_sha256
from stage15_test_support import box, row, write_case
from video_test_support import temporary_directory


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.video = self.root / "people.mp4"
        self.video.write_bytes(b"report fixture")

    def summary(self, *names, status="completed"):
        return dict(status=status, results=[dict(case_id=name, status=status, frames_processed=2, error=None) for name in names], not_processed=[])

    def test_tracking_gpu_frame_and_object_counts_are_not_confused(self):
        data = row(0, [box(1), box(2)])
        data["untracked_detections"] = [box(None), box(None)]
        write_case(self.root / "a", self.video, [data, row(1)], elapsed_ms=2000)
        text = format_processing_report(self.root, self.summary("a"))
        for expected in ("people.mp4", "bytetrack", "cuda:0", "NVIDIA RTX 5060", "2 / 2", "Fotogramas con tracks: 1",
                         "2 cajas en 1 fotogramas", "2.000 s", "1.00 frames/s", "no son FPS de cámara"):
            self.assertIn(expected, text)
        self.assertNotIn("Personas: 2", text)

    def test_detection_cpu_and_no_id_boxes(self):
        data = row()
        data["detections"] = [box(None), box(None)]
        write_case(self.root / "a", self.video, [data], mode="detection", device_effective="cpu")
        text = format_processing_report(self.root, self.summary("a"))
        self.assertIn("tracker: no aplica", text)
        self.assertIn("Dispositivo efectivo: cpu", text)
        self.assertNotIn("GPU:", text)
        self.assertIn("Fotogramas con tracks: 0", text)
        self.assertIn("2 cajas en 1 fotogramas", text)

    def test_global_fps_uses_summed_frames_and_time_not_mean_of_fps(self):
        write_case(self.root / "a", self.video, [row(0)], elapsed_ms=1000)
        write_case(self.root / "b", self.video, [row(0), row(1), row(2)], elapsed_ms=1000)
        text = format_processing_report(self.root, self.summary("a", "b"))
        self.assertIn("Resumen global: 2 videos", text)
        self.assertIn("global de procesamiento: 2.00 frames/s", text)

    def test_report_preserves_all_structured_files(self):
        directory = write_case(self.root / "a", self.video)
        before = {p.name: file_sha256(p) for p in directory.iterdir()}
        format_processing_report(self.root, self.summary("a"))
        self.assertEqual(before, {p.name: file_sha256(p) for p in directory.iterdir()})

    def test_invalid_times_and_missing_metadata_not_invented(self):
        write_case(self.root / "a", self.video, elapsed_ms=-5, configuration={})
        text = format_processing_report(self.root, self.summary("a", "missing"))
        self.assertIn("Modelo: no registrado", text)
        self.assertIn("Rendimiento de procesamiento: N/D", text)
        self.assertIn("informe detallado no disponible", text)

    def test_partial_corrupt_results_and_global_error_are_visible(self):
        directory = write_case(self.root / "a", self.video, status="interrupted")
        text = format_processing_report(self.root, self.summary("a", status="interrupted"))
        self.assertIn("puede ser parcial", text)
        (directory / "predictions.jsonl").write_text('{')
        text = format_processing_report(self.root, {**self.summary("a", status="failed"), "error": "disk error"})
        self.assertIn("JSON inválido", text)
        self.assertIn("disk error", text)

    def test_unsafe_case_path_is_not_followed(self):
        text = format_processing_report(self.root, self.summary(".."))
        self.assertIn("identificador de caso inválido", text)

    def test_presentation_failure_does_not_change_exit_contract(self):
        with patch("src.processing_report.format_processing_report", side_effect=ValueError("bad data")), redirect_stdout(io.StringIO()) as output:
            print_processing_report(self.root, self.summary("a"))
        self.assertIn("informe no disponible", output.getvalue())

    def test_existing_cli_calls_report_and_preserves_success_failure_codes(self):
        from src import process_videos
        for status, code in (("completed", 0), ("failed", 1), ("incomplete", 1), ("interrupted", 130)):
            with self.subTest(status=status), patch.object(process_videos, "run_cases", return_value=(self.root, self.summary(status=status))) as run, \
                    patch.object(process_videos, "print_processing_report") as report:
                result = process_videos.main(["--video", str(self.video), "--mode", "tracking", "--device", "cpu"])
                self.assertEqual(result, code)
                self.assertEqual(run.call_count, 1)
                report.assert_called_once_with(self.root, self.summary(status=status))


if __name__ == "__main__":
    unittest.main()
