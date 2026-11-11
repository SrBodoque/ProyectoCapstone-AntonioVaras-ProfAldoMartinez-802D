import math
import unittest
from dataclasses import asdict, replace
from types import SimpleNamespace

from src.count_engine import CountSettings, EntryCounter, Observation, Phase
from src.count_geometry import RouteGeometry, clearance
from src.counting_config import load_counting_config
from src.zones import ZoneError, _intersects, bottom_center
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


class NarrowRouteSimulationTests(unittest.TestCase):
    """SIM-03/08: caracterizacion sintetica, sin acreditar entradas fisicas.

    Un total cero documenta un rechazo actual, no su idoneidad para un bano real.
    SIM-01/02/06 reutilizan tambien los casos existentes de EntryTests.
    """
    PREFIX = ((.22, .5), (.23, .5), (.24, .5), (.27, .5), (.37, .5),
              (.47, .5), (.52, .5), (.53, .5), (.54, .5), (.55, .5))
    ENTRY = PREFIX + ((.58, .5), (.60, .5), (.62, .5))
    JITTER = PREFIX[:3] + ((.255, .5), (.262, .5), (.258, .5)) + ENTRY[3:]
    RETURN = ((.53, .5), (.43, .5), (.33, .5), (.24, .5), (.23, .5),
              (.22, .5), (.18, .5), (.17, .5), (.16, .5))

    @classmethod
    def setUpClass(cls):
        cls.settings = load_counting_config().thresholds

    @staticmethod
    def strips(zone_width=.06, b_left=.50):
        def rectangle(left):
            return ((left, .15), (left + zone_width, .15),
                    (left + zone_width, .85), (left, .85))
        return profile(rectangle(.20), rectangle(b_left), width=1280, height=720)

    @staticmethod
    def frames(points, offset=0., identifier=1, fps=10):
        return [(round(offset + i / fps, 6), [(identifier, point)])
                for i, point in enumerate(points)]

    @staticmethod
    def straight(p, speed, fps):
        start, end = p.a[0][0] - .03, max(v[0] for v in p.b) + .08
        count = math.ceil(((end - start) / speed + .3) * fps)
        return [(round(i / fps, 6), [(1, (min(end, start + speed * i / fps), .5))])
                for i in range(count + 1)]

    def simulate(self, frames, p=None):
        """Observa la FSM real; no reconstruye sus decisiones ni guarda archivos."""
        engine = EntryCounter(self.strips() if p is None else p, self.settings)
        events, trace = [], []
        for timestamp, items in frames:
            events.extend(engine.update(timestamp, [Observation(i, point) for i, point in items]))
            visible = dict(items)
            for identifier, state in engine.states.items():
                point = visible.get(identifier)
                trace.append(dict(t=timestamp, id=identifier, point=point,
                                  zone=engine.geometry.classify(point) if point is not None else None,
                                  phase=state.phase, reason=state.reason, episode=state.episode,
                                  evidence=state.evidence, crossing=state.crossing,
                                  elapsed=timestamp - state.evidence_since if state.evidence else 0.))
        return engine, events, trace

    @staticmethod
    def first_cancel(trace):
        return next(row for row in trace if row['phase'] == Phase.CANCELLED)

    def box_frames(self, points, *, fps=10):
        converted = []
        for i, (x, y) in enumerate(points):
            width, height = (.06, .075, .065)[i % 3], (.20, .21, .19)[i % 3]
            box = SimpleNamespace(x1=(x - width / 2) * 1280, x2=(x + width / 2) * 1280,
                                  y1=(y - height) * 720, y2=y * 720)
            bx, by = bottom_center(box)
            converted.append((bx / 1280, by / 720))
        return self.frames(converted, fps=fps)

    @staticmethod
    def direction_step(engine, zone, previous, current):
        """Diagnostico geometrico; las decisiones siguen en la FSM real."""
        geometry = engine.geometry
        a, b = geometry.project(previous), geometry.project(current)
        angle = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        edges = [(geometry.unproject(p), geometry.unproject(q), normal)
                 for p, q, _, _, normal in geometry._edges(zone)
                 if _intersects(a, b, p, q)]
        return dict(angle=angle, edges=edges,
                    crossing=geometry.exit_through(zone, a, b))

    def test_sim03_turns_at_b_accept_45_degrees_but_reject_46(self):
        for angle in (0, 15, 30, 44, 45, 46, 60, 75):
            with self.subTest(metric_angle=angle):
                tail = tuple((x, .5 + (x - .55) * (1280 / 720) * math.tan(math.radians(angle)))
                             for x in (.58, .60, .62))
                engine, events, trace = self.simulate(self.frames(self.PREFIX + tail))
                self.assertEqual((engine.total_entries, len(events)), (1, 1) if angle <= 45 else (0, 0))
                if angle > 45:
                    rejected = self.first_cancel(trace)
                    self.assertEqual(rejected['t'], 1.)
                    self.assertEqual(rejected['reason'], 'salida de B lateral, inversa o junto a vértice ambiguo')

    def test_sim04_box_reentry_near_a_edge_preserves_entry_despite_small_jitter(self):
        engine, events, trace = self.simulate(self.box_frames(self.JITTER))
        self.assertEqual(engine.total_entries, 1)
        self.assertEqual([(e.track_id, e.episode, e.timestamp) for e in events], [(1, 1, 1.5)])
        self.assertFalse(any(row['phase'] == Phase.CANCELLED for row in trace))
        self.assertEqual(trace[5]['phase'], Phase.APPROACHING)
        self.assertLess(.004 / .30, self.settings.position_margin)
        self.assertEqual([row['zone'] for row in trace[3:7]], ['A', 'FUERA', 'A', 'FUERA'])

    def test_sim04_a_reentry_respects_existing_interior_margin(self):
        for x, expected in ((.248001, 1), (.248, 0), (.245, 0)):
            with self.subTest(return_x=x):
                points = self.JITTER[:5] + ((x, .5),) + self.ENTRY[3:]
                engine, events, trace = self.simulate(self.box_frames(points))
                self.assertEqual((engine.total_entries, len(events)), (expected, expected))
                if not expected:
                    rejected = self.first_cancel(trace)
                    self.assertEqual(rejected['t'], .5)
                    self.assertEqual(rejected['reason'], 'regresó a A antes de completar')

    def test_sim04_repeated_shallow_a_oscillations_count_once(self):
        oscillations = ((.255, .5), (.262, .5), (.258, .5), (.263, .5),
                        (.257, .5), (.264, .5), (.258, .5))
        points = self.PREFIX[:3] + oscillations + self.ENTRY[3:] + ((.62, .5),) * 5
        engine, events, trace = self.simulate(self.box_frames(points))
        self.assertEqual((engine.total_entries, len(events)), (1, 1))
        self.assertEqual((events[0].track_id, events[0].episode), (1, 1))
        self.assertFalse(any(row['phase'] == Phase.CANCELLED for row in trace))

    def test_sim04_shallow_a_return_keeps_longitudinal_reverse_guard(self):
        points = self.JITTER[:5] + ((.29, .5), (.259, .5)) + self.ENTRY[3:]
        engine, events, trace = self.simulate(self.box_frames(points))
        self.assertEqual((engine.total_entries, events), (0, []))
        self.assertEqual(self.first_cancel(trace)['reason'], 'retroceso longitudinal')

    def test_sim04_unfinished_shallow_a_return_expires_or_is_lost(self):
        for missing in (False, True):
            with self.subTest(missing=missing):
                if missing:
                    frames = self.box_frames(self.JITTER[:6]) + [(.6, []), (1.1, [])]
                    reason = 'recorrido perdido o expirado'
                else:
                    frames = self.box_frames(self.JITTER[:6] + ((.258, .5),) * 125)
                    reason = 'recorrido expirado'
                engine, events, trace = self.simulate(frames)
                self.assertEqual((engine.total_entries, events), (0, []))
                self.assertEqual(engine.states[1].phase, Phase.CANCELLED)
                self.assertEqual(self.first_cancel(trace)['reason'], reason)

    def test_sim04_new_a_exit_after_jitter_still_requires_forward_direction(self):
        points = self.JITTER[:6] + ((.262, .51),) + self.ENTRY[4:]
        engine, events, trace = self.simulate(self.box_frames(points))
        self.assertEqual((engine.total_entries, events), (0, []))
        rejected = self.first_cancel(trace)
        self.assertEqual(rejected['t'], .6)
        self.assertEqual(rejected['reason'], 'salida de A lateral, inversa o no observada')

    def test_sim04_loss_or_new_id_during_shallow_a_return_does_not_count(self):
        for new_id in (False, True):
            with self.subTest(new_id=new_id):
                frames = self.box_frames(self.JITTER)
                if new_id:
                    frames = [(t, [(2 if t >= .6 else i, point) for i, point in items])
                              for t, items in frames]
                else:
                    frames.insert(6, (.55, []))
                engine, events, trace = self.simulate(frames)
                self.assertEqual((engine.total_entries, events), (0, []))
                if new_id:
                    self.assertEqual(engine.states[2].episode, 0)
                else:
                    rejected = self.first_cancel(trace)
                    self.assertEqual(rejected['t'], .6)
                    self.assertEqual(rejected['reason'], 'cambio de zona durante una pérdida')

    def test_sim04_box_bottom_shift_can_reject_a_forward_edge_crossing(self):
        points = self.PREFIX[:3] + ((.258, .5), (.262, .51), (.27, .5)) + self.ENTRY[4:]
        engine, events, trace = self.simulate(self.box_frames(points))
        rejected = self.first_cancel(trace)
        self.assertEqual((engine.total_entries, events, rejected['t']), (0, [], .4))
        self.assertEqual(rejected['reason'], 'salida de A lateral, inversa o no observada')
        geometry = engine.geometry
        displacement = math.dist(geometry.project((.258, .5)), geometry.project((.262, .51)))
        self.assertLess(displacement, self.settings.position_margin)

    def test_sim05_width_gap_speed_and_sampling_matrix(self):
        # Columnas = 10/20/30 observaciones por segundo. Cambian solo seis casos
        # antes omitidos por el margen de permanencia en las geometrías 1 y 3.
        profiles = (profile(), self.strips(), self.strips(b_left=.32), self.strips(.04, .60))
        expected = (((1, 1, 1), (1, 1, 1), (1, 1, 1), (1, 1, 1), (0, 1, 1)),
                    ((1, 1, 1), (1, 1, 1), (0, 0, 1), (0, 0, 0), (0, 0, 0)),
                    ((1, 1, 1), (1, 1, 1), (0, 0, 1), (0, 0, 0), (0, 0, 0)),
                    ((1, 1, 1), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)))
        for g, p in enumerate(profiles):
            for v, speed in enumerate((.10, .20, .30, .40, .60)):
                for f, fps in enumerate((10, 20, 30)):
                    with self.subTest(geometry=g, speed=speed, fps=fps):
                        engine, events, trace = self.simulate(self.straight(p, speed, fps), p)
                        self.assertEqual((engine.total_entries, len(events)), (expected[g][v][f],) * 2)
                        if expected[g][v][f]:
                            for phase in (Phase.AT_A, Phase.AT_B):
                                stable = next(row for row in trace if row['phase'] == phase)
                                self.assertGreaterEqual(stable['elapsed'] + 1e-9, self.settings.zone_dwell_seconds)
        with self.assertRaisesRegex(ZoneError, 'estrechas'):
            EntryCounter(self.strips(.03, .65), self.settings)

    def test_sim05_local_dwell_counts_without_changing_the_deep_margin(self):
        engine, _, trace = self.simulate(self.straight(self.strips(), .20, 20))
        in_a = [row['t'] for row in trace if row['zone'] == 'A']
        deep = [row['t'] for row in trace if row['zone'] == 'A'
                and engine.geometry.deep('A', engine.geometry.project(row['point']))]
        self.assertGreater(max(in_a) - min(in_a), self.settings.zone_dwell_seconds)
        self.assertAlmostEqual(max(deep) - min(deep), .10)  # Margen de cruces/histeresis intacto.
        stable = next(row for row in trace if row['phase'] == Phase.AT_A)
        self.assertAlmostEqual(stable['elapsed'], .15)
        self.assertGreaterEqual(stable['elapsed'], self.settings.zone_dwell_seconds)
        self.assertEqual(engine.states[1].phase, Phase.CONFIRMED)
        self.assertEqual(engine.total_entries, 1)

    def test_sim05_narrow_route_counts_with_full_dwell_at_all_sampling_rates(self):
        for fps in (10, 20, 30):
            with self.subTest(fps=fps):
                engine, events, trace = self.simulate(self.straight(self.strips(), .20, fps))
                self.assertEqual((engine.total_entries, len(events)), (1, 1))
                for phase in (Phase.AT_A, Phase.AT_B):
                    stable = next(row for row in trace if row['phase'] == phase)
                    self.assertGreaterEqual(stable['elapsed'] + 1e-9, self.settings.zone_dwell_seconds)

    def test_sim05_far_strips_allow_slow_entry_but_reject_too_short_residence(self):
        p = self.strips(.04, .60)
        for fps in (10, 20, 30):
            for speed, expected in ((.10, 1), (.40, 0)):
                with self.subTest(fps=fps, speed=speed):
                    engine, events, _ = self.simulate(self.straight(p, speed, fps), p)
                    self.assertEqual((engine.total_entries, len(events)), (expected, expected))

    def test_sim05_dwell_margin_uses_each_polygon_and_preserves_crossing_margin(self):
        for b_left in (.50, .65):
            with self.subTest(b_left=b_left):
                geometry = RouteGeometry(self.strips(b_left=b_left), self.settings.position_margin)
                for zone in ('A', 'B'):
                    pixels = geometry.dwell_margins[zone] * geometry.distance * geometry.profile.height
                    self.assertAlmostEqual(pixels, 12.8)
                point = geometry.project((.248001, .5))
                self.assertFalse(geometry.deep('A', point))  # Banda de histeresis del Paso 3C intacta.
                self.assertTrue(geometry.dwell_interior('A', point))
                self.assertFalse(geometry.dwell_interior('FUERA', point))
                self.assertFalse(geometry.dwell_interior('A', geometry.project((.18, .5))))
                self.assertEqual(geometry.margin, self.settings.position_margin)
        for p in (profile(), self.strips(b_left=.32)):
            geometry = RouteGeometry(p, self.settings.position_margin)
            self.assertEqual(geometry.dwell_margins, {'A': geometry.margin, 'B': geometry.margin})

    def test_sim05_superficial_contacts_do_not_arm_a_or_confirm_b(self):
        for fps in (10, 20, 30):
            for grazed_zone in ('A', 'B'):
                with self.subTest(fps=fps, grazed_zone=grazed_zone):
                    frames = []
                    for timestamp, items in self.straight(self.strips(), .10, fps):
                        x = items[0][1][0]
                        y = .1505 if grazed_zone == 'A' else max(.1505, .5 - .3495 * max(0., x - .30) / .20)
                        frames.append((timestamp, [(1, (x, y))]))
                    engine, events, trace = self.simulate(frames)
                    self.assertEqual((engine.total_entries, events), (0, []))
                    blocked = Phase.AT_A if grazed_zone == 'A' else Phase.AT_B
                    self.assertFalse(any(row['phase'] == blocked for row in trace))
                    if grazed_zone == 'B':
                        self.assertTrue(any(row['phase'] == Phase.AT_A for row in trace))

    def test_sim05_one_observation_or_less_than_dwell_is_still_insufficient(self):
        frames = self.frames(self.ENTRY)
        paths = {
            'one_a': frames[:1] + frames[3:],
            'one_b': frames[:6] + frames[8:9] + frames[10:],
            'short_a': self.frames(self.PREFIX[:2], fps=20) + frames[3:],
            'short_b': frames[:6] + self.frames(self.PREFIX[6:8], offset=.6, fps=20) + frames[10:],
        }
        for name, path in paths.items():
            with self.subTest(path=name):
                engine, events, trace = self.simulate(path)
                self.assertEqual((engine.total_entries, events), (0, []))
                blocked = Phase.AT_A if name.endswith('a') else Phase.AT_B
                self.assertFalse(any(row['phase'] == blocked for row in trace))

    def test_sim05_box_jitter_interior_counts_but_edge_jitter_does_not(self):
        for fps in (10, 20, 30):
            for grazing in (False, True):
                with self.subTest(fps=fps, grazing=grazing):
                    points = []
                    for i, (_, items) in enumerate(self.straight(self.strips(), .10, fps)):
                        sign = 1 if i % 2 else -1
                        x = items[0][1][0] + sign * .001
                        y = .1505 + sign * .0001 if grazing else .5 + sign * .001
                        points.append((x, y))
                    engine, events, _ = self.simulate(self.box_frames(points, fps=fps))
                    self.assertEqual((engine.total_entries, len(events)), (0, 0) if grazing else (1, 1))

    def test_sim05_two_independent_narrow_routes_count_without_duplicates(self):
        for fps in (10, 20, 30):
            with self.subTest(fps=fps):
                base = [items[0][1] for _, items in self.straight(self.strips(), .20, fps)]
                lag = round(.2 * fps)
                frames = []
                for frame in range(len(base) + lag + 5):
                    items = []
                    for identifier, delay, y in ((7, 0, .45), (19, lag, .55)):
                        if frame >= delay:
                            x = base[min(frame - delay, len(base) - 1)][0]
                            items.append((identifier, (x, y)))
                    frames.append((round(frame / fps, 6), items))
                engine, events, _ = self.simulate(frames)
                self.assertEqual((engine.total_entries, len(events)), (2, 2))
                self.assertEqual([e.track_id for e in events], [7, 19])
                self.assertIsNot(engine.states[7], engine.states[19])

    def test_sim05_a_and_b_use_their_own_polygon_size(self):
        a = ((.20, .15), (.35, .15), (.35, .85), (.20, .85))
        b = ((.55, .15), (.59, .15), (.59, .85), (.55, .85))
        p = profile(a, b, width=1280, height=720)
        for fps in (10, 20, 30):
            with self.subTest(fps=fps):
                engine, events, _ = self.simulate(self.straight(p, .10, fps), p)
                self.assertEqual((engine.total_entries, len(events)), (1, 1))
                self.assertGreater(engine.geometry.dwell_margins['A'], engine.geometry.dwell_margins['B'])

    def test_sim07_cancelled_episode_needs_full_return_before_new_entry(self):
        # La oscilacion superficial ya se tolera; este caso debe cancelar un retorno real.
        real_return = self.JITTER[:5] + ((.245, .5),) + self.ENTRY[3:]
        cancelled = self.frames(real_return)
        offset = round(cancelled[-1][0] + .1, 6)
        for complete in (False, True):
            with self.subTest(complete_return=complete):
                returning = self.RETURN if complete else self.RETURN[:6]
                frames = cancelled + self.frames(returning, offset)
                frames += self.frames(self.ENTRY, round(frames[-1][0] + .1, 6))
                engine, events, trace = self.simulate(frames)
                self.assertEqual(self.first_cancel(trace)['reason'], 'regresó a A antes de completar')
                self.assertEqual(engine.total_entries, int(complete))
                if complete:
                    self.assertEqual([(e.track_id, e.episode) for e in events], [(1, 2)])
                    self.assertTrue(any(row['t'] > offset and row['phase'] == Phase.IDLE for row in trace))
                else:
                    self.assertEqual(events, [])
                    self.assertEqual(engine.states[1].phase, Phase.CANCELLED)

    def test_sim08_staggered_people_count_once_per_independent_id(self):
        frames = []
        for frame in range(len(self.ENTRY) + 8):
            items = []
            for identifier, lag, y in ((101, 0, .45), (202, 2, .55)):
                index = frame - lag
                if index >= 0:
                    items.append((identifier, (self.ENTRY[min(index, len(self.ENTRY) - 1)][0], y)))
            frames.append((round(frame / 10, 6), items))
        engine, events, _ = self.simulate(frames)
        self.assertEqual(engine.total_entries, 2)
        self.assertEqual([(e.track_id, e.number, e.timestamp) for e in events], [(101, 1, 1.2), (202, 2, 1.4)])
        self.assertIsNot(engine.states[101], engine.states[202])


    def test_dir02_pixel_crossings_expose_local_angle_sensitivity_in_a_and_b(self):
        for zone in ('A', 'B'):
            for dx in (1, 2, 4, 8):
                for dy in (0, 1, 2, 4, 8):
                    with self.subTest(zone=zone, dx_px=dx, dy_px=dy):
                        edge = .26 if zone == 'A' else .56
                        previous = (edge - dx / (2 * 1280), .5)
                        current = (edge + dx / (2 * 1280), .5 + dy / 720)
                        if zone == 'A':
                            points = self.PREFIX[:3] + (previous, current, (.27, .5)) + self.ENTRY[4:]
                            index, before = 4, Phase.AT_A
                        else:
                            points = self.PREFIX + (previous, current) + self.ENTRY[10:]
                            index, before = 11, Phase.AT_B
                        engine, events, trace = self.simulate(self.frames(points))
                        detail = self.direction_step(engine, zone, previous, current)
                        self.assertEqual(trace[index - 1]['phase'], before)
                        self.assertAlmostEqual(detail['angle'], math.degrees(math.atan2(dy, dx)))
                        self.assertEqual(len(detail['edges']), 1)
                        for actual, expected_normal in zip(detail['edges'][0][2], (1., 0.)):
                            self.assertAlmostEqual(actual, expected_normal)
                        expected = int(dy <= dx)  # Incluye el limite existente de 45 grados.
                        self.assertEqual((engine.total_entries, len(events)), (expected, expected))
                        self.assertEqual(detail['crossing'] is not None, bool(expected))
                        if not expected:
                            rejected = self.first_cancel(trace)
                            self.assertEqual(rejected['t'], trace[index]['t'])
                            self.assertEqual(rejected['phase'], Phase.CANCELLED)
                            self.assertTrue(rejected['reason'].startswith('salida de ' + zone))

    def test_dir03_repeated_interior_jitter_does_not_imply_a_bad_crossing(self):
        for fps in (10, 20, 30):
            with self.subTest(fps=fps):
                frames = []
                for i, (t, items) in enumerate(self.straight(self.strips(), .10, fps)):
                    x = items[0][1][0]
                    jitter = 4 / 720 * (-1 if i % 2 else 1)
                    y = .5 + jitter if .22 <= x <= .24 or .52 <= x <= .54 else .5
                    frames.append((t, [(1, (x, y))]))
                engine, events, trace = self.simulate(frames)
                self.assertEqual((engine.total_entries, len(events)), (1, 1))
                self.assertFalse(any(row['phase'] == Phase.CANCELLED for row in trace))
                angles = [abs(self.direction_step(engine, 'A', a['point'], b['point'])['angle'])
                          for a, b in zip(trace, trace[1:]) if a['zone'] == b['zone'] == 'A']
                if fps >= 20:
                    self.assertGreater(max(angles), 45)

    def test_dir04_gradual_turn_can_fail_at_crossing_or_later_confirmation(self):
        schedules = {'soft': (10, 20, 30, 30, 30, 30),
                     'hard': (10, 30, 50, 60, 60, 60),
                     'late': (0, 0, 30, 60, 75, 75)}
        for name, angles in schedules.items():
            with self.subTest(turn=name):
                points = list(self.PREFIX[:9])
                x, y = points[-1]
                for angle in angles:
                    x, y = x + .01, y + .01 * (1280 / 720) * math.tan(math.radians(angle))
                    points.append((x, y))
                if name == 'late':
                    points += [points[-1]] * 113  # Permite observar la expiracion real.
                engine, events, trace = self.simulate(self.frames(points))
                at_crossing = trace[11]  # t=1.1: sale de B despues de tocar su borde.
                detail = self.direction_step(engine, 'B', trace[10]['point'], at_crossing['point'])
                self.assertEqual(trace[10]['phase'], Phase.AT_B)
                self.assertEqual(len(detail['edges']), 1)
                for actual, expected_normal in zip(detail['edges'][0][2], (1., 0.)):
                    self.assertAlmostEqual(actual, expected_normal)
                self.assertAlmostEqual(detail['angle'], angles[2])
                if name == 'hard':
                    rejected = self.first_cancel(trace)
                    self.assertEqual((engine.total_entries, events, rejected['t']), (0, [], 1.1))
                    self.assertTrue(rejected['reason'].startswith('salida de B'))
                    self.assertIsNone(detail['crossing'])
                else:
                    self.assertEqual(at_crossing['phase'], Phase.CONFIRMING)
                    self.assertIsNotNone(detail['crossing'])
                    if name == 'soft':
                        self.assertEqual((engine.total_entries, len(events)), (1, 1))
                        self.assertFalse(any(row['phase'] == Phase.CANCELLED for row in trace))
                    else:
                        later = trace[12]
                        crossing = at_crossing['crossing']
                        point = engine.geometry.project(later['point'])
                        dx, dy = point[0] - crossing.anchor[0], point[1] - crossing.anchor[1]
                        self.assertGreater(math.degrees(math.atan2(dy, dx)), 45)
                        self.assertGreater(point[0] - crossing.point[0], engine.geometry.margin)
                        self.assertFalse(engine.geometry.beyond(crossing, point))
                        self.assertEqual((later['phase'], later['evidence']), (Phase.CONFIRMING, None))
                        rejected = self.first_cancel(trace)
                        self.assertEqual((engine.total_entries, events, rejected['t']), (0, [], 12.3))
                        self.assertEqual(rejected['reason'], 'recorrido expirado')

    def test_dir05_real_side_exit_fails_normal_even_with_a_forward_local_angle(self):
        frames = [(t, [(1, (x, y))]) for t, x, y in ENTRY[:6]]
        frames += [(.9, [(1, (.62, .60))]), (1.05, [(1, (.62, .64))]),
                   (1.2, [(1, (.66, .66))]), (1.35, [(1, (.75, .68))])]
        engine, events, trace = self.simulate(frames, profile())
        detail = self.direction_step(engine, 'B', (.62, .64), (.66, .66))
        self.assertLess(detail['angle'], 45)
        self.assertEqual(len(detail['edges']), 1)
        for actual, expected_normal in zip(detail['edges'][0][2], (0., 1.)):
            self.assertAlmostEqual(actual, expected_normal)
        self.assertIsNone(detail['crossing'])
        self.assertEqual(trace[7]['phase'], Phase.AT_B)
        rejected = self.first_cancel(trace)
        self.assertEqual((engine.total_entries, events, rejected['t']), (0, [], 1.2))
        self.assertTrue(rejected['reason'].startswith('salida de B'))

    def test_dir07_bbox_size_only_changes_direction_if_bottom_center_moves(self):
        points = self.PREFIX[:3] + ((.258, .5), (.262, .5), (.27, .5)) + self.ENTRY[4:]
        for mode in ('width', 'height_fixed_bottom', 'height_fixed_top'):
            with self.subTest(mode=mode):
                converted = []
                for i, (x, y) in enumerate(points):
                    width = .075 if mode == 'width' and i == 4 else .06
                    height = .21 if mode != 'width' and i == 4 else .20
                    top = y - .20 if mode == 'height_fixed_top' else y - height
                    box = SimpleNamespace(x1=(x - width / 2) * 1280,
                                          x2=(x + width / 2) * 1280,
                                          y1=top * 720, y2=(top + height) * 720)
                    bx, by = bottom_center(box)
                    converted.append((bx / 1280, by / 720))
                engine, events, trace = self.simulate(self.frames(converted))
                detail = self.direction_step(engine, 'A', converted[3], converted[4])
                if mode == 'height_fixed_top':
                    self.assertAlmostEqual(detail['angle'], 54.5829447235)
                    self.assertEqual((engine.total_entries, events), (0, []))
                    self.assertEqual(self.first_cancel(trace)['t'], .4)
                else:
                    self.assertAlmostEqual(detail['angle'], 0)
                    self.assertEqual((engine.total_entries, len(events)), (1, 1))

    def test_dir08_fixed_pixel_jitter_depends_on_synthetic_sampling_rate(self):
        for fps, expected in ((10, 1), (20, 0), (30, 0)):
            with self.subTest(observations_per_second=fps):
                clean = self.straight(self.strips(), .10, fps)
                engine, events, _ = self.simulate(clean)
                self.assertEqual((engine.total_entries, len(events)), (1, 1))
                jitter = [(t, [(1, (items[0][1][0], .5 + (4 if i % 2 else -4) / 720))])
                          for i, (t, items) in enumerate(clean)]
                engine, events, trace = self.simulate(jitter)
                self.assertEqual((engine.total_entries, len(events)), (expected, expected))
                if not expected:
                    rejected = self.first_cancel(trace)
                    index = trace.index(rejected)
                    detail = self.direction_step(engine, 'A', trace[index - 1]['point'], rejected['point'])
                    self.assertEqual(trace[index - 1]['phase'], Phase.AT_A)
                    self.assertGreater(abs(detail['angle']), 45)
                    self.assertAlmostEqual(abs(detail['angle']), math.degrees(math.atan2(8, 128 / fps)), places=4)
                    for actual, expected_normal in zip(detail['edges'][0][2], (1., 0.)):
                        self.assertAlmostEqual(actual, expected_normal)
                    self.assertTrue(rejected['reason'].startswith('salida de A'))

    def test_dir09_clean_and_jittering_ids_keep_independent_results(self):
        for fps in (10, 20, 30):
            with self.subTest(observations_per_second=fps):
                frames = [(t, [(101, (items[0][1][0], .45)),
                               (202, (items[0][1][0], .55 + (4 if i % 2 else -4) / 720))])
                          for i, (t, items) in enumerate(self.straight(self.strips(), .10, fps))]
                engine, events, trace = self.simulate(frames)
                self.assertEqual([e.track_id for e in events], [101, 202] if fps == 10 else [101])
                self.assertEqual(engine.total_entries, 2 if fps == 10 else 1)
                self.assertEqual(engine.states[101].phase, Phase.CONFIRMED)
                self.assertEqual(engine.states[202].phase, Phase.CONFIRMED if fps == 10 else Phase.CANCELLED)
                self.assertIsNot(engine.states[101], engine.states[202])
                self.assertFalse(any(row['id'] == 101 and row['phase'] == Phase.CANCELLED for row in trace))


if __name__ == '__main__':
    unittest.main()
