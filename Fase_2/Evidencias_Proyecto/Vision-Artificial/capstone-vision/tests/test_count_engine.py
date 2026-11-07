"""Contrato definitivo A exterior <-> B puerta. Trayectorias sintéticas sin IA."""

import math
import unittest
from dataclasses import asdict, replace

from src.count_engine import CountSettings, EntryCounter, Observation, Phase, TransitionCounter
from count_test_support import A, B, ENTRY, RETURN, profile, run_path


class TransitionTests(unittest.TestCase):
    def test_direct_excessive_gap_preserves_reset_reason_in_same_frame(self):
        c = EntryCounter(profile())
        run_path(c, ENTRY[:2])
        c.update(3., [Observation(1, (.62,.5))])
        self.assertIn("intervalo_excesivo",c.states[1].reset_reason)
        self.assertIn("estabilidad_insuficiente",c.states[1].reason)
        c.update(3.2, [Observation(1, (.62,.5))])
        self.assertIsNone(c.states[1].reset_reason)
        self.assertEqual(c.total_events,0)

    def test_expired_id_explains_why_it_does_not_inherit_old_origin(self):
        c = EntryCounter(profile())
        run_path(c, ENTRY[:2])
        c.update(40., [Observation(1, (.62,.5))])
        self.assertIn("estado_expirado",c.states[1].reset_reason)
        c.update(40.2, [Observation(1, (.62,.5))])
        self.assertEqual(c.total_events,0)

    def test_entry_is_confirmed_inside_b_without_leaving_it(self):
        c = EntryCounter(profile())
        events = run_path(c, ENTRY[:6])
        self.assertEqual((c.total_entries, c.total_exits), (1, 0))
        self.assertEqual([(e.direction, e.origin, e.destination) for e in events], [("IN", "A", "B")])

    def test_exit_is_confirmed_inside_a_without_final_line(self):
        c = EntryCounter(profile())
        events = run_path(c, RETURN[:6])
        self.assertEqual((c.total_entries, c.total_exits), (0, 1))
        self.assertEqual(events[0].direction, "OUT")

    def test_entry_exit_and_reentry_rearm_from_each_confirmed_zone(self):
        c = EntryCounter(profile())
        events = run_path(c)
        events += run_path(c, RETURN, offset=1.35)
        events += run_path(c, offset=2.55)
        self.assertEqual([e.direction for e in events], ["IN", "OUT", "IN"])
        self.assertEqual([e.number for e in events], [1, 2, 3])
        self.assertEqual([e.episode for e in events], [1, 2, 3])

    def test_isolated_appearance_or_standing_never_counts(self):
        for x in (.28, .62):
            c = EntryCounter(profile())
            run_path(c, tuple((i * .1, x, .5) for i in range(500)))
            self.assertEqual((c.total_entries, c.total_exits), (0, 0))

    def test_approach_then_leave_a_without_b_has_no_event(self):
        c = EntryCounter(profile())
        run_path(c, ENTRY[:4] + ((.6, .3, .5), (.8, .15, .5)))
        self.assertEqual(c.total_events, 0)

    def test_staying_in_destination_does_not_duplicate(self):
        c = EntryCounter(profile())
        run_path(c, ENTRY[:6])
        run_path(c, tuple((1. + i*.1, .62, .5) for i in range(500)))
        self.assertEqual(c.total_entries, 1)

    def test_one_frame_destination_and_jitter_do_not_confirm(self):
        c = EntryCounter(profile())
        run_path(c, ENTRY[:2])
        for i in range(20):
            c.update(.2+i*.05, [Observation(1, (.62 if i % 2 == 0 else .28, .5))])
        self.assertEqual(c.total_events, 0)

    def test_time_and_observation_requirements_both_apply(self):
        c = EntryCounter(profile(), replace(CountSettings(), min_observations=3))
        run_path(c, ((0., .28, .5), (.2, .28, .5), (.3, .28, .5),
                     (.4, .62, .5), (.401, .62, .5), (.402, .62, .5)))
        self.assertEqual(c.total_events, 0)
        c.update(.55, [Observation(1, (.62, .5))])
        self.assertEqual(c.total_entries, 1)

    def test_two_people_enter_consecutively(self):
        c = EntryCounter(profile())
        run_path(c, identifier=1)
        run_path(c, identifier=2, offset=2.)
        self.assertEqual(c.total_entries, 2)

    def test_opposite_crossing_people_keep_separate_histories(self):
        c = EntryCounter(profile())
        for t, x, y in ENTRY:
            c.update(t, [Observation(1, (x, y-.02)), Observation(2, (.95-x, y+.02))])
        self.assertEqual((c.total_entries, c.total_exits), (1, 1))

    def test_short_missing_same_id_can_resume_with_new_destination_dwell(self):
        c = EntryCounter(profile())
        run_path(c, ENTRY[:2])
        c.update(.3, [])
        self.assertEqual(c.total_events, 0)
        c.update(.5, [Observation(1, (.62, .5))])
        self.assertEqual(c.total_events, 0)
        c.update(.65, [Observation(1, (.62, .5))])
        self.assertEqual(c.total_entries, 1)

    def test_missing_resets_pending_dwell(self):
        c = EntryCounter(profile())
        run_path(c, ENTRY[:2])
        c.update(.3, [Observation(1, (.62, .5))])
        c.update(.4, [])
        c.update(.5, [Observation(1, (.62, .5))])
        self.assertEqual(c.total_events, 0)
        c.update(.65, [Observation(1, (.62, .5))])
        self.assertEqual(c.total_entries, 1)

    def test_long_gap_needs_new_origin_and_cannot_inherit_a(self):
        for empty in (False, True):
            c = EntryCounter(profile())
            run_path(c, ENTRY[:2])
            if empty:
                c.update(3., [])
            c.update(3.2, [Observation(1, (.62, .5))])
            c.update(3.4, [Observation(1, (.62, .5))])
            self.assertEqual(c.total_events, 0)

    def test_new_id_never_inherits_previous_origin(self):
        c = EntryCounter(profile())
        run_path(c, ENTRY[:2], identifier=1)
        run_path(c, ENTRY[4:6], identifier=2)
        self.assertEqual(c.total_events, 0)

    def test_outside_zones_is_not_outside_frame_or_cancellation(self):
        c = EntryCounter(profile())
        run_path(c, ENTRY[:4])
        self.assertEqual(c.states[1].stable_zone, "A")
        self.assertIn("fuera_de_zonas", c.states[1].reason)
        run_path(c, ENTRY[4:6])
        self.assertEqual(c.total_entries, 1)

    def test_invalid_tracker_point_resets_only_its_id_and_does_not_clip(self):
        c = EntryCounter(profile())
        for t in (0., .2):
            c.update(t, [Observation(1, (.28, .5)), Observation(2, (.28, .5))])
        c.update(.4, [Observation(1, (1.1, .5)), Observation(2, (.62, .5))])
        self.assertIn("fuera_de_imagen", c.states[1].reason)
        c.update(.6, [Observation(1, (.62, .5)), Observation(2, (.62, .5))])
        self.assertEqual(c.total_entries, 1)
        c.update(.8, [Observation(1, (.62, .5))])
        self.assertEqual(c.total_entries, 1)

    def test_nonfinite_or_malformed_point_rejected_per_id(self):
        for point in ((math.nan,.5), (math.inf,.5), None, (.5,), (True,.5)):
            c = EntryCounter(profile())
            run_path(c, ENTRY[:2])
            c.update(.3, [Observation(1, point)])
            self.assertIsNone(c.states[1].stable_zone)
            self.assertIn("punto_invalido", c.states[1].reason)

    def test_invalid_timestamps_and_ids_leave_state_unchanged(self):
        c = EntryCounter(profile())
        run_path(c, ENTRY[:2])
        before = asdict(c.states[1])
        for t in (math.inf, math.nan, True, -.1, .15):
            with self.assertRaises(ValueError): c.update(t, [])
        for items in ([Observation(0, (.3,.5))], [Observation(1,(.3,.5))]*2, [object()]):
            with self.assertRaises(ValueError): c.update(.3, items)
        self.assertEqual(asdict(c.states[1]), before)

    def test_no_episode_timeout_for_slow_observed_route_or_wait(self):
        c = EntryCounter(profile())
        run_path(c, tuple((i*.5,.28,.5) for i in range(200)))
        run_path(c, tuple((100.+i*.5,.62,.5) for i in range(3)))
        self.assertEqual(c.total_entries, 1)

    def test_fast_route_can_use_configured_dwell_without_exit_b(self):
        c = EntryCounter(profile(), replace(CountSettings(), zone_dwell_seconds=0))
        run_path(c, ((0.,.28,.5),(.01,.28,.5),(.02,.62,.5),(.03,.62,.5)))
        self.assertEqual(c.total_entries, 1)

    def test_routes_at_multiple_frame_rates_and_speeds(self):
        for fps in (5, 10, 30, 60):
            for duration in (2., 8., 40.):
                c = EntryCounter(profile())
                for frame in range(round(duration*fps)+1):
                    t = frame/fps
                    c.update(t, [Observation(1,(.25+.4*t/duration,.5))])
                self.assertEqual(c.total_entries, 1, (fps,duration))

    def test_no_convexity_axis_or_visible_exit_requirement(self):
        a = ((.2,.35),(.35,.35),(.30,.5),(.35,.65),(.2,.65))
        for p in (profile(a=a), profile(b=((.55,.35),(1.,.35),(1.,.65),(.55,.65)))):
            c = EntryCounter(p)
            run_path(c, ENTRY[:6])
            self.assertEqual(c.total_entries, 1)

    def test_capacity_and_ttl_preserve_totals(self):
        c = EntryCounter(profile())
        run_path(c)
        c.MAX_STATES=1
        with self.assertRaises(ValueError):
            c.update(1.3, [Observation(2,(.28,.5))])
        self.assertEqual(c.total_entries, 1)
        c.update(40., [])
        self.assertEqual(c.states, {})
        self.assertEqual(c.total_entries, 1)

    def test_new_session_has_no_history(self):
        self.assertEqual((EntryCounter(profile()).total_events, EntryCounter(profile()).states), (0, {}))
        self.assertIs(EntryCounter, TransitionCounter)

    def test_duplicate_tracker_ids_are_not_person_deduplication(self):
        c = EntryCounter(profile())
        for t,x,y in ENTRY:
            c.update(t,[Observation(1,(x,y)),Observation(2,(x,y))])
        self.assertEqual(c.total_entries,2)  # Limite explicito del tracker, no personas unicas.


class SettingsTests(unittest.TestCase):
    def test_only_four_justified_thresholds_remain(self):
        self.assertEqual(set(asdict(CountSettings())),
                         {"zone_dwell_seconds","min_observations","max_gap_seconds","state_ttl_seconds"})

    def test_invalid_thresholds(self):
        for key in asdict(CountSettings()):
            for value in (True, math.nan, math.inf, "1"):
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                    replace(CountSettings(), **{key:value})
        for change in (dict(zone_dwell_seconds=-1),dict(min_observations=1),
                       dict(min_observations=2.5),dict(max_gap_seconds=0),
                       dict(max_gap_seconds=31),dict(state_ttl_seconds=1)):
            with self.assertRaises(ValueError):replace(CountSettings(),**change)


if __name__ == "__main__":
    unittest.main()
