"""Diagnóstico sin ventanas; --scan prueba índices 0 a 4 secuencialmente."""

import argparse
import logging
import platform
import struct
import sys
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .config import CONFIG_PATH, DETECTION_CONFIG_PATH, PROJECT_ROOT, load_config, load_detection_config
from .config import (TRACKING_CONFIG_PATH, load_tracking_config,
                     resolve_tracker_path, load_bytetrack_config)


def report_tracking() -> bool:
    """Valida ByteTrack sin abrir cámara, instanciar YOLO ni descargar pesos."""
    complete = True
    print("Tracker: ByteTrack")
    print(f"Configuración de tracking: {TRACKING_CONFIG_PATH}")
    try:
        config = load_tracking_config()
        path = resolve_tracker_path(config["tracker_config"])
        params = load_bytetrack_config(path)
        print(f"Tracking configurado: {config}")
        print(f"YAML ByteTrack: {path}")
        for key, value in params.items():
            print(f"  {key}: {value}")
        detection = load_detection_config()
        if detection["confidence_threshold"] >= params["track_high_thresh"]:
            print("AVISO: confidence_threshold filtra antes de ByteTrack; el baseline actual "
                  "no alimenta la segunda asociación de baja confianza.")
    except ValueError as exc:
        print(f"ERROR de configuración de tracking: {exc}")
        complete = False
    try:
        installed = version("lap")
        print(f"Distribución lap: {installed} (objetivo: 0.5.12)")
        if installed != "0.5.12":
            print("AVISO: lap no coincide con requirements.txt.")
            complete = False
        from .detector import _load_yolo
        _load_yolo()  # Configura privacidad antes de importar el tracker integrado.
        import_module("ultralytics.trackers.byte_tracker")
        print("Import ByteTrack integrado: OK (sin modelo ni pesos).")
    except PackageNotFoundError:
        print("FALTA lap. Ejecuta python -m pip install -r requirements.txt.")
        complete = False
    except Exception as exc:
        print(f"ERROR al cargar ByteTrack/lap: {exc}. "
              "Ejecuta python -m pip install -r requirements.txt y python -m pip check.")
        complete = False
    return complete


def report_detection() -> bool:
    """Sin pesos ni inferencia. Un fallo de IA no impide el escaneo de webcam."""
    complete = True
    print(f"Configuración de detección: {DETECTION_CONFIG_PATH}")
    try:
        config = load_detection_config()
        print(f"Detección configurada: {config}")
        print(f"Dispositivo Hito 2: {config['device']}; modelo: {config['model']}")
    except ValueError as exc:
        print(f"ERROR de configuración de detección: {exc}")
        complete = False
    for package, expected in (("ultralytics", "8.4.163"), ("torch", "2.14.0"), ("torchvision", "0.29.0")):
        try:
            installed = version(package)
            print(f"Distribución {package}: {installed} (objetivo: {expected})")
            if installed.split("+")[0] != expected:
                print(f"AVISO: {package} no coincide con requirements.txt.")
                complete = False
            if package == "ultralytics":
                from .detector import _load_yolo
                _load_yolo()  # Importa con telemetría desactivada; NO instancia YOLO.
            module = import_module(package)
            print(f"{package} cargado: {module.__version__}")
            if package == "torch":
                print(f"CUDA disponible: {module.cuda.is_available()} (detección usa cpu).")
        except PackageNotFoundError:
            print(f"FALTA {package}. Activa .venv y ejecuta python -m pip install -r requirements.txt.")
            complete = False
        except Exception as exc:
            print(f"ERROR al cargar {package}: {exc}. Revisa .venv, requirements.txt y python -m pip check.")
            complete = False
    return complete


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
        ai_complete = report_detection()
        tracking_complete = report_tracking()
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
    return 0 if ai_complete and tracking_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
