"""Detección local de personas sobre frames en memoria; sin captura ni GUI."""

import logging
import math
import os
import time
from dataclasses import dataclass

from .config import DetectionConfig, PROJECT_ROOT, load_detection_config

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Detection:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int


@dataclass(frozen=True)
class FrameDetections:
    detections: tuple[Detection, ...]
    inference_ms: float | None
    processing_ms: float


def _load_yolo():
    """Importación diferida: importar src.detector no carga PyTorch ni pesos."""
    # Evita sondeos de conectividad, telemetría y auto-instalación. La descarga
    # oficial explícita de un checkpoint ausente sigue disponible en YOLO().
    os.environ["YOLO_OFFLINE"] = "true"
    os.environ["YOLO_AUTOINSTALL"] = "false"
    os.environ["YOLO_CONFIG_DIR"] = str(PROJECT_ROOT / ".ultralytics")
    try:
        (PROJECT_ROOT / ".ultralytics").mkdir(exist_ok=True)
        from ultralytics import YOLO, settings
        settings.update({"sync": False})
    except Exception as exc:
        raise RuntimeError(
            "No se pudo cargar Ultralytics/PyTorch. Activa .venv y ejecuta "
            "python -m pip install -r requirements.txt y python -m pip check. "
            f"Detalle: {exc}"
        ) from exc
    return YOLO


def load_person_model(config: DetectionConfig):
    """Carga compartida H2/H3: un modelo, pesos locales y clase person validada."""
    model_path = PROJECT_ROOT / config["model"]
    LOGGER.info("Cargando %s en %s; el primer inicio puede descargar los pesos oficiales.",
                config["model"], config["device"])
    yolo = _load_yolo()
    started = time.perf_counter()
    try:
        model = yolo(str(model_path), task="detect")
        names = model.names
        class_id = config["person_class_id"]
        if names[0] != "person" or names[class_id] != "person":
            raise ValueError("La clase 0 y person_class_id deben corresponder a 'person'.")
    except Exception as exc:
        raise RuntimeError(
            f"No se pudo preparar {config['model']}: {exc}. "
            "Comprueba person_class_id=0, los pesos oficiales y la conexión "
            "si es la primera descarga."
        ) from exc
    LOGGER.info("Modelo cargado una vez en %.2f s; clase person=%s.",
                time.perf_counter() - started, class_id)
    return model


class PersonDetector:
    """Mantiene un único modelo y devuelve datos simples de cada frame."""

    def __init__(self, config: DetectionConfig | None = None):
        self.config = dict(config if config is not None else load_detection_config())
        self.model_path = PROJECT_ROOT / self.config["model"]
        self._model = load_person_model(self.config)

    def detect(self, frame) -> FrameDetections:
        """Inferencia individual. No acepta una URL ni un índice de webcam."""
        if (frame is None or not hasattr(frame, "shape") or
                len(frame.shape) != 3 or frame.shape[2] != 3 or frame.size == 0):
            raise ValueError("Se requiere un frame OpenCV BGR no vacío (alto, ancho, 3).")
        started = time.perf_counter()
        try:
            results = self._model.predict(
                source=frame,
                classes=[self.config["person_class_id"]],
                conf=self.config["confidence_threshold"],
                iou=self.config["iou_threshold"],
                imgsz=self.config["image_size"],
                device=self.config["device"],
                stream=False,
                save=False, save_txt=False, save_conf=False, save_crop=False,
                show=False, visualize=False, verbose=False,
                augment=False,
            )
            if len(results) != 1:
                raise RuntimeError("YOLO no devolvió exactamente un resultado para el frame.")
            result = results[0]
            detections = []
            if result.boxes is not None:
                # .data: x1, y1, x2, y2, confianza, clase; nunca usamos track().
                for row in result.boxes.data.cpu().tolist():
                    if len(row) != 6:
                        raise RuntimeError("Formato de detección inesperado: se requieren seis campos.")
                    x1, y1, x2, y2, confidence, class_id = row
                    if class_id != self.config["person_class_id"]:
                        continue  # Defensa adicional al filtro classes de la API.
                    if confidence < self.config["confidence_threshold"]:
                        continue
                    detections.append(Detection(float(x1), float(y1), float(x2), float(y2),
                                                float(confidence), int(class_id)))
            inference_ms = result.speed.get("inference") if result.speed else None
            if (not isinstance(inference_ms, (float, int)) or
                    not math.isfinite(inference_ms) or inference_ms < 0):
                inference_ms = None
            return FrameDetections(tuple(detections), inference_ms,
                                   (time.perf_counter() - started) * 1000)
        except Exception as exc:
            raise RuntimeError(f"Falló la inferencia local de personas: {exc}") from exc
