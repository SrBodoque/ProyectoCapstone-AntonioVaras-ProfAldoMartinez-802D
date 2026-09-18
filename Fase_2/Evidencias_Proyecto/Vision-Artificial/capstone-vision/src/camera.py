"""Apertura y liberación de webcam sin almacenamiento de imágenes."""

import logging
import platform
from contextlib import contextmanager
from collections.abc import Iterator

import cv2

from .config import CameraConfig

LOGGER = logging.getLogger(__name__)


def backend_candidates(name: str) -> list[tuple[str, int]]:
    """Auto en Windows prueba DirectShow, MSMF y por último CAP_ANY."""
    system = platform.system()
    supported = {
        "Windows": [("dshow", cv2.CAP_DSHOW), ("msmf", cv2.CAP_MSMF)],
        "Linux": [("v4l2", cv2.CAP_V4L2)],
        "Darwin": [("avfoundation", cv2.CAP_AVFOUNDATION)],
    }.get(system, [])
    if name == "auto":
        return supported + [("auto", cv2.CAP_ANY)]
    for candidate in supported:
        if candidate[0] == name:
            return [candidate]
    raise ValueError(f"El backend '{name}' no corresponde a {system}. Usa 'auto'.")


def open_camera(config: CameraConfig) -> tuple[cv2.VideoCapture, object]:
    """Devuelve captura abierta y primer frame; libera cada intento fallido."""
    failures = []
    for name, api in backend_candidates(config["backend"]):
        capture = cv2.VideoCapture()
        succeeded = False
        try:
            if not capture.open(config["camera_index"], api) or not capture.isOpened():
                raise RuntimeError("no se pudo abrir")
            for prop, key in ((cv2.CAP_PROP_FRAME_WIDTH, "width"),
                              (cv2.CAP_PROP_FRAME_HEIGHT, "height"),
                              (cv2.CAP_PROP_FPS, "fps")):
                if not capture.set(prop, config[key]):
                    LOGGER.warning("El backend %s no aceptó %s=%s.", name, key, config[key])
            ok, frame = capture.read()
            if not ok or frame is None or frame.size == 0:
                raise RuntimeError("abrió, pero no entregó el primer frame")
            succeeded = True
            return capture, frame
        except (cv2.error, RuntimeError) as exc:
            failures.append(f"{name}: {exc}")
            LOGGER.warning("Intento %s: %s", name, exc)
        finally:
            if not succeeded:
                capture.release()
    raise RuntimeError(
        f"No se pudo utilizar camera_index={config['camera_index']}. "
        "Prueba otro índice (1, 2, etc.) en config/camera.json; cierra Cámara, Teams "
        "u otras aplicaciones y revisa conexión y permisos de cámara para aplicaciones "
        "de escritorio en Windows. Detalles: " + " | ".join(failures)
    )


@contextmanager
def camera_session(config: CameraConfig) -> Iterator[tuple[cv2.VideoCapture, object]]:
    """Garantiza liberación aun si el consumidor falla o recibe Ctrl+C."""
    capture, frame = open_camera(config)
    try:
        yield capture, frame
    finally:
        capture.release()


def camera_info(capture: cv2.VideoCapture) -> dict:
    """Propiedades informadas por el controlador; FPS no es una medición."""
    try:
        backend = capture.getBackendName()
    except cv2.error as exc:
        LOGGER.warning("No se pudo consultar el nombre del backend: %s", exc)
        backend = "no informado"
    return {
        "backend": backend,
        "width": capture.get(cv2.CAP_PROP_FRAME_WIDTH),
        "height": capture.get(cv2.CAP_PROP_FRAME_HEIGHT),
        "fps": capture.get(cv2.CAP_PROP_FPS),
    }
