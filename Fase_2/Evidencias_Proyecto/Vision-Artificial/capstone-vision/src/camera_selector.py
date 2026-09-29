"""Configurar la cámara del equipo: python -m src.camera_selector."""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from .config import CONFIG_PATH, CameraConfig, load_config

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class AvailableCamera:
    """Metadatos del primer frame; no conserva imágenes ni capturas abiertas."""

    index: int
    width: int
    height: int
    backend: str
    reported_fps: float


def scan_cameras(config: CameraConfig) -> list[AvailableCamera]:
    """Prueba índices 0–4 con la apertura, validación y liberación existentes."""
    import cv2

    from .camera import camera_info, camera_session

    available = []
    for index in range(5):
        try:
            with camera_session({**config, "camera_index": index}) as (capture, frame):
                info = camera_info(capture)
                height, width = frame.shape[:2]
                available.append(AvailableCamera(
                    index=index, width=width, height=height,
                    backend=info["backend"], reported_fps=info["fps"],
                ))
        except (RuntimeError, cv2.error) as exc:
            LOGGER.debug("Índice %s no disponible: %s", index, exc)
    return available


def choose_camera(available: list[AvailableCamera]) -> int | None:
    """Pide un índice detectado; q cancela sin guardar."""
    indexes = {camera.index for camera in available}
    if not indexes:
        raise ValueError("No hay cámaras disponibles para seleccionar.")
    while True:
        answer = input("Seleccione camera_index (q para cancelar): ").strip()
        if answer.lower() == "q":
            return None
        try:
            index = int(answer)
        except ValueError:
            index = -1
        if index in indexes:
            return index
        print(f"Selección inválida. Elija uno de {sorted(indexes)} o q para cancelar.")


def save_camera_index(index: int, path: Path = CONFIG_PATH) -> CameraConfig:
    """Cambia solo el índice mediante un temporal validado y reemplazo atómico."""
    if type(index) is not int or not 0 <= index <= 2**31 - 1:
        raise ValueError("camera_index debe ser un entero entre 0 y 2147483647.")
    # Leer de nuevo al guardar conserva los valores vigentes, no una copia del scan.
    current = load_config(path)
    updated = {**current, "camera_index": index}
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n",
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(updated, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        # El archivo está cerrado antes del reemplazo, también en Windows.
        if load_config(temporary) != updated:
            raise RuntimeError("La configuración temporal no coincide con la selección.")
        os.replace(temporary, path)
        saved = load_config(path)
        if saved != updated:
            raise RuntimeError("No se pudo verificar la configuración guardada.")
        return saved
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(path: Path = CONFIG_PATH) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        config = load_config(path)
        print("CAPSTONE - Selector de cámara")
        print(f"Índice configurado: {config['camera_index']}")
        print("Buscando cámaras disponibles (índices 0 a 4)...", flush=True)
        available = scan_cameras(config)
        if not available:
            print("No se encontraron cámaras que entreguen frames. "
                  "La configuración no se modificó. Revisa conexión, permisos "
                  "y aplicaciones que estén utilizando la cámara.")
            return 1
        for camera in available:
            print(f"[{camera.index}] DISPONIBLE | {camera.width}x{camera.height} | "
                  f"{camera.backend} | FPS informado: {camera.reported_fps:g}")
        print(f"Cámaras disponibles: {[camera.index for camera in available]}")
        # Todas las sesiones de captura ya terminaron antes de solicitar entrada.
        index = choose_camera(available)
        if index is None:
            print("Selección cancelada; la configuración no se modificó.")
            return 0
        save_camera_index(index, path)
        print(f"Cámara seleccionada: {index}")
        print(f"Configuración guardada y verificada en {path}.")
        return 0
    except EOFError:
        print("Entrada finalizada; la configuración no se modificó.")
        return 1
    except KeyboardInterrupt:
        print("\nSelector interrumpido.")
        return 130
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        LOGGER.error("No se pudo completar la selección de cámara: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
