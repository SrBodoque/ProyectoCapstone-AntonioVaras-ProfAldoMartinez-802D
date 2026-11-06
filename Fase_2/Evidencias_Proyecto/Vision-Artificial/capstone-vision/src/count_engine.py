"""FSM de entradas por episodio. Datos normalizados + reloj; sin cámara ni IA."""

import math
from dataclasses import dataclass, fields
from enum import Enum

from .count_geometry import RouteGeometry


@dataclass(frozen=True)
class CountSettings:
    zone_dwell_seconds: float = .12
    exit_dwell_seconds: float = .12
    min_observations: int = 2
    position_margin: float = .04
    max_gap_seconds: float = .5
    episode_timeout_seconds: float = 12.
    state_ttl_seconds: float = 30.
    max_speed_per_second: float = 4.

    def __post_init__(self):
        for item in fields(self):
            value = getattr(self, item.name)
            if type(value) not in (int, float) or not 0 < value < 1e6 or not math.isfinite(value):
                raise ValueError(f"Umbral {item.name} debe ser positivo y finito.")
        if type(self.min_observations) is not int or not 2 <= self.min_observations <= 10:
            raise ValueError("min_observations debe ser un entero de 2 a 10.")
        if not .005 <= self.position_margin <= .2:
            raise ValueError("position_margin debe estar entre 0.005 y 0.2 distancias A/B.")
        if not (max(self.zone_dwell_seconds, self.exit_dwell_seconds) < self.episode_timeout_seconds
                and self.max_gap_seconds < self.episode_timeout_seconds < self.state_ttl_seconds):
            raise ValueError("Dwell y max_gap deben ser menores que episode_timeout, y este menor que state_ttl.")


class Phase(str, Enum):
    IDLE = "SIN_RECORRIDO"
    AT_A = "INICIO_EN_A"
    APPROACHING = "AVANZANDO_A_B"
    AT_B = "EN_B"
    CONFIRMING = "CONFIRMANDO_SALIDA_B"
    CONFIRMED = "ENTRADA_CONFIRMADA"
    CANCELLED = "CANCELADO"
    REVERSE = "SALIDA_OBSERVADA"


@dataclass(frozen=True)
class Observation:
    track_id: int
    point: tuple[float, float]  # (x / ancho, y / alto), bottom-center del frame.


@dataclass(frozen=True)
class EntryEvent:
    number: int
    track_id: int
    episode: int
    timestamp: float


@dataclass
class TrackState:
    phase: Phase = Phase.IDLE
    episode: int = 0
    started: float | None = None
    last_seen: float = 0.
    last_point: tuple | None = None
    zone: str = "FUERA"
    peak: float = -math.inf
    evidence: str | None = None
    evidence_since: float = 0.
    evidence_count: int = 0
    crossing: object | None = None
    missing: bool = False
    first_in_b: bool = False
    return_a: bool = False
    reason: str = "sin recorrido"


BLOCKED = (Phase.CONFIRMED, Phase.CANCELLED, Phase.REVERSE)
ACTIVE = (Phase.AT_A, Phase.APPROACHING, Phase.AT_B, Phase.CONFIRMING)


