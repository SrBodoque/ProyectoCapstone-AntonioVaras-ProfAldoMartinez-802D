"""Argumentos compartidos H1/H2/H3, sin importar OpenCV ni bibliotecas de IA."""

import argparse

from .config import validate_camera_index


class CameraSelectionCancelled(Exception):
    """Cancelación voluntaria antes de abrir la sesión de procesamiento."""


def _camera_argument(value: str) -> int:
    try:
        index = int(value)
        validate_camera_index(index)
        return index
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--camera requiere un entero entre 0 y 2147483647.") from exc


def parse_camera_args(description: str, argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--camera", type=_camera_argument, metavar="N",
                        help="Índice de cámara para esta ejecución; tiene prioridad sobre camera.json.")
    return parser.parse_args(argv)
