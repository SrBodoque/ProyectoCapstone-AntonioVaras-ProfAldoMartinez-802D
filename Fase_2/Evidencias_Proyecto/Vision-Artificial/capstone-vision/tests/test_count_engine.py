import math
import unittest
from dataclasses import asdict, replace

from src.count_engine import CountSettings, EntryCounter, Observation, Phase
from src.count_geometry import RouteGeometry, clearance
from src.zones import ZoneError
from count_test_support import A, B, ENTRY, RETURN, counter_at_b, profile, rotation, run_path


class EntryTests(unittest.TestCase):
    def test_normal_entry_exactly_one_event_after_leaving_b(self):
        engine = EntryCounter(profile())
        self.assertEqual(run_path(engine, ENTRY[:-1]), [])
        events = run_path(engine, ENTRY[-1:])
        self.assertEqual((engine.total_entries, len(events)), (1, 1))
        self.assertEqual((events[0].number, events[0].track_id, events[0].episode, events[0].timestamp), (1, 1, 1, 1.2))
        self.assertEqual(engine.states[1].phase, Phase.CONFIRMED)

    def test_reverse_exit_has_no_event_or_out_counter(self):
        engine = EntryCounter(profile())
        self.assertEqual(run_path(engine, RETURN[:6]), [])
        self.assertEqual(engine.states[1].phase, Phase.REVERSE)
        run_path(engine, RETURN[6:])
        self.assertEqual(engine.total_entries, 0)
        self.assertFalse(any("out" in key.lower() for key in vars(engine)))

    def test_approach_a_then_return_does_not_count(self):
        engine = EntryCounter(profile())
        run_path(engine, ENTRY[:3] + ((.45, .3, .5), (.6, .25, .5)))
        self.assertEqual(engine.total_entries, 0)
        self.assertEqual(engine.states[1].phase, Phase.CANCELLED)

    def test_standing_in_a_never_counts(self):
        engine = EntryCounter(profile())
        run_path(engine, tuple((i * .1, .28, .5) for i in range(200)))
        self.assertEqual(engine.total_entries, 0)

    def test_standing_in_b_after_a_never_counts(self):
        engine = counter_at_b()
        run_path(engine, tuple((.9 + i * .1, .62, .5) for i in range(200)))
        self.assertEqual(engine.total_entries, 0)

    def test_b_then_back_toward_a_cancels(self):
        engine = counter_at_b()
        run_path(engine, ((.9, .56, .5), (1.05, .5, .5), (1.2, .4, .5)))
        self.assertEqual(engine.total_entries, 0)
        self.assertEqual(engine.states[1].phase, Phase.CANCELLED)

    def test_lateral_b_exit_and_later_forward_progress_do_not_count(self):
        engine = counter_at_b()
        run_path(engine, ((.9, .64, .7), (1.05, .72, .72), (1.2, .8, .72)))
        self.assertEqual(engine.total_entries, 0)
        self.assertEqual(engine.states[1].phase, Phase.CANCELLED)

    def test_forward_progress_through_side_is_rejected(self):
        engine = counter_at_b()
        run_path(engine, ((.9, .69, .64), (1.05, .72, .68), (1.2, .8, .69)))
        self.assertEqual(engine.total_entries, 0)

    def test_corner_exit_is_ambiguous(self):
        engine = counter_at_b()
        run_path(engine, ((.9, .68, .63), (1.05, .73, .68), (1.2, .8, .72)))
        self.assertEqual(engine.total_entries, 0)

    def test_entry_then_return_does_not_subtract_or_repeat(self):
        engine = EntryCounter(profile())
        run_path(engine)
        self.assertEqual(run_path(engine, RETURN, offset=1.35), [])
        self.assertEqual(engine.total_entries, 1)
        self.assertEqual(engine.states[1].phase, Phase.IDLE)

    def test_full_return_and_new_entry_rearms_spatially(self):
        engine = EntryCounter(profile())
        run_path(engine)
        run_path(engine, RETURN, offset=1.35)
        events = run_path(engine, offset=2.55)
        self.assertEqual(engine.total_entries, 2)
        self.assertEqual((events[0].number, events[0].episode), (2, 2))

    def test_return_to_a_without_exterior_does_not_rearm(self):
        engine = EntryCounter(profile())
        run_path(engine)
        run_path(engine, RETURN[:6], offset=1.35)
        run_path(engine, ENTRY[2:], offset=2.)
        self.assertEqual(engine.total_entries, 1)

    def test_timer_alone_does_not_rearm_visible_id(self):
        engine = EntryCounter(profile())
        run_path(engine)
        run_path(engine, tuple((1.35 + i * .2, .76, .5) for i in range(200)))
        self.assertEqual(engine.states[1].phase, Phase.CONFIRMED)
        self.assertEqual(engine.total_entries, 1)

    def test_initial_b_then_forward_is_zero(self):
        engine = EntryCounter(profile())
        self.assertEqual(run_path(engine, ENTRY[4:]), [])
        self.assertEqual(engine.total_entries, 0)

    def test_initial_exit_then_legitimate_entry_counts_only_entry(self):
        engine = EntryCounter(profile())
        run_path(engine, RETURN)
        self.assertEqual(engine.total_entries, 0)
        run_path(engine, offset=1.2)
        self.assertEqual(engine.total_entries, 1)

    def test_even_single_initial_b_observation_blocks_unobserved_return(self):
        engine = EntryCounter(profile())
        run_path(engine, ((0., .58, .5), (.2, .4, .5), (.4, .28, .5), (.55, .28, .5)))
        run_path(engine, ENTRY[2:], offset=.5)
        self.assertEqual(engine.total_entries, 0)

    def test_direct_a_b_allowed_with_speed_and_dwell_evidence(self):
        engine = EntryCounter(profile())
        path = ((0., .28, .5), (.15, .32, .5), (.4, .57, .5), (.55, .61, .5),
                (.7, .68, .5), (.85, .73, .5), (1., .77, .5))
        self.assertEqual(len(run_path(engine, path)), 1)

    def test_arbitrary_teleport_cannot_make_direct_a_b_valid(self):
        engine = EntryCounter(profile())
        run_path(engine, ((0., .28, .5), (.15, .28, .5), (.151, .62, .5),
                          (.3, .65, .5), (.45, .73, .5), (.6, .77, .5)))
        self.assertEqual(engine.total_entries, 0)
        self.assertEqual(engine.states[1].phase, Phase.CANCELLED)

    def test_single_frame_in_a_cannot_arm(self):
        engine = EntryCounter(profile())
        run_path(engine, (ENTRY[1],) + ENTRY[2:])
        self.assertEqual(engine.total_entries, 0)

    def test_single_frame_in_b_cannot_confirm(self):
        engine = EntryCounter(profile())
        run_path(engine, ENTRY[:5] + ENTRY[7:])
        self.assertEqual(engine.total_entries, 0)

    def test_two_observations_without_elapsed_time_are_insufficient(self):
        engine = counter_at_b()
        run_path(engine, ((.9, .69, .5), (1., .72, .5), (1.001, .721, .5)))
        self.assertEqual(engine.total_entries, 0)
        run_path(engine, ((1.13, .75, .5),))
        self.assertEqual(engine.total_entries, 1)

    def test_boundary_jitter_below_margin_does_not_count(self):
        engine = counter_at_b()
        run_path(engine, ((.9, .697, .5),) + tuple((1.05 + i * .15, .703 if i % 2 == 0 else .697, .5) for i in range(20)))
        self.assertEqual(engine.total_entries, 0)

    def test_return_to_b_resets_pending_confirmation(self):
        engine = counter_at_b()
        run_path(engine, ((.9, .69, .5), (1.05, .716, .5), (1.10, .699, .5)))
        self.assertEqual(engine.total_entries, 0)
        run_path(engine, ((1.2, .72, .5), (1.35, .75, .5)))
        self.assertEqual(engine.total_entries, 1)

    def test_confirmed_then_jitter_no_duplicate(self):
        engine = EntryCounter(profile())
        run_path(engine)
        run_path(engine, tuple((1.35 + i * .15, .69 if i % 2 else .73, .5) for i in range(30)))
        self.assertEqual(engine.total_entries, 1)

    def test_short_loss_inside_b_can_resume_but_loss_is_not_entry(self):
        engine = counter_at_b()
        engine.update(.8, [])
        self.assertEqual(engine.total_entries, 0)
        run_path(engine, ENTRY[6:])
        self.assertEqual(engine.total_entries, 1)

    def test_missing_b_then_first_reappearance_outside_cannot_count(self):
        engine = counter_at_b()
        engine.update(.9, [])
        run_path(engine, ENTRY[7:])
        self.assertEqual(engine.total_entries, 0)

    def test_missing_id_during_confirmation_cancels(self):
        engine = EntryCounter(profile())
        run_path(engine, ENTRY[:-1])
        engine.update(1.1, [])
        run_path(engine, ENTRY[-1:])
        self.assertEqual(engine.total_entries, 0)

    def test_new_id_does_not_inherit_previous_a(self):
        engine = EntryCounter(profile())
        run_path(engine, ENTRY[:4], identifier=3)
        run_path(engine, ENTRY[4:], identifier=8)
        self.assertEqual(engine.total_entries, 0)

    def test_lost_in_b_expires_without_entry(self):
        engine = counter_at_b()
        engine.update(1.3, [])
        self.assertEqual(engine.states[1].phase, Phase.CANCELLED)
        self.assertEqual(engine.total_entries, 0)

    def test_large_time_gap_cancels_even_if_id_never_absent_from_submitted_frames(self):
        engine = counter_at_b()
        run_path(engine, ((2., .68, .5), (2.15, .73, .5), (2.3, .77, .5)))
        self.assertEqual(engine.total_entries, 0)

    def test_two_ids_have_separate_states_and_two_entries(self):
        engine = EntryCounter(profile())
        for t, x, y in ENTRY:
            engine.update(t, [Observation(1, (x, y - .05)), Observation(2, (x, y + .05))])
        self.assertEqual(engine.total_entries, 2)
        self.assertIsNot(engine.states[1], engine.states[2])

    def test_crossing_opposite_tracks_do_not_fuse_histories(self):
        engine = EntryCounter(profile())
        for t, x, y in ENTRY:
            engine.update(t, [Observation(3, (x, y - .02)), Observation(8, (.95 - x, y + .02))])
        self.assertEqual(engine.total_entries, 1)

    def test_slow_accumulated_reverse_cancels(self):
        engine = counter_at_b()
        run_path(engine, tuple((.9 + i * .15, .62 - .005 * i, .5) for i in range(12)))
        self.assertEqual(engine.states[1].phase, Phase.CANCELLED)

    def test_episode_timeout_not_frame_count(self):
        settings = replace(CountSettings(), episode_timeout_seconds=1.)
        engine = EntryCounter(profile(), settings)
        run_path(engine)
        self.assertEqual(engine.total_entries, 0)
        self.assertEqual(engine.states[1].phase, Phase.CANCELLED)

    def test_old_states_removed_without_resetting_session_total(self):
        engine = EntryCounter(profile())
        run_path(engine)
        engine.update(32., [])
        self.assertEqual(engine.states, {})
        self.assertEqual(engine.total_entries, 1)

    def test_new_session_starts_at_zero(self):
        first = EntryCounter(profile())
        run_path(first)
        second = EntryCounter(profile())
        self.assertEqual(second.total_entries, 0)
        self.assertEqual(second.states, {})

    def test_invalid_timestamps_and_positions_do_not_mutate(self):
        engine = EntryCounter(profile())
        run_path(engine, ENTRY[:2])
        before = asdict(engine.states[1])
        for t in (None, True, -.1, math.nan, math.inf, .15, .1):
            with self.subTest(t=t), self.assertRaises(ValueError): engine.update(t, [])
        for p in ((math.nan, .5), (math.inf, .5), (-.1, .5), (1.1, .5), (True, .5), (.5,), None):
            with self.subTest(p=p), self.assertRaises(ValueError): engine.update(.3, [Observation(1, p)])
        self.assertEqual(asdict(engine.states[1]), before)
        self.assertEqual(engine.total_entries, 0)

    def test_invalid_and_duplicate_ids_rejected_atomically(self):
        for items in ([Observation(0, (.5, .5))], [Observation(True, (.5, .5))],
                      [Observation(1, (.3, .5)), Observation(1, (.3, .5))], [object()]):
            engine = EntryCounter(profile())
            with self.assertRaises(ValueError): engine.update(0, items)
            self.assertEqual(engine.states, {})

    def test_capacity_fails_without_evicting_confirmed_protection(self):
        engine = EntryCounter(profile())
        engine.MAX_STATES = 2
        run_path(engine)
        with self.assertRaises(ValueError):
            engine.update(1.3, [Observation(2, (.28, .5)), Observation(3, (.28, .5))])
        self.assertEqual(engine.total_entries, 1)
        self.assertEqual(engine.states[1].phase, Phase.CONFIRMED)

    def test_five_to_sixty_fps_same_physical_trajectory(self):
        # Tres segundos, A y B con residencia suficiente en todas las frecuencias.
        for fps in (5, 10, 20, 30, 60):
            engine = EntryCounter(profile())
            for frame in range(3 * fps + 1):
                t = frame / fps
                engine.update(t, [Observation(1, (.25 + .19 * t, .5))])
            self.assertEqual(engine.total_entries, 1, fps)


