"""Selección exclusiva de track_count; reutiliza rutas, YAML y overrides actuales."""

import json
from dataclasses import dataclass, fields
from pathlib import Path

from .config import PROJECT_ROOT, load_tracking_config, load_tracker_config, resolve_tracker_path
from .count_engine import CountSettings
from .track_botsort_reid import BOTSORT_CONFIG, BOTSORT_LABEL
from .track_fast import FASTTRACK_CONFIG
from .track_recovery import RECOVERY_CONFIG, RECOVERY_CONFIDENCE, RECOVERY_LABEL

COUNTING_PATH = PROJECT_ROOT / "config" / "counting.json"
TRACKERS = ("botsort_reid", "fasttracker", "bytetrack", "recovery")


@dataclass(frozen=True)
class CountingConfig:
    tracker: str
    thresholds: CountSettings


@dataclass(frozen=True)
class TrackerSelection:
    name: str
    label: str
    tracking_config: dict
    tracker_params: dict
    confidence_override: float | None

    def constructor_options(self):
        return ({} if self.confidence_override is None
                else {"tracking_confidence_override": self.confidence_override})


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError(f"counting.json tiene una clave repetida: {key}.")
        result[key] = value
    return result


def load_counting_config(path=COUNTING_PATH):
    try:
        path = Path(path)
        if path.stat().st_size > 16384: raise ValueError("counting.json es demasiado grande.")
        data = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_unique)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"No se pudo leer config/counting.json: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {"tracker", "thresholds"}:
        raise ValueError("counting.json requiere exactamente tracker y thresholds.")
    if not isinstance(data["tracker"], str) or data["tracker"] not in TRACKERS:
        raise ValueError("Tracker de conteo inválido. Valores: " + ", ".join(TRACKERS))
    values = data["thresholds"]
    if not isinstance(values, dict) or set(values) != {f.name for f in fields(CountSettings)}:
        raise ValueError("thresholds requiere zone_dwell_seconds, min_observations, max_gap_seconds y state_ttl_seconds. La configuracion antigua con salida final ya no es valida.")
    return CountingConfig(data["tracker"], CountSettings(**values))


def select_tracker(name):
    if not isinstance(name, str) or name not in TRACKERS:
        raise ValueError("Tracker de conteo desconocido; no se selecciona otro automáticamente.")
    base = load_tracking_config()
    choices = {
        "botsort_reid": (BOTSORT_CONFIG, BOTSORT_LABEL, "botsort", None),
        "fasttracker": (FASTTRACK_CONFIG, "FastTracker", "fasttrack", None),
        "bytetrack": (base["tracker_config"], "ByteTrack", "bytetrack", None),
        "recovery": (RECOVERY_CONFIG, RECOVERY_LABEL, "bytetrack", RECOVERY_CONFIDENCE),
    }
    path, label, expected, confidence = choices[name]
    params = load_tracker_config(resolve_tracker_path(path))
    if params["tracker_type"] != expected:
        raise ValueError(f"El YAML de {name} no corresponde al backend {expected}; revise la configuración original.")
    if name == "bytetrack" and resolve_tracker_path(path) == resolve_tracker_path(RECOVERY_CONFIG):
        raise ValueError("El baseline apunta al YAML de Recovery. Restaure la configuración original; no se omite su override.")
    return TrackerSelection(name, label, {**base, "tracker_config": path}, params, confidence)
