"""Geometría/JSON reales sobre datos sintéticos: sin cámara ni modelo."""

import json
import math
import os
import random
import subprocess
import sys
from video_test_support import temporary_directory
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from src import zones as z
from zone_test_support import A, B, profile


class GeometryTests(unittest.TestCase):
    def test_valid_convex_concave_and_reversed(self):
        for p in (A, tuple(reversed(A)), ((0, 0), (1, 0), (1, .5), (.5, .5), (.5, 1), (0, 1)),
                  ((0, 0), (.5, 0), (1, 0), (1, 1), (0, 1))):
            result = z.validate_polygon(p)
            self.assertEqual(len(result), len(p))
            self.assertAlmostEqual(sum(abs(z.signed_area(t)) for t in z._triangles(result)), abs(z.signed_area(result)))

    def test_reject_degenerate_duplicate_and_backtracking(self):
        for p in ([], [(0, 0), (1, 1)], [(0, 0), (.5, .5), (1, 1)],
                  [(0, 0), (1, 0), (1, 1), (0, 0)],
                  [(0, 0), (.8, 0), (.4, 0), (.4, 1), (0, 1)],
                  [(0, 0), (1e-8, 0), (0, 1e-8)]):
            with self.subTest(p=p), self.assertRaises(z.ZoneError): z.validate_polygon(p)

    def test_reject_self_crossing_and_self_touching(self):
        for p in (((0, 0), (1, 1), (0, 1), (1, 0)),
                  ((0, 0), (1, 0), (.5, .5), (1, 1), (0, 1), (.5, .5))):
            with self.assertRaises(z.ZoneError): z.validate_polygon(p)

    def test_invalid_coordinates_types_and_finiteness(self):
        for value in (-.01, 1.01, float("nan"), float("inf"), -float("inf"), True, "0.5", None, 10**1000):
            with self.subTest(value=type(value)), self.assertRaises(z.ZoneError):
                z.validate_polygon(((0, 0), (1, 0), (value, .5)))
        for point in ((0,), (0, 0, 0), "bad", {}):
            with self.assertRaises(z.ZoneError): z.validate_polygon(((0, 0), (1, 0), point))

    def test_maximum_points(self):
        polygon = tuple((.5 + .4 * math.cos(i * 2 * math.pi / 16), .5 + .4 * math.sin(i * 2 * math.pi / 16)) for i in range(16))
        self.assertEqual(len(z.validate_polygon(polygon)), 16)
        with self.assertRaises(z.ZoneError): z.validate_polygon(polygon + ((.5, .5),))

    def test_overlap_containment_identical_and_crossing(self):
        square = ((0, 0), (1, 0), (1, 1), (0, 1))
        horizontal = ((0, .4), (1, .4), (1, .6), (0, .6))
        vertical = ((.4, 0), (.6, 0), (.6, 1), (.4, 1))
        for a, b in ((A, A), (square, A), (horizontal, vertical)):
            with self.assertRaisesRegex(z.ZoneError, "superponen"): z.validate_zones(a, b)

    def test_concave_indentation_is_not_overlap(self):
        concave = ((0, 0), (1, 0), (1, .3), (.3, .3), (.3, 1), (0, 1))
        inside_hollow = ((.5, .5), (.9, .5), (.9, .9), (.5, .9))
        z.validate_zones(concave, inside_hollow)
        self.assertEqual(z.point_location((.6, .6), concave), -1)

    def test_shared_edges_vertices_allowed_priority_a(self):
        a = ((0, 0), (.5, 0), (.5, 1), (0, 1))
        b = ((.5, 0), (1, 0), (1, 1), (.5, 1))
        p = z.ZoneProfile.create("bordes", 0, 100, 100, a, b)
        self.assertEqual(p.classify((50, 50), 100, 100), "A")
        self.assertEqual(p.classify((100, 100), 100, 100), "B")
        self.assertEqual(p.classify((0, 0), 100, 100), "A")
        z.validate_zones(((0, 0), (.5, 0), (.5, .5), (0, .5)), ((.5, .5), (1, .5), (1, 1), (.5, 1)))

    def test_random_rectangles_overlap_matches_analytic_intersection(self):
        rng = random.Random(42)
        for _ in range(300):
            x1, x2, x3, x4 = [rng.uniform(.01, .99) for _ in range(4)]
            y1, y2, y3, y4 = [rng.uniform(.01, .99) for _ in range(4)]
            ax, bx = sorted((x1, x2)), sorted((x3, x4)); ay, by = sorted((y1, y2)), sorted((y3, y4))
            if min(ax[1]-ax[0], bx[1]-bx[0], ay[1]-ay[0], by[1]-by[0]) < .01: continue
            rect = lambda x, y: ((x[0], y[0]), (x[1], y[0]), (x[1], y[1]), (x[0], y[1]))
            overlap = min(ax[1], bx[1]) > max(ax[0], bx[0]) and min(ay[1], by[1]) > max(ay[0], by[0])
            if overlap:
                with self.assertRaises(z.ZoneError): z.validate_zones(rect(ax, ay), rect(bx, by))
            else: z.validate_zones(rect(ax, ay), rect(bx, by))

    def test_normalized_pixels_roundtrip(self):
        self.assertEqual(z.pixel_point((.25, .6), 1000, 500), (250, 300))
        self.assertEqual(z.normalized_point(250, 300, 1000, 500), (.25, .6))
        self.assertIsNone(z.normalized_point(10, 500, 1000, 500))
        self.assertIsNone(z.normalized_point(-1, 10, 1000, 500))

    def test_bottom_center_not_box_center(self):
        self.assertEqual(z.bottom_center(NS(x1=10, y1=20, x2=30, y2=100)), (20, 100))
        with self.assertRaises(z.ZoneError): z.bottom_center(NS(x1=30, y1=20, x2=10, y2=100))
        with self.assertRaises(z.ZoneError): z.bottom_center(NS(x1=0, y1=0, x2=1, y2=float("nan")))

    def test_classification_a_b_outside_and_offscreen(self):
        p = profile()
        for point, expected in (((500, 200), "A"), ((100, 200), "B"), ((320, 200), "FUERA"),
                                ((-10, 200), "FUERA"), ((700, 200), "FUERA")):
            self.assertEqual(p.classify(point, 640, 480), expected)
        with self.assertRaises(z.ZoneError): p.classify((float("inf"), 0), 640, 480)

    def test_compatible_resolution_and_incompatible_camera_aspect(self):
        p = profile(); p.check_camera(1, 1280, 960)
        self.assertEqual(p.classify((1000, 400), 1280, 960), "A")
        with self.assertRaisesRegex(z.ZoneError, "índice"): p.check_camera(2, 640, 480)
        with self.assertRaisesRegex(z.ZoneError, "aspecto"): p.check_camera(1, 1280, 720)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory(); self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "zones"
        self.store = z.ZoneStore(self.directory)

    def test_read_missing_does_not_create_files(self):
        self.assertEqual(self.store.names(), [])
        with self.assertRaisesRegex(z.ZoneError, "zone_calibrator"): self.store.load_active()
        with self.assertRaises(z.ZoneError): self.store.load("missing")
        self.assertFalse(self.directory.exists())

    def test_save_load_active_and_new_store_persistence(self):
        p = profile(); self.store.save_and_activate(p)
        self.assertEqual(self.store.load(p.name), p)
        self.assertEqual(z.ZoneStore(self.directory).load_active(), p)
        self.assertEqual(set(x.name for x in self.directory.iterdir()), {"prueba.json", "active.json"})
        data = json.loads((self.directory / "prueba.json").read_text())
        self.assertEqual(set(data["zones"]), {"A", "B"})
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["reference_size"], [640, 480])

    def test_persistence_in_another_process(self):
        self.store.save_and_activate(profile())
        code = "import sys; from src.zones import ZoneStore; print(ZoneStore(sys.argv[1]).load_active().name)"
        r = subprocess.run([sys.executable, "-c", code, str(self.directory)], capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "prueba"), r.stderr)

    def test_activate_other_profile_and_guard_stale_review(self):
        a, b = profile("uno"), profile("dos")
        self.store.save_and_activate(a); self.store.save_and_activate(b)
        self.store.activate("uno", expected=a)
        self.assertEqual(self.store.load_active().name, "uno")
        with self.assertRaisesRegex(z.ZoneError, "cambió"): self.store.activate("uno", expected=b)
        self.assertEqual(self.store.load_active(), a)

    def test_overwrite_requires_explicit_confirmation(self):
        p = profile(); self.store.save_and_activate(p)
        before = {p.name:p.read_bytes() for p in self.directory.iterdir()}
        with self.assertRaisesRegex(z.ZoneError, "sobrescritura"): self.store.save_and_activate(p)
        self.assertEqual(before, {p.name:p.read_bytes() for p in self.directory.iterdir()})
        self.store.save_and_activate(p, overwrite=True)

    def test_profile_names_reject_paths_reserved_and_case(self):
        for value in ("../x", "/tmp/x", "a/b", "C:\\x", "foo.json", "active", "CON", "con", "com1", "x y", "área", "X", "", "x"*49, None):
            with self.subTest(value=value), self.assertRaises(z.ZoneError): self.store.load(value)
        for value in ("a", "habitacion_pruebas", "pasillo-2"): self.assertEqual(z.validate_name(value), value)

    def test_invalid_json_duplicate_keys_and_schema(self):
        self.directory.mkdir()
        for text in ('{', '{"schema_version":1,"schema_version":1}', '[]', '{}', '['*1200 + ']'*1200):
            (self.directory / "prueba.json").write_text(text)
            with self.assertRaises(z.ZoneError): self.store.load("prueba")
        valid = profile().to_dict()
        for key, value in (("schema_version", True), ("reference_size", [1, 480]), ("camera_index", True),
                           ("aspect_ratio", 2), ("zones", {"A": A}), ("profile_name", "../x")):
            with self.assertRaises(z.ZoneError): z.ZoneProfile.from_dict({**valid, key:value})
        with self.assertRaises(z.ZoneError): z.ZoneProfile.from_dict({**valid, "image": "forbidden"})

    def test_invalid_active_never_silently_uses_named_profile(self):
        self.store.save_and_activate(profile())
        for data in ({}, {"active_profile": "other", "calibration": profile().to_dict()}):
            (self.directory / "active.json").write_text(json.dumps(data))
            with self.assertRaises(z.ZoneError): self.store.load_active()

    def test_failed_write_flush_and_replace_preserve_active(self):
        self.store.save_and_activate(profile())
        before = (self.directory / "active.json").read_bytes()
        for target in ("os.fsync", "os.replace"):
            with patch("src.zones." + target, side_effect=OSError("disk")), self.assertRaises(z.ZoneError):
                self.store.save_and_activate(profile("otro"))
            self.assertEqual((self.directory / "active.json").read_bytes(), before)
            self.assertFalse(list(self.directory.glob(".pending-*")))
            self.assertFalse((self.directory / ".write-lock").exists())

    def test_activation_failure_keeps_previous_active_snapshot_even_same_name(self):
        original = profile(); self.store.save_and_activate(original)
        changed = z.ZoneProfile.create("prueba", 1, 1280, 960, A, B)
        real = os.replace
        def fail_active(source, destination):
            if Path(destination).name == "active.json": raise OSError("active failed")
            return real(source, destination)
        with patch("src.zones.os.replace", side_effect=fail_active), self.assertRaisesRegex(z.ZoneError, "no pudo activarse"):
            self.store.save_and_activate(changed, overwrite=True)
        self.assertEqual(self.store.load_active(), original)
        self.assertEqual(self.store.load("prueba"), changed)

    def test_existing_writer_lock_not_removed_or_bypassed(self):
        self.directory.mkdir(); (self.directory / ".write-lock").mkdir()
        with self.assertRaisesRegex(z.ZoneError, "guardado"): self.store.save_and_activate(profile())
        self.assertTrue((self.directory / ".write-lock").exists())
        self.assertFalse((self.directory / "active.json").exists())

    def test_symlink_and_oversized_file_rejected(self):
        self.directory.mkdir(); outside = Path(self.temp.name) / "outside.json"; outside.write_text("{}")
        try: (self.directory / "prueba.json").symlink_to(outside)
        except OSError: self.skipTest("Sistema sin permiso para crear enlaces simbólicos de prueba")
        with self.assertRaises(z.ZoneError): self.store.load("prueba")
        with self.assertRaises(z.ZoneError): self.store.save_and_activate(profile(), overwrite=True)
        self.assertEqual(outside.read_text(), "{}")
        (self.directory / "prueba.json").unlink(); (self.directory / "prueba.json").write_text(" "*65537)
        with self.assertRaises(z.ZoneError): self.store.load("prueba")


