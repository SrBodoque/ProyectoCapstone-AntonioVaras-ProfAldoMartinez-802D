"""Carga y validación de configuración de cámara y detección."""

import json
import math
from pathlib import Path, PureWindowsPath
from typing import TypedDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "camera.json"
DETECTION_CONFIG_PATH = PROJECT_ROOT / "config" / "detection.json"
TRACKING_CONFIG_PATH = PROJECT_ROOT / "config" / "tracking.json"
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


class TrackingConfig(TypedDict):
    tracker_config: str
    persist: bool
    show_track_id: bool
    show_trail: bool
    trail_length: int


def resolve_tracker_path(value: str) -> Path:
    """Ruta portable, local al proyecto, independiente del directorio actual."""
    if (not isinstance(value, str) or not value.strip() or "\\" in value
            or Path(value).is_absolute() or PureWindowsPath(value).drive):
        raise ValueError("tracker_config debe ser una ruta relativa al proyecto con separadores '/'.")
    path = (PROJECT_ROOT / value).resolve()
    if (not path.is_relative_to(PROJECT_ROOT) or path.suffix.lower() not in (".yaml", ".yml")
            or not path.is_file()):
        raise ValueError("tracker_config debe apuntar a un YAML existente dentro del proyecto.")
    return path


def validate_tracking_config(data: dict) -> TrackingConfig:
    fields = {"tracker_config", "persist", "show_track_id", "show_trail", "trail_length"}
    if not isinstance(data, dict) or set(data) != fields:
        raise ValueError(f"tracking.json debe contener exactamente: {', '.join(sorted(fields))}.")
    resolve_tracker_path(data["tracker_config"])
    for key in ("persist", "show_track_id", "show_trail"):
        if type(data[key]) is not bool:
            raise ValueError(f"{key} debe ser true o false.")
    if not data["persist"]:
        raise ValueError("persist debe ser true en Hito 3: los frames pertenecen a una secuencia continua.")
    if type(data["trail_length"]) is not int or not 1 <= data["trail_length"] <= 300:
        raise ValueError("trail_length debe ser un entero entre 1 y 300.")
    return dict(data)


def load_tracking_config(path: Path = TRACKING_CONFIG_PATH) -> TrackingConfig:
    return validate_tracking_config(_read_config(path, {
        "tracker_config", "persist", "show_track_id", "show_trail", "trail_length"}))


def load_bytetrack_config(path: Path) -> dict:
    """YAML estricto del baseline; PyYAML ya es dependencia de Ultralytics."""
    try:
        import yaml
    except ImportError as exc:
        raise ValueError("Falta PyYAML; ejecuta python -m pip install -r requirements.txt.") from exc
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError(f"YAML inválido o inaccesible: {path}: {exc}") from exc
    fields = {"tracker_type", "track_high_thresh", "track_low_thresh", "new_track_thresh",
              "track_buffer", "match_thresh", "fuse_score"}
    if not isinstance(data, dict) or set(data) != fields:
        raise ValueError(f"YAML ByteTrack debe contener exactamente: {', '.join(sorted(fields))}.")
    if data["tracker_type"] != "bytetrack":
        raise ValueError("tracker_type debe ser bytetrack.")
    for key in ("track_high_thresh", "track_low_thresh", "new_track_thresh", "match_thresh"):
        value = data[key]
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{key} debe ser un número finito entre 0 y 1.")
    if data["track_low_thresh"] >= data["track_high_thresh"]:
        raise ValueError("track_low_thresh debe ser menor que track_high_thresh.")
    if type(data["track_buffer"]) is not int or not 1 <= data["track_buffer"] <= 3000:
        raise ValueError("track_buffer debe ser un entero entre 1 y 3000 frames.")
    if type(data["fuse_score"]) is not bool:
        raise ValueError("fuse_score debe ser true o false.")
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
