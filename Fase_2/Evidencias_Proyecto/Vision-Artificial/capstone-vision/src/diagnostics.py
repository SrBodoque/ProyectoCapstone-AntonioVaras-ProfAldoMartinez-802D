"""Diagnóstico sin ventanas; --scan prueba índices 0 a 4 secuencialmente."""

import argparse
import logging
import platform
import struct
import sys
from importlib.metadata import version
from pathlib import Path

from .config import CONFIG_PATH, PROJECT_ROOT, load_config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", action="store_true", help="Probar cámaras 0 a 4 (puede tardar).")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print(f"Python: {platform.python_version()} (objetivo: 3.13.15)", flush=True)
    print(f"Sistema: {platform.platform()}")
    print(f"Arquitectura intérprete: {struct.calcsize('P') * 8} bits; CPU: {platform.machine()}")
    print(f"Intérprete: {sys.executable}")
    print(f"Entorno virtual: {sys.prefix != sys.base_prefix}")
    print(f"Directorio actual: {Path.cwd()}")
    print(f"Proyecto: {PROJECT_ROOT}")
    print(f"Configuración: {CONFIG_PATH}")
    try:
        config = load_config()
        print(f"Cámara configurada: {config}", flush=True)
        import cv2
        from .camera import backend_candidates, camera_info, camera_session
        print(f"OpenCV (cv2): {cv2.__version__}")
        print(f"Distribución opencv-python: {version('opencv-python')}")
        if platform.python_version() != "3.13.15" or struct.calcsize('P') * 8 != 64:
            print("AVISO: este intérprete no coincide con Python 3.13.15 x64 objetivo.")
        if version("opencv-python") != "4.14.0.94":
            print("AVISO: opencv-python no coincide con requirements.txt.")
        backend_candidates(config["backend"])
        if args.scan:
            found = []
            for index in range(5):
                try:
                    with camera_session({**config, "camera_index": index}) as (capture, frame):
                        print(f"Índice {index}: DISPONIBLE; frame {frame.shape[1]}x{frame.shape[0]}; {camera_info(capture)}", flush=True)
                        found.append(index)
                except (RuntimeError, cv2.error) as exc:
                    print(f"Índice {index}: no disponible. {exc}", flush=True)
            print(f"Índices que entregaron frames: {found}")
            if not found:
                print("No se encontró webcam. En un entorno sin hardware es esperable; validar en el equipo del usuario.")
        else:
            print("Sin acceso a cámara. Usa python -m src.diagnostics --scan para probar índices 0 a 4.")
    except (ImportError, ValueError, RuntimeError) as exc:
        logging.error("Diagnóstico incompleto: %s. Revisa .venv, requirements.txt y config/camera.json.", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
