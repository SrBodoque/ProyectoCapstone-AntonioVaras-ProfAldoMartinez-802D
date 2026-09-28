"""Apertura y liberación de webcam sin almacenamiento de imágenes."""

import logging
import math
import platform
import sys
from dataclasses import dataclass
from contextlib import contextmanager
from collections.abc import Iterator

import cv2

from .config import CameraConfig, validate_camera_index
from .camera_cli import CameraSelectionCancelled

LOGGER = logging.getLogger(__name__)
SCAN_INDICES = tuple(range(5))


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
    if validate_camera_index(config["camera_index"]) == "auto":
        raise ValueError("Resuelve camera_index='auto' antes de abrir mediante resolve_camera_config().")
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
        except (cv2.error, RuntimeError, OSError) as exc:
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
    def reported(prop):
        try:
            value = capture.get(prop)
            return value if type(value) in (int, float) and math.isfinite(value) and value > 0 else None
        except (cv2.error, OSError):
            return None

    try:
        backend = capture.getBackendName() or "no informado"
    except (cv2.error, OSError) as exc:
        LOGGER.warning("No se pudo consultar el nombre del backend: %s", exc)
        backend = "no informado"
    return {
        "backend": backend,
        "width": reported(cv2.CAP_PROP_FRAME_WIDTH),
        "height": reported(cv2.CAP_PROP_FRAME_HEIGHT),
        "fps": reported(cv2.CAP_PROP_FPS),
    }


@dataclass(frozen=True)
class CameraCandidate:
    """Metadata de un índice funcional; nunca retiene capturas o frames."""
    index: int
    width: int
    height: int
    fps: float | None
    backend: str


def probe_camera(config: CameraConfig, index: int) -> CameraCandidate:
    """Reutiliza apertura/fallback/lectura y libera antes de devolver metadata."""
    with camera_session({**config, "camera_index": index}) as (capture, frame):
        info = camera_info(capture)
        return CameraCandidate(index, int(frame.shape[1]), int(frame.shape[0]),
                               info["fps"], info["backend"])


def find_first_available_camera(config: CameraConfig) -> CameraCandidate:
    """Sondea en orden y se detiene al primer éxito; no lista ni solicita entrada."""
    backend_candidates(config["backend"])
    for index in SCAN_INDICES:
        try:
            return probe_camera(config, index)
        except (RuntimeError, cv2.error, OSError) as exc:
            LOGGER.warning("Índice %s: no disponible. %s", index, exc)
    raise RuntimeError(
        "No se detectó ninguna cámara funcional en los índices 0–4. "
        "Comprueba conexión, permisos y otras aplicaciones. "
        "Ejecuta python -m src.diagnostics --scan; para otro índice utiliza --camera N.")


def discover_cameras(config: CameraConfig) -> list[CameraCandidate]:
    """Un recorrido secuencial 0–4; como máximo un candidato por índice."""
    backend_candidates(config["backend"])  # Rechaza backend incompatible antes del scan.
    candidates = []
    for index in SCAN_INDICES:
        try:
            candidates.append(probe_camera(config, index))
        except (RuntimeError, cv2.error, OSError) as exc:
            LOGGER.warning("Índice %s: no disponible. %s", index, exc)
    return candidates


def describe_camera(candidate: CameraCandidate) -> str:
    fps = f"{candidate.fps:g}" if candidate.fps is not None else "desconocidos"
    return (f"[{candidate.index}] Cámara {candidate.index} | {candidate.width}x{candidate.height} | "
            f"backend {candidate.backend} | FPS informados: {fps}")


def select_camera(candidates: list[CameraCandidate]) -> int:
    """Selecciona un índice descubierto sin abrir ni reescanear dispositivos."""
    if not candidates:
        raise RuntimeError(
            "No se detectaron cámaras disponibles en los índices 0–4. Comprueba conexión, permisos, "
            "otras aplicaciones y que la cámara virtual esté activa. Ejecuta "
            "python -m src.diagnostics --scan; para otro índice utiliza --camera N.")
    print("Cámaras disponibles:", flush=True)
    for candidate in candidates:
        print(describe_camera(candidate), flush=True)
    if len(candidates) == 1:
        selected = candidates[0].index
        print(f"Seleccionando automáticamente cámara {selected}.", flush=True)
        return selected
    print("Se detectaron múltiples cámaras.", flush=True)
    no_input = ("Se detectaron múltiples cámaras pero no existe entrada interactiva. "
                "Utiliza --camera N o configura camera_index explícitamente en config/camera.json.")
    try:
        interactive = sys.stdin is not None and sys.stdin.isatty()
    except (OSError, ValueError):
        interactive = False
    if not interactive:
        raise RuntimeError(no_input)
    available = {candidate.index for candidate in candidates}
    while True:
        try:
            answer = input("Seleccione cámara por índice (q para cancelar): ").strip()
        except (EOFError, OSError, ValueError) as exc:
            raise RuntimeError(no_input) from exc
        if answer.lower() == "q":
            raise CameraSelectionCancelled()
        try:
            selected = int(answer)
        except ValueError:
            selected = None
        if selected in available:
            return selected
        print("Selección inválida. Introduce uno de los índices mostrados o q.", flush=True)


def resolve_camera_config(config: CameraConfig, camera_override: int | None = None) -> CameraConfig:
    """CLI > JSON fijo > scan/selector; devuelve copia, nunca escribe el JSON."""
    if camera_override is not None:
        if type(camera_override) is not int:
            raise ValueError("--camera requiere un índice entero.")
        selected = validate_camera_index(camera_override)
    else:
        selected = validate_camera_index(config["camera_index"])
    if selected == "auto":
        print("Buscando cámaras en índices 0–4; puede tardar...", flush=True)
        selected = select_camera(discover_cameras(config))
    LOGGER.info("Cámara seleccionada: índice %s. Abriendo cámara...", selected)
    return {**config, "camera_index": selected}