class EntryCounter:
    """Una instancia = una sesión, total inicial cero. No conserva lista de eventos."""
    MAX_STATES = 512

    def __init__(self, profile, settings=None):
        self.settings = CountSettings() if settings is None else settings
        if not isinstance(self.settings, CountSettings):
            raise ValueError("Se requiere CountSettings validado.")
        self.geometry = RouteGeometry(profile, self.settings.position_margin)
        self.total_entries = 0
        self.states = {}
        self._timestamp = None

    def _stable(self, state, kind, now, duration):
        if kind is None:
            state.evidence, state.evidence_count = None, 0
            return False
        if state.evidence != kind:
            state.evidence, state.evidence_since, state.evidence_count = kind, now, 1
        else:
            state.evidence_count = min(state.evidence_count + 1, self.settings.min_observations)
        return (state.evidence_count >= self.settings.min_observations
                and now - state.evidence_since + 1e-9 >= duration)

    def _cancel(self, state, reason):
        state.phase, state.reason = Phase.CANCELLED, reason
        state.crossing, state.return_a = None, False
        self._stable(state, None, 0, 0)

    def update(self, timestamp, observations):
        """Un frame completo, incluso vacío. Valida todo antes de mutar el contador."""
        if (type(timestamp) not in (int, float) or not 0 <= timestamp < 1e100
                or not math.isfinite(timestamp)
                or self._timestamp is not None and timestamp <= self._timestamp):
            raise ValueError("Timestamp inválido: use segundos finitos, no negativos y estrictamente crecientes.")
        items = list(observations)
        seen = set()
        for obs in items:
            if (not isinstance(obs, Observation) or type(obs.track_id) is not int or obs.track_id <= 0
                    or obs.track_id in seen):
                raise ValueError("Cada observación necesita un ID positivo único dentro del frame.")
            if (not isinstance(obs.point, (tuple, list)) or len(obs.point) != 2
                    or any(type(v) not in (int, float) or not 0 <= v <= 1 or not math.isfinite(v) for v in obs.point)):
                raise ValueError("Posición inválida: bottom-center normalizado finito dentro de la imagen.")
            seen.add(obs.track_id)
        surviving = {i for i, s in self.states.items() if timestamp - s.last_seen <= self.settings.state_ttl_seconds}
        if len(surviving | seen) > self.MAX_STATES:
            raise ValueError("Demasiados tracks recientes; se detiene el conteo sin descartar protecciones de episodios.")
        self._timestamp = timestamp
        self.states = {i: s for i, s in self.states.items() if i in surviving}
        for identifier, state in self.states.items():
            if identifier not in seen:
                state.missing = True
                self._stable(state, None, 0, 0)
                if state.phase == Phase.CONFIRMING:
                    self._cancel(state, "salida B interrumpida; falta evidencia espacial continua")
                elif state.phase in ACTIVE and (timestamp - state.last_seen > self.settings.max_gap_seconds
                                                or timestamp - state.started > self.settings.episode_timeout_seconds):
                    self._cancel(state, "recorrido perdido o expirado")
        events = []
        for obs in items:
            point = self.geometry.project(obs.point)
            zone = self.geometry.classify(obs.point)
            state = self.states.setdefault(obs.track_id, TrackState(last_seen=timestamp))
            gap = timestamp - state.last_seen
            if state.last_point is not None:
                if gap > self.settings.max_gap_seconds:
                    if state.phase not in BLOCKED: self._cancel(state, "intervalo sin evidencia suficiente")
                    state.crossing, state.return_a = None, False
                    self._stable(state, None, 0, 0)
                elif (math.dist(point, state.last_point) > self.settings.max_speed_per_second * gap
                      + self.settings.position_margin):
                    self._cancel(state, "salto de posición incompatible con continuidad")
                elif state.missing and (zone != state.zone or state.phase == Phase.CONFIRMING):
                    if state.phase not in BLOCKED: self._cancel(state, "cambio de zona durante una pérdida")
                    state.crossing, state.return_a = None, False
            if state.phase in ACTIVE and timestamp - state.started > self.settings.episode_timeout_seconds:
                self._cancel(state, "recorrido expirado")
            event = self._advance(obs.track_id, state, zone, point, timestamp,
                                  continuous=not state.missing and gap <= self.settings.max_gap_seconds)
            state.last_seen, state.last_point, state.zone, state.missing = timestamp, point, zone, False
            if event is not None: events.append(event)
        return tuple(events)

    def _advance(self, identifier, state, zone, point, now, continuous):
        margin = self.settings.position_margin
        deep = self.geometry.deep(zone, point)
        if state.phase in BLOCKED:
            self._rearm(state, zone, point, now, deep, continuous)
            return None
        if state.phase == Phase.IDLE:
            # Una observación en B sin A previa ya impide inventar un inicio
            # de entrada al retroceder a A, aunque B no alcance el dwell.
            if zone == "B": state.first_in_b = True
            stable = self._stable(state, zone if deep else None, now, self.settings.zone_dwell_seconds)
            if stable and zone == "B":
                state.first_in_b, state.reason = True, "observado en B sin recorrido desde A"
            if stable and zone == "A":
                if state.first_in_b:
                    state.phase, state.return_a, state.reason = Phase.REVERSE, True, "sentido B -> A; salida sin conteo"
                    self._stable(state, None, now, 0)
                else:
                    state.phase, state.started, state.peak = Phase.AT_A, now, point[0]
                    state.episode += 1
                    state.reason = "inicio estable en A"
            return None
        if point[0] < state.peak - 2 * margin:
            self._cancel(state, "retroceso longitudinal")
            return None
        state.peak = max(state.peak, point[0])
        if state.phase == Phase.AT_A and zone != "A":
            crossing = (self.geometry.exit_through("A", state.last_point, point)
                        if continuous and state.last_point is not None and state.zone == "A" else None)
            if crossing is None:
                self._cancel(state, "salida de A lateral, inversa o no observada")
                return None
            state.phase, state.reason = Phase.APPROACHING, "avanzando A -> B"
            self._stable(state, None, now, 0)
        if state.phase == Phase.APPROACHING:
            if zone == "A":
                self._cancel(state, "regresó a A antes de completar")
                return None
            if self._stable(state, "B" if zone == "B" and deep else None, now, self.settings.zone_dwell_seconds):
                state.phase, state.reason = Phase.AT_B, "B estable después de A; aún sin entrada"
            return None
        if state.phase == Phase.AT_B and zone != "B":
            if zone != "FUERA" or not continuous or state.zone != "B":
                self._cancel(state, "salida de B sin continuidad o en sentido inverso")
                return None
            state.crossing = self.geometry.exit_through("B", state.last_point, point)
            if state.crossing is None:
                self._cancel(state, "salida de B lateral, inversa o junto a vértice ambiguo")
                return None
            state.phase, state.reason = Phase.CONFIRMING, "comprobando salida frontal de B"
            self._stable(state, None, now, 0)
        if state.phase == Phase.CONFIRMING:
            if zone == "B":
                state.phase, state.crossing, state.reason = Phase.AT_B, None, "regresó al borde B; confirmación anulada"
                self._stable(state, None, now, 0)
                return None
            eligible = zone == "FUERA" and self.geometry.beyond(state.crossing, point)
            if self._stable(state, "SALIDA_B" if eligible else None, now, self.settings.exit_dwell_seconds):
                state.phase, state.reason = Phase.CONFIRMED, "entrada confirmada una vez; esperar recorrido de regreso"
                state.crossing, state.return_a = None, False
                self.total_entries += 1
                return EntryEvent(self.total_entries, identifier, state.episode, now)
        return None

    def _rearm(self, state, zone, point, now, deep, continuous):
        """Rearme espacial: volver a A y salir de A hacia exterior, ambos estables."""
        if zone == "A":
            state.crossing = None
            if self._stable(state, "RETORNO_A" if deep else None, now, self.settings.zone_dwell_seconds):
                state.return_a = True
                if state.phase == Phase.CONFIRMED: state.phase = Phase.REVERSE
                state.reason = "retorno en A; falta salir hacia exterior para rearmar"
            return
        if not state.return_a or zone != "FUERA":
            self._stable(state, None, now, 0)
            if zone == "B": state.return_a = False
            state.crossing = None
            return
        if state.zone == "A":
            state.crossing = (self.geometry.exit_through("A", state.last_point, point, -1) if continuous else None)
        eligible = (continuous and state.crossing is not None
                    and self.geometry.beyond(state.crossing, point))
        if self._stable(state, "EXTERIOR" if eligible else None, now, self.settings.exit_dwell_seconds):
            state.phase, state.started, state.peak = Phase.IDLE, None, -math.inf
            state.first_in_b, state.return_a, state.crossing = False, False, None
            state.reason = "rearmado tras retorno A -> exterior; necesita un recorrido nuevo completo"
            self._stable(state, None, now, 0)
