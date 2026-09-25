"""Carga y validación de configuración de cámara y detección."""

import json
import math
from pathlib import Path
from typing import TypedDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "camera.json"
DETECTION_CONFIG_PATH = PROJECT_ROOT / "config" / "detection.json"
BACKENDS = ("auto", "dshow", "msmf", "v4l2", "avfoundation")


class CameraConfig(TypedDict):
    camera_index: int
    width: int
    height: int
    fps: float
    backend: str


def _read_config(path: Path, fields: set[str]) -> dict:
    """Lector JSON común; conserva UTF-8 con BOM y rechazo de campos extra."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise ValueError(f"No se pudo leer {path}: {exc}. Restaura config/{path.name}.") from exc
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError(f"JSON inválido en {path}: {exc}. Revisa comas y comillas.") from exc
    if not isinstance(data, dict) or set(data) != fields:
        raise ValueError(f"{path} debe contener exactamente: {', '.join(sorted(fields))}.")
    return data


def load_config(path: Path = CONFIG_PATH) -> CameraConfig:
    """Rechaza campos ausentes, desconocidos y valores inválidos."""
    data = _read_config(path, {"camera_index", "width", "height", "fps", "backend"})
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


class DetectionConfig(TypedDict):
    model: str
    confidence_threshold: float
    iou_threshold: float
    image_size: int
    device: str
    person_class_id: int
    show_confidence: bool


def load_detection_config(path: Path = DETECTION_CONFIG_PATH) -> DetectionConfig:
    """Parámetros iniciales del Hito 2; CPU y pesos oficiales YOLO26n."""
    data = _read_config(path, {"model", "confidence_threshold", "iou_threshold",
                              "image_size", "device", "person_class_id", "show_confidence"})
    model = data["model"]
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model debe ser un string no vacío.")
    # Acota este hito al checkpoint oficial, evitando URLs, YAML o modelos de otras tareas.
    if model != "yolo26n.pt":
        raise ValueError("model debe ser yolo26n.pt en este hito; se resuelve desde la raíz del proyecto.")
    for key in ("confidence_threshold", "iou_threshold"):
        value = data[key]
        if type(value) not in (int, float) or not 0 <= value <= 1 or not math.isfinite(value):
            raise ValueError(f"{key} debe ser un número finito entre 0.0 y 1.0.")
    for key, minimum in (("image_size", 1), ("person_class_id", 0)):
        if type(data[key]) is not int or not minimum <= data[key] <= 2**31 - 1:
            raise ValueError(f"{key} debe ser un entero entre {minimum} y {2**31 - 1}.")
    if data["device"] != "cpu":
        raise ValueError("device debe ser 'cpu' para el baseline del Hito 2.")
    if type(data["show_confidence"]) is not bool:
        raise ValueError("show_confidence debe ser true o false.")
    return data
