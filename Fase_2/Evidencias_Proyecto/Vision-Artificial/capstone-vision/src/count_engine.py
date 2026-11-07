"""Transiciones estables A exterior <-> B puerta por ID. Sin IA ni línea final."""

import math
from dataclasses import dataclass, fields
from enum import Enum

from .count_geometry import ZoneGeometry


@dataclass(frozen=True)
class CountSettings:
    zone_dwell_seconds: float = .12
    min_observations: int = 2
    max_gap_seconds: float = 2.
    state_ttl_seconds: float = 30.

    def __post_init__(self):
        for item in fields(self):
            value = getattr(self, item.name)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"Umbral {item.name} debe ser numérico y finito.")
        if not 0 <= self.zone_dwell_seconds <= 60:
            raise ValueError("zone_dwell_seconds debe estar entre 0 y 60 segundos.")
        if type(self.min_observations) is not int or not 2 <= self.min_observations <= 100:
            raise ValueError("min_observations debe ser un entero de 2 a 100.")
        if not 0 < self.max_gap_seconds < self.state_ttl_seconds <= 86400:
            raise ValueError("Se requiere 0 < max_gap_seconds < state_ttl_seconds <= 86400.")


class Phase(str, Enum):
    IDLE = "SIN_ORIGEN_ESTABLE"
    AT_A = "ESTABLE_A"
    AT_B = "ESTABLE_B"
    CANDIDATE_A = "CONFIRMANDO_A"
    CANDIDATE_B = "CONFIRMANDO_B"
    MISSING = "ID_AUSENTE"


@dataclass(frozen=True)
class Observation:
    track_id: int
    point: tuple[float, float]


@dataclass(frozen=True)
class CountEvent:
    number: int
    track_id: int
    episode: int
    timestamp: float
    direction: str
    origin: str
    destination: str


@dataclass
class TrackState:
    phase: Phase = Phase.IDLE
    episode: int = 0
    stable_zone: str | None = None
    candidate: str | None = None
    candidate_since: float = 0.
    candidate_count: int = 0
    last_seen: float = 0.
    zone: str = "FUERA"
    missing: bool = False
    reason: str = "sin origen estable; aparecer en una zona no cuenta"
    reset_reason: str | None = None


class TransitionCounter:
    """Una sesión; una confirmación por cambio de zona estable del mismo ID."""
    MAX_STATES = 512

    def __init__(self, profile, settings=None):
        self.settings = CountSettings() if settings is None else settings
        if not isinstance(self.settings, CountSettings):
            raise ValueError("Se requiere CountSettings validado.")
        self.geometry = ZoneGeometry(profile)
        self.states = {}
        self.total_entries = self.total_exits = self.total_events = 0
        self._timestamp = None

    @staticmethod
    def _clear_candidate(state):
        state.candidate, state.candidate_count = None, 0

    def _reset(self, state, reason):
        state.stable_zone = None
        state.phase, state.reason = Phase.IDLE, reason
        state.reset_reason = reason
        self._clear_candidate(state)

    def update(self, timestamp, observations):
        if (type(timestamp) not in (int, float) or not math.isfinite(timestamp)
                or timestamp < 0 or self._timestamp is not None and timestamp <= self._timestamp):
            raise ValueError("Timestamp: segundos finitos, no negativos y estrictamente crecientes.")
        items = list(observations)
        seen = set()
        for obs in items:
            if (not isinstance(obs, Observation) or type(obs.track_id) is not int
                    or obs.track_id <= 0 or obs.track_id in seen):
                raise ValueError("Cada observación necesita un ID positivo único en el frame.")
            seen.add(obs.track_id)
        surviving = {i for i, s in self.states.items()
                     if timestamp - s.last_seen <= self.settings.state_ttl_seconds}
        if len(surviving | seen) > self.MAX_STATES:
            raise ValueError("Demasiados IDs recientes; no se descartan protecciones para seguir contando.")
        expired = set(self.states) - surviving
        self.states = {i: s for i, s in self.states.items() if i in surviving}
        self._timestamp = timestamp
        for identifier, state in self.states.items():
            state.reset_reason = None
            if identifier not in seen:
                self._clear_candidate(state)
                state.missing = True
                if timestamp - state.last_seen > self.settings.max_gap_seconds:
                    self._reset(state, "perdida_prolongada: se necesita un origen estable nuevo")
                else:
                    state.phase, state.reason = Phase.MISSING, "perdida_breve: sin evento; se reinicia la estabilidad pendiente"
        events = []
        for obs in items:
            state = self.states.setdefault(obs.track_id, TrackState(last_seen=timestamp))
            if obs.track_id in expired:
                self._reset(state, "estado_expirado: este ID necesita establecer nuevamente su origen")
            if timestamp - state.last_seen > self.settings.max_gap_seconds:
                self._reset(state, "intervalo_excesivo: no se atribuye continuidad a este ID")
            elif state.missing:
                self._clear_candidate(state)
            state.last_seen, state.missing = timestamp, False
            point = obs.point
            if (not isinstance(point, (tuple, list)) or len(point) != 2
                    or any(type(v) not in (int, float) or not math.isfinite(v) for v in point)):
                self._reset(state, "punto_invalido_del_tracker: se descarta la historia de este ID")
                state.zone = "INVALIDO"
                continue
            if any(not 0 <= v <= 1 for v in point):
                self._reset(state, "fuera_de_imagen: no se recorta ni cuenta; revisar caja/resolucion del tracker")
                state.zone = "INVALIDO"
                continue
            zone = self.geometry.classify(point)
            state.zone = zone
            if zone == "FUERA":
                self._clear_candidate(state)
                state.phase = Phase.AT_A if state.stable_zone == "A" else Phase.AT_B if state.stable_zone == "B" else Phase.IDLE
                state.reason = "fuera_de_zonas: esperando destino; no es fuera de imagen ni una cancelacion"
                continue
            if zone == state.stable_zone:
                self._clear_candidate(state)
                state.phase = Phase.AT_A if zone == "A" else Phase.AT_B
                state.reason = "misma_zona: sin duplicar; preparado para la zona contraria"
                continue
            if state.candidate != zone:
                state.candidate, state.candidate_since, state.candidate_count = zone, timestamp, 1
            else:
                state.candidate_count = min(state.candidate_count + 1, self.settings.min_observations)
            state.phase = Phase.CANDIDATE_A if zone == "A" else Phase.CANDIDATE_B
            state.reason = "estabilidad_insuficiente: requiere tiempo y observaciones configurados"
            if (state.candidate_count < self.settings.min_observations
                    or timestamp - state.candidate_since + 1e-9 < self.settings.zone_dwell_seconds):
                continue
            origin = state.stable_zone
            state.stable_zone = zone
            self._clear_candidate(state)
            state.phase = Phase.AT_A if zone == "A" else Phase.AT_B
            if origin is None:
                state.reason = "origen_estable: aparicion inicial sin evento"
                continue
            direction = "IN" if (origin, zone) == ("A", "B") else "OUT"
            state.episode += 1
            self.total_events += 1
            if direction == "IN":
                self.total_entries += 1
            else:
                self.total_exits += 1
            state.reason = f"confirmado_{direction}: {origin} -> {zone}; rearmado desde {zone}"
            events.append(CountEvent(self.total_events, obs.track_id, state.episode,
                                     timestamp, direction, origin, zone))
        return tuple(events)


# Conserva el nombre público del primer H5.1; ahora cuenta ambos sentidos.
EntryCounter = TransitionCounter
