"""Ordered MP4 presentation, following the technical viewer's per-frame deadline."""
from collections import deque
import sys
import threading
import time


class DisplayQueue:
    def __init__(self, capacity=4, clock=time.monotonic, prefill=1, nominal=False):
        self.capacity, self.clock = capacity, clock
        self.nominal = nominal
        self.last_due = None
        self.items = deque()
        self.condition = threading.Condition()
        self.cancelled = False
        self.last_timestamp = None
        self.last_shown = None
        self.prefill = prefill
        self.finished = False
        self.in_flight = False

    def put(self, state):
        with self.condition:
            while len(self.items) >= self.capacity and not self.cancelled:
                self.condition.wait(.05)
            if self.cancelled:
                return
            self.items.append(state)
            self.condition.notify_all()

    def take(self):
        with self.condition:
            if self.cancelled or not self.items:
                return None
            if self.last_shown is None and len(self.items)<self.prefill and not self.finished:
                return None
            next_state = self.items[0]
            interval = (next_state.timestamp-self.last_timestamp) if self.last_timestamp is not None else 0.
            if self.nominal and next_state.source_fps > 0:
                interval = 1 / next_state.source_fps
            due = ((self.last_due if self.nominal else self.last_shown) + max(0.,interval)) if self.last_shown is not None else self.clock()
            if self.clock() < due:
                return None
            state = self.items.popleft()
            self.last_timestamp, self.last_shown = state.timestamp, self.clock()
            self.last_due = self.last_shown if self.last_shown-due>interval else due
            self.in_flight = True
            self.condition.notify_all()
            return state

    def acknowledge(self):
        with self.condition:
            self.in_flight = False
            self.condition.notify_all()

    def finish(self):
        with self.condition:
            self.finished = True
            self.condition.notify_all()

    def wait_drained(self):
        with self.condition:
            while (self.items or self.in_flight) and not self.cancelled:
                self.condition.wait(.05)

    def cancel(self):
        with self.condition:
            self.cancelled = True
            self.items.clear()
            self.condition.notify_all()


class WindowsTimer:
    """Balanced process-scoped 1 ms timer request; no busy loop or permanent setting."""
    def __init__(self):
        self.library = None
        if sys.platform == 'win32':
            import ctypes
            library = ctypes.WinDLL('winmm')
            if library.timeBeginPeriod(1) == 0:
                self.library = library

    def close(self):
        if self.library is not None:
            self.library.timeEndPeriod(1)
            self.library = None
