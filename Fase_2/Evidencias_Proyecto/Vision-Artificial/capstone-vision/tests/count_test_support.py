"""Recorridos sintéticos de H5.1; ninguna observación física ni imagen personal."""

import math

from src.count_engine import EntryCounter, Observation
from src.zones import ZoneProfile

A = ((.2, .35), (.35, .35), (.35, .65), (.2, .65))
B = ((.55, .35), (.7, .35), (.7, .65), (.55, .65))
ENTRY = ((0., .25, .5), (.15, .28, .5), (.3, .37, .5), (.45, .5, .5),
         (.6, .58, .5), (.75, .62, .5), (.9, .68, .5), (1.05, .73, .5), (1.2, .76, .5))
RETURN = ((0., .65, .5), (.15, .62, .5), (.3, .52, .5), (.45, .43, .5),
          (.6, .32, .5), (.75, .28, .5), (.9, .18, .5), (1.05, .15, .5))


def profile(a=A, b=B, width=1000, height=1000):
    return ZoneProfile.create("conteo", 1, width, height, a, b)


def run_path(counter, path=ENTRY, identifier=1, offset=0., transform=lambda p: p):
    events = []
    for t, x, y in path:
        events.extend(counter.update(t + offset, [Observation(identifier, transform((x, y)))]))
    return events


def rotation(angle):
    theta = math.radians(angle)
    def transform(p):
        x, y = p[0] - .5, p[1] - .5
        return (.5 + x * math.cos(theta) - y * math.sin(theta),
                .5 + x * math.sin(theta) + y * math.cos(theta))
    return transform


def counter_at_b():
    engine = EntryCounter(profile())
    run_path(engine, ENTRY[:6])
    return engine
