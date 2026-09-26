"""YOLO + ByteTrack integrado, una inferencia por frame, sin cámara ni GUI."""

import logging
import math
import time
from collections import deque
from dataclasses import dataclass

from .config import (DetectionConfig, TrackingConfig, load_detection_config,
                     load_tracking_config, validate_tracking_config,
                     resolve_tracker_path, load_bytetrack_config)
from .detector import Detection, load_person_model

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Track(Detection):
    """ID temporal de trayectoria en esta ejecución; no identidad personal."""
    track_id: int

    def __post_init__(self):
        if type(self.track_id) is not int or self.track_id <= 0:
            raise ValueError("track_id debe ser un entero positivo.")

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)


@dataclass(frozen=True)
class FrameTracks:
    tracks: tuple[Track, ...]
    untracked_detections: tuple[Detection, ...]
    inference_ms: float | None
    processing_ms: float


class TrackHistory:
    """Solo puntos para dibujo, nunca imágenes ni decisiones de asociación."""

    def __init__(self, trail_length: int, track_buffer: int):
        if type(trail_length) is not int or not 1 <= trail_length <= 300:
            raise ValueError("trail_length debe estar entre 1 y 300.")
        if type(track_buffer) is not int or not 1 <= track_buffer <= 3000:
            raise ValueError("track_buffer debe estar entre 1 y 3000.")
        self.trail_length = trail_length
        self.track_buffer = track_buffer
        self.points: dict[int, deque] = {}
        self._last_seen: dict[int, int] = {}
        self._frame = 0

    def update(self, tracks: tuple[Track, ...]) -> None:
        self._frame += 1
        # Conserva ausencias breves. Un frame de gracia acompaña el orden de
        # asociación y retirada de perdidos de Ultralytics 8.4.163.
        for track_id, last in tuple(self._last_seen.items()):
            if self._frame - last > self.track_buffer + 1:
                del self.points[track_id]
                del self._last_seen[track_id]
        for track in tracks:
            history = self.points.setdefault(track.track_id, deque(maxlen=self.trail_length))
            history.append(tuple(round(v) for v in track.center))
            self._last_seen[track.track_id] = self._frame


class PersonTracker:
    """Una instancia por sesión; model.track incluye detección y asociación."""

    def __init__(self, detection_config: DetectionConfig | None = None,
                 tracking_config: TrackingConfig | None = None):
        self.config = dict(detection_config if detection_config is not None else load_detection_config())
        self.tracking_config = validate_tracking_config(
            tracking_config if tracking_config is not None else load_tracking_config())
        self.tracker_path = resolve_tracker_path(self.tracking_config["tracker_config"])
        self.bytetrack_config = load_bytetrack_config(self.tracker_path)
        self._model = load_person_model(self.config)
        LOGGER.info("ByteTrack: %s | persist=%s", self.tracker_path, self.tracking_config["persist"])
        if self.config["confidence_threshold"] >= self.bytetrack_config["track_high_thresh"]:
            LOGGER.warning(
                "conf=%.2f filtra antes de ByteTrack: la segunda asociación de baja confianza "
                "no recibe candidatos. Se conserva el baseline de detection.json.",
                self.config["confidence_threshold"])

    def track(self, frame) -> FrameTracks:
        if (frame is None or not hasattr(frame, "shape") or len(frame.shape) != 3
                or frame.shape[2] != 3 or frame.size == 0):
            raise ValueError("Se requiere un frame OpenCV BGR no vacío (alto, ancho, 3).")
        started = time.perf_counter()
        try:
            results = self._model.track(
                source=frame, tracker=str(self.tracker_path),
                persist=self.tracking_config["persist"],
                classes=[self.config["person_class_id"]],
                conf=self.config["confidence_threshold"], iou=self.config["iou_threshold"],
                imgsz=self.config["image_size"], device=self.config["device"],
                stream=False, save=False, save_txt=False, save_conf=False, save_crop=False,
                show=False, visualize=False, verbose=False, augment=False,
            )
            if len(results) != 1:
                raise RuntimeError("YOLO no devolvió exactamente un resultado para el frame.")
            result = results[0]
            tracks, untracked = [], []
            seen_ids = set()
            if result.boxes is not None:
                # Results puede conservar cajas de detección sin ID si no hay
                # tracks confirmados. No inventar IDs ni esconder esas cajas.
                is_track = bool(result.boxes.is_track)
                for row in result.boxes.data.cpu().tolist():
                    if len(row) != (7 if is_track else 6):
                        raise RuntimeError("Formato de cajas/IDs inesperado de Ultralytics.")
                    if not all(type(v) in (int, float) and math.isfinite(v) for v in row):
                        raise RuntimeError("Caja o ID no finito recibido de Ultralytics.")
                    x1, y1, x2, y2 = row[:4]
                    confidence, class_id = row[-2:]
                    if class_id != self.config["person_class_id"]:
                        continue
                    if not 0 <= confidence <= 1 or x2 < x1 or y2 < y1:
                        raise RuntimeError("Caja o confidence inválida recibida de Ultralytics.")
                    geometry = (float(x1), float(y1), float(x2), float(y2), float(confidence), int(class_id))
                    if is_track:
                        raw_id = row[4]
                        if raw_id <= 0 or int(raw_id) != raw_id or int(raw_id) in seen_ids:
                            raise RuntimeError("track_id inválido o repetido en el mismo frame.")
                        track_id = int(raw_id)
                        seen_ids.add(track_id)
                        tracks.append(Track(*geometry, track_id))
                    else:
                        untracked.append(Detection(*geometry))
            inference_ms = result.speed.get("inference") if result.speed else None
            if (type(inference_ms) not in (float, int) or not math.isfinite(inference_ms)
                    or inference_ms < 0):
                inference_ms = None
            return FrameTracks(tuple(tracks), tuple(untracked), inference_ms,
                               (time.perf_counter() - started) * 1000)
        except Exception as exc:
            raise RuntimeError(
                f"Falló YOLO + ByteTrack local: {exc}. Comprueba el YAML y ejecuta "
                "python -m pip install -r requirements.txt (incluye lap); "
                "no se instalan paquetes automáticamente."
            ) from exc