class GeometryAndSettingsTests(unittest.TestCase):
    def test_different_orientations_are_consistent(self):
        for angle in (0, 30, 45, 90, 135, 180, 225, 270, 315):
            transform = rotation(angle)
            p = profile(tuple(map(transform, A)), tuple(map(transform, B)))
            engine = EntryCounter(p)
            self.assertEqual(len(run_path(engine, transform=transform)), 1, angle)

    def test_pixel_aspect_compensated_and_resolution_scaling(self):
        # Mismo recorrido físico en frames 16:9: comprime coordenadas X.
        transform = lambda p: (.5 + (p[0] - .5) / (16 / 9), p[1])
        for width, height in ((1280, 720), (640, 360)):
            p = profile(tuple(map(transform, A)), tuple(map(transform, B)), width, height)
            engine = EntryCounter(p)
            self.assertEqual(len(run_path(engine, transform=transform)), 1)
            self.assertAlmostEqual(engine.geometry.distance, .35)

    def test_trapezoids_and_reversed_vertex_order(self):
        a = ((.2, .38), (.35, .4), (.35, .6), (.2, .62))
        b = ((.55, .42), (.7, .44), (.7, .56), (.55, .58))
        for aa, bb in ((a, b), (a[::-1], b[::-1])):
            self.assertEqual(len(run_path(EntryCounter(profile(aa, bb)))), 1)

    def test_shared_edge_direct_a_b_is_supported(self):
        a = ((.2, .35), (.45, .35), (.45, .65), (.2, .65))
        b = ((.45, .35), (.7, .35), (.7, .65), (.45, .65))
        self.assertEqual(len(run_path(EntryCounter(profile(a, b)))), 1)

    def test_concave_valid_h4_geometry_is_rejected_conservatively_for_counting(self):
        a = ((.2, .35), (.35, .35), (.30, .5), (.35, .65), (.2, .65))
        p = profile(a, B)  # H4 lo admite; H5.1 no inventa una orientación segura.
        with self.assertRaisesRegex(ZoneError, "convexas"): EntryCounter(p)

    def test_skew_projection_overlap_is_ambiguous(self):
        a = ((.1, .1), (.45, .1), (.45, .45), (.1, .45))
        b = ((.4, .46), (.9, .46), (.9, .9), (.4, .9))
        with self.assertRaises(ZoneError): EntryCounter(profile(a, b))

    def test_b_at_frame_edge_has_no_visible_exit(self):
        b = ((.7, .35), (1., .35), (1., .65), (.7, .65))
        with self.assertRaisesRegex(ZoneError, "observar"): EntryCounter(profile(A, b))

    def test_a_with_only_pointed_forward_tip_is_ambiguous(self):
        a = ((.1, .4), (.4, .5), (.1, .6))
        with self.assertRaisesRegex(ZoneError, "borde frontal"): EntryCounter(profile(a, B))

    def test_observed_return_after_confirmed_entry_is_labeled_reverse(self):
        engine = EntryCounter(profile())
        run_path(engine)
        run_path(engine, RETURN[:6], offset=1.35)
        self.assertEqual(engine.states[1].phase, Phase.REVERSE)
        self.assertEqual(engine.total_entries, 1)

    def test_too_thin_zones_reject_spatial_margin(self):
        a = ((.2, .499), (.35, .499), (.35, .501), (.2, .501))
        b = ((.55, .499), (.7, .499), (.7, .501), (.55, .501))
        with self.assertRaisesRegex(ZoneError, "estrechas"): EntryCounter(profile(a, b))

    def test_redundant_collinear_vertex_does_not_make_false_corner(self):
        b = ((.55, .35), (.7, .35), (.7, .5), (.7, .65), (.55, .65))
        self.assertEqual(len(run_path(EntryCounter(profile(A, b)))), 1)

    def test_projection_inverse_and_boundary_margin(self):
        geometry = RouteGeometry(profile(), .04)
        for p in ((0., 0.), (.5, .5), (1., 1.)):
            actual = geometry.unproject(geometry.project(p))
            for value, expected in zip(actual, p): self.assertAlmostEqual(value, expected)
        self.assertFalse(geometry.deep("FUERA", (0., 0.)))
        self.assertAlmostEqual(clearance(geometry.project((.7, .5)), geometry.polygons['B']), 0.)

    def test_invalid_thresholds_fail_without_camera(self):
        for name in asdict(CountSettings()):
            for value in (0, -1, True, math.nan, math.inf, "1"):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    replace(CountSettings(), **{name: value})
        for changes in ({'min_observations': 1}, {'min_observations': 2.5}, {'position_margin': .3},
                        {'max_gap_seconds': 13}, {'state_ttl_seconds': 10}, {'zone_dwell_seconds': 13}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): replace(CountSettings(), **changes)


if __name__ == '__main__':
    unittest.main()
