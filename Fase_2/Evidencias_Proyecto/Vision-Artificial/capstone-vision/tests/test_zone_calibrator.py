"""Calibrador: modelo de edición real; eventos de GUI/cámara simulados."""

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from src import zone_calibrator as c
from src.config import PROJECT_ROOT, load_config
from src.zones import ZoneStore
from video_test_support import temporary_directory
from zone_test_support import A, B, profile, make_ui, camera_module


class EditorTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory(); self.addCleanup(self.temp.cleanup)
        self.store = ZoneStore(Path(self.temp.name) / "zones")
        self.editor = c.CalibrationEditor(self.store, 1, 640, 480)

    def draw(self):
        for name, points in (("A", A), ("B", B)):
            self.editor.key(ord(name))
            for x, y in points: self.editor.mouse("down", x * 640, y * 480, 640, 480)
            self.editor.mouse("right", 300, 200, 640, 480)

    def save(self, name="habitacion"):
        self.editor.key(ord("s"))
        for char in name: self.editor.key(ord(char))
        self.editor.key(13)

    def test_mouse_draws_two_closed_polygons_and_saves(self):
        self.draw()
        self.assertTrue(self.editor.dirty)
        self.assertTrue(all(self.editor.closed.values()))
        self.save()
        self.assertEqual(self.store.load_active().name, "habitacion")
        self.assertFalse(self.editor.dirty)
        self.assertEqual(self.editor.active_name, "habitacion")

    def test_edit_active_drag_undo_redraw_and_cancel_preserves_disk(self):
        original = profile(); self.store.save_and_activate(original)
        self.editor = c.CalibrationEditor(self.store, 1, 640, 480)
        x, y = self.editor.polygons["A"][0]
        self.editor.mouse("down", x*640, y*480, 640, 480)
        self.editor.mouse("move", 390, 70, 640, 480); self.editor.mouse("up", 390, 70, 640, 480)
        self.assertEqual(self.editor.polygons["A"][0], (390/640, 70/480))
        self.editor.key(ord("u")); self.assertEqual(len(self.editor.polygons["A"]), 3)
        self.editor.key(ord("r")); self.assertEqual(self.editor.polygons["A"], [])
        self.editor.request_exit(); self.assertEqual(self.editor.mode, "confirm")
        self.editor.key(ord("n")); self.assertFalse(self.editor.exit_requested)
        self.editor.request_exit(); self.editor.key(ord("y")); self.assertTrue(self.editor.exit_requested)
        self.assertEqual(self.store.load_active(), original)
        self.assertEqual(self.store.load("prueba"), original)

    def test_cancel_filename_and_overwrite_do_not_change_active(self):
        self.store.save_and_activate(profile("habitacion")); self.draw()
        self.editor.key(ord("s")); self.editor.key(27)
        self.assertFalse((self.store.directory / "validacion.json").exists())
        self.save(); self.assertEqual(self.editor.mode, "confirm")
        self.editor.key(ord("n"))
        self.assertEqual(self.store.load_active(), profile("habitacion"))
        self.assertTrue(self.editor.dirty)

    def test_edit_and_confirm_overwrite(self):
        self.store.save_and_activate(profile())
        self.editor = c.CalibrationEditor(self.store, 1, 640, 480)
        self.editor.mouse("down", A[0][0]*640, A[0][1]*480, 640, 480)
        self.editor.mouse("move", 370, 60, 640, 480); self.editor.mouse("up", 370, 60, 640, 480)
        self.editor.key(ord("s")); self.editor.key(13)
        self.assertEqual(self.editor.mode, "confirm")
        self.editor.key(ord("y"))
        self.assertEqual(self.store.load_active().a[0], (370/640, 60/480))
        self.assertFalse(self.editor.dirty)

    def test_select_preview_then_activate_existing_profile(self):
        self.store.save_and_activate(profile("a")); self.store.save_and_activate(profile("b"))
        self.editor = c.CalibrationEditor(self.store, 1, 640, 480)
        self.editor.key(ord("p")); self.assertEqual(self.editor.mode, "profiles")
        self.editor.key(ord("j")); self.editor.key(ord("k")); self.editor.key(13)
        self.assertEqual(self.editor.name, "a")
        self.assertEqual(self.store.load_active().name, "b")
        self.editor.key(ord("g")); self.assertEqual(self.store.load_active().name, "a")

    def test_dirty_profile_switch_requires_confirmation(self):
        self.store.save_and_activate(profile("uno")); self.draw()
        self.editor.key(ord("p")); self.editor.key(13)
        self.assertEqual(self.editor.mode, "confirm")
        self.editor.key(ord("n")); self.assertTrue(self.editor.dirty)
        self.editor.key(ord("p")); self.editor.key(13); self.editor.key(ord("y"))
        self.assertEqual(self.editor.name, "uno"); self.assertFalse(self.editor.dirty)

    def test_new_profile_discard_protection(self):
        self.draw(); self.editor.key(ord("n")); self.assertEqual(self.editor.mode, "confirm")
        self.editor.key(27); self.assertTrue(self.editor.dirty)
        self.editor.key(ord("n")); self.editor.key(ord("y"))
        self.assertEqual(self.editor.polygons, {"A":[], "B":[]})
        self.assertEqual(self.store.names(), [])

    def test_incompatible_camera_blocks_activation_and_requires_redraw(self):
        self.store.save_and_activate(profile(camera=2))
        self.editor = c.CalibrationEditor(self.store, 1, 640, 480)
        self.assertTrue(self.editor.incompatible)
        self.editor.key(ord("g")); self.assertEqual(self.store.load_active().camera_index, 2)
        self.editor.key(ord("s")); self.assertEqual(self.editor.mode, "edit")
        self.editor.key(ord("r")); self.assertFalse(self.editor.incompatible)
        self.assertEqual(self.editor.polygons, {"A":[], "B":[]})
        self.draw(); self.editor.key(ord("s")); self.editor.key(13); self.editor.key(ord("y"))
        self.assertEqual(self.store.load_active().camera_index, 1)

    def test_incompatible_aspect_and_corrupt_active_are_visible(self):
        self.store.save_and_activate(profile(width=1280, height=720))
        self.assertTrue(c.CalibrationEditor(self.store, 1, 640, 480).incompatible)
        (self.store.directory / "active.json").write_text("{")
        editor = c.CalibrationEditor(self.store, 1, 640, 480)
        self.assertIn("No se pudo leer", editor.status)
        self.assertEqual(editor.polygons, {"A":[], "B":[]})

    def test_incomplete_and_overlap_cannot_be_saved(self):
        self.editor.key(ord("s")); self.assertIn("Cierre", self.editor.status)
        self.editor.polygons = {"A":list(A), "B":list(A)}; self.editor.closed = {"A":True,"B":True}
        self.editor.key(ord("s")); self.assertIn("superponen", self.editor.status)
        self.assertEqual(self.store.names(), [])

    def test_mouse_ignores_toolbar_and_modal_and_limits_points(self):
        self.editor.mouse("down", 20, 600, 640, 480)
        self.assertEqual(self.editor.polygons["A"], [])
        self.editor.mode = "name"; self.editor.mouse("down", 10, 10, 640, 480)
        self.assertEqual(self.editor.polygons["A"], [])
        self.editor.mode = "edit"
        for i in range(20): self.editor.mouse("down", 12+30*i, 50, 640, 480)
        self.assertEqual(len(self.editor.polygons["A"]), 16)

    def test_reject_dangerous_name_and_disk_error_without_losing_edits(self):
        self.draw(); self.editor.key(ord("s")); self.editor.name_input = "../outside"; self.editor.key(13)
        self.assertEqual(self.store.names(), [])
        self.editor.name_input = "normal"
        with patch.object(self.store, "save_and_activate", side_effect=OSError("disk")): self.editor.key(13)
        self.assertTrue(self.editor.dirty); self.assertIn("disk", self.editor.status)

    def test_freeze_is_only_an_editor_flag(self):
        self.editor.key(32); self.assertTrue(self.editor.frozen)
        self.editor.key(32); self.assertFalse(self.editor.frozen)
        self.assertFalse(self.editor.dirty)
        self.assertFalse(self.store.directory.exists())

    def test_imports_without_ai_camera_or_writes(self):
        code = '''
import sys
sys.dont_write_bytecode=True
from unittest.mock import patch
with patch("builtins.input", side_effect=AssertionError), patch("os.replace", side_effect=AssertionError):
 import src.zones, src.zone_calibrator, src.track_zones
assert not any(m in sys.modules for m in ("torch","ultralytics","cv2","numpy","src.camera"))
'''
        r = subprocess.run([sys.executable, "-c", code], cwd=PROJECT_ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


class CalibratorLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory(); self.addCleanup(self.temp.cleanup)
        self.store = ZoneStore(Path(self.temp.name) / "zones")

    def test_q_esc_and_selected_camera_release(self):
        for key in (ord("q"), 27):
            ui, capture, _ = make_ui(); ui.waitKey.return_value = key
            with camera_module(ui): c.run_calibrator(ui, load_config(), self.store)
            self.assertEqual(capture.open.call_args.args[0], load_config()["camera_index"])
            capture.release.assert_called_once(); ui.destroyAllWindows.assert_called_once()
            self.assertFalse(self.store.directory.exists())

    def test_dirty_window_close_and_ctrl_c_request_confirmation(self):
        for scenario in ("q", "window", "window_error", "ctrl_c"):
            with self.subTest(scenario=scenario):
                ui, capture, _ = make_ui(); calls = 0
                def keys(delay):
                    nonlocal calls
                    calls += 1
                    if calls == 1:
                        callback = ui.setMouseCallback.call_args.args[1]
                        callback(ui.EVENT_LBUTTONDOWN, 100, 100, 0, None)
                        if scenario == "ctrl_c": raise KeyboardInterrupt()
                        return ord("q") if scenario == "q" else -1
                    return ord("y")
                ui.waitKey.side_effect = keys
                if scenario == "window": ui.getWindowProperty.side_effect = [-1, 1]
                if scenario == "window_error": ui.getWindowProperty.side_effect = ui.error("closed")
                with camera_module(ui): c.run_calibrator(ui, load_config(), self.store)
                self.assertEqual(calls, 2)
                if scenario.startswith("window"): self.assertEqual(ui.namedWindow.call_count, 2)
                capture.release.assert_called_once(); ui.destroyAllWindows.assert_called_once()
                self.assertFalse(self.store.directory.exists())

    def test_loading_read_ui_errors_release_resources(self):
        for scenario in ("open", "read", "ui", "aspect"):
            ui, capture, frame = make_ui(); expected = RuntimeError
            if scenario == "open": capture.open.return_value = False
            if scenario == "read":
                capture.read.side_effect = [(True, frame), (False, None)]; ui.waitKey.return_value = -1
            if scenario == "ui": ui.imshow.side_effect = ui.error("GUI"); expected = ui.error
            if scenario == "aspect":
                capture.read.side_effect = [(True, frame), (True, frame[:200])]; ui.waitKey.return_value = -1
            with self.subTest(scenario=scenario), camera_module(ui), self.assertRaises(expected):
                c.run_calibrator(ui, load_config(), self.store)
            self.assertGreaterEqual(capture.release.call_count, 1); ui.destroyAllWindows.assert_called_once()

    def test_freeze_keeps_exact_displayed_frame_only_in_memory(self):
        ui, capture, frame = make_ui()
        capture.read.side_effect = [(True, frame), (True, frame+1), (True, frame+2)]
        ui.waitKey.side_effect = [32, -1, ord("q")]
        seen = []
        def render(cv2, image, editor): seen.append(int(image[0,0,0])); return image
        with camera_module(ui), patch.object(c, "render_editor", side_effect=render):
            c.run_calibrator(ui, load_config(), self.store)
        self.assertEqual(seen, [70,70,70])
        self.assertFalse(self.store.directory.exists())
        capture.release.assert_called_once()

    def test_preview_fit_and_toolbar_do_not_change_calibration_coordinates(self):
        ui, _, frame = make_ui()
        editor = c.CalibrationEditor(self.store, 1, 640, 480)
        canvas = c.render_editor(ui, frame, editor)
        self.assertEqual(canvas.shape, (700,960,3))
        self.assertTrue((frame == 70).all())
        self.assertEqual(c.preview_size(frame), (640,480))
        editor.mouse("down", 320, 240, 640, 480)
        self.assertEqual(editor.polygons["A"], [(.5,.5)])


if __name__ == "__main__": unittest.main()
