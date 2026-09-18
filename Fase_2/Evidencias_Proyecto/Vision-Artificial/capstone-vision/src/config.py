"""Carga y validación de la única configuración de cámara."""

import json
import math
from pathlib import Path
from typing import TypedDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "camera.json"
BACKENDS = ("auto", "dshow", "msmf", "v4l2", "avfoundation")


class CameraConfig(TypedDict):
    camera_index: int
    width: int
    height: int
    fps: float
    backend: str


def load_config(path: Path = CONFIG_PATH) -> CameraConfig:
    """Rechaza campos ausentes, desconocidos y valores inválidos."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise ValueError(f"No se pudo leer {path}: {exc}. Restaura config/camera.json.") from exc
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError(f"JSON inválido en {path}: {exc}. Revisa comas y comillas.") from exc
    fields = {"camera_index", "width", "height", "fps", "backend"}
    if not isinstance(data, dict) or set(data) != fields:
        raise ValueError(f"{path} debe contener exactamente: {', '.join(sorted(fields))}.")
    for key in ("camera_index", "width", "height"):
        minimum = 0 if key == "camera_index" else 1
        if type(data[key]) is not int or not minimum <= data[key] <= 2**31 - 1:
            raise ValueError(f"{key} debe ser un entero entre {minimum} y {2**31 - 1}.")
    fps = data["fps"]
    if type(fps) not in (int, float) or not 0 < fps <= 2**31 - 1 or not math.isfinite(fps):
        raise ValueError("fps debe ser un número positivo y finito.")
    if not isinstance(data["backend"], str) or data["backend"] not in BACKENDS:
        raise ValueError(f"backend debe ser uno de: {', '.join(BACKENDS)}.")
    return data