class ObservationTests(unittest.TestCase):
    def test_debounce_then_recent_transition_expires(self):
        view = z.ZoneObservations(stable_frames=3, recent_frames=2)
        for _ in range(3): self.assertIsNone(view.update([(1, "B")])[1])
        for _ in range(2): self.assertIsNone(view.update([(1, "A")])[1])
        self.assertEqual(view.update([(1, "A")])[1], "B -> A")
        self.assertEqual(view.update([(1, "A")])[1], "B -> A")
        self.assertIsNone(view.update([(1, "A")])[1])

    def test_still_person_and_boundary_jitter_do_not_generate_repeated_transitions(self):
        view = z.ZoneObservations()
        for _ in range(20): self.assertIsNone(view.update([(1, "B")])[1])
        for zone in ["A", "B"] * 30: self.assertIsNone(view.update([(1, zone)])[1])

    def test_absence_or_new_id_breaks_continuity(self):
        view = z.ZoneObservations(stable_frames=1)
        view.update([(1, "B")]); view.update([])
        self.assertIsNone(view.update([(1, "A")])[1])
        self.assertIsNone(view.update([(2, "B")])[2])
        self.assertEqual(len(view._states), 1)
        view.update([]); self.assertEqual(view._states, {})

    def test_each_id_and_outside_are_independent(self):
        view = z.ZoneObservations(stable_frames=1)
        view.update([(1, "B"), (2, "A")])
        result = view.update([(1, "FUERA"), (2, "B")])
        self.assertEqual(result, {1:"B -> FUERA", 2:"A -> B"})
        self.assertFalse(hasattr(view, "count_in"))


if __name__ == "__main__": unittest.main()
