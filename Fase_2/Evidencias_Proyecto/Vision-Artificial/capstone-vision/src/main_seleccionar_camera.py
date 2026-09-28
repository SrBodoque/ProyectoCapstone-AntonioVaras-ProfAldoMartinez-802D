"""Preview con selección: python -m src.main_seleccionar_camera. Sin IA."""

import argparse
import logging
import os
import sys

from . import main as preview
from .camera_cli import CameraSelectionCancelled
from .config import CameraConfig, load_config

LOGGER = logging.getLogger(__name__)


def run_preview(cv2, config: CameraConfig) -> None:
    """Selecciona temporalmente, incluso con JSON fijo; reutiliza el único preview."""
    from .camera import resolve_camera_config

    selected = resolve_camera_config({**config, "camera_index": "auto"})
    preview.run_preview(cv2, selected)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Para abrir un índice sin escaneo: python -m src.main --camera N.")
    parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        import cv2
    except ImportError as exc:
        LOGGER.error("No se pudo importar OpenCV: %s. Activa .venv y ejecuta python -m pip install -r requirements.txt", exc)
        return 1
    try:
        config = load_config()
        if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            raise RuntimeError("No hay sesión gráfica disponible. Ejecuta el preview en tu equipo con escritorio y webcam.")
        run_preview(cv2, config)
    except CameraSelectionCancelled:
        LOGGER.info("Selección de cámara cancelada; recursos liberados.")
        return 0
    except KeyboardInterrupt:
        LOGGER.info("Cierre solicitado con Ctrl+C.")
    except (ValueError, RuntimeError, cv2.error) as exc:
        LOGGER.error("%s", exc)
        LOGGER.info("Para apertura directa: python -m src.main --camera N (usa un índice disponible).")
        return 1
    LOGGER.info("Vista previa finalizada; cámara liberada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
