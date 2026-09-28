"""Preview Hito 1: primera cámara funcional; --camera N fuerza un índice."""

import logging
import os
import sys
import time

from .camera_cli import CameraSelectionCancelled, parse_camera_args

from .config import CameraConfig, load_config, validate_camera_index

LOGGER = logging.getLogger(__name__)
WINDOW = "CAPSTONE - Webcam - q / ESC para salir"


def direct_camera_config(config: CameraConfig, camera_override: int | None = None) -> CameraConfig:
    """Prepara el índice ya elegido para el preview compartido, sin descubrir cámaras."""
    index = validate_camera_index(config["camera_index"] if camera_override is None else camera_override)
    if index == "auto":
        raise ValueError("El preview compartido requiere un índice resuelto antes de abrir la cámara.")
    return {**config, "camera_index": index}


def run_preview(cv2, config: CameraConfig, camera_override: int | None = None) -> None:
    """Muestra frames en memoria y libera cámara/ventanas al terminar."""
    from .camera import camera_info, camera_session

    try:
        config = direct_camera_config(config, camera_override)
        with camera_session(config) as (capture, frame):
            info = camera_info(capture)
            LOGGER.info("Solicitado: %s", config)
            LOGGER.info("Informado por OpenCV: %s", info)
            cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
            started = time.perf_counter()
            count = 0
            measured_fps = 0.0
            while True:
                height, width = frame.shape[:2]
                count += 1
                now = time.perf_counter()
                elapsed = now - started
                if elapsed >= 1.0:
                    measured_fps = count / elapsed
                    count = 0
                    started = now
                label = (f"{width}x{height} | FPS aprox: {measured_fps:.1f} | "
                         f"cam: {config['camera_index']} | {info['backend']}")
                cv2.putText(frame, label, (10, 28), cv2.FONT_HERSHEY_SIMPLEX,
                            0.55, (0, 0, 0), 3, cv2.LINE_AA)
                cv2.putText(frame, label, (10, 28), cv2.FONT_HERSHEY_SIMPLEX,
                            0.55, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.imshow(WINDOW, frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    break
                ok, frame = capture.read()
                if not ok or frame is None or frame.size == 0:
                    raise RuntimeError("La webcam dejó de entregar frames. Revisa la conexión y vuelve a ejecutar.")
    finally:
        try:
            cv2.destroyAllWindows()
        except cv2.error as exc:
            LOGGER.warning("No se pudieron destruir las ventanas de OpenCV: %s", exc)


def main(argv: list[str] | None = None) -> int:
    args = parse_camera_args(__doc__, argv)
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
        if args.camera is None:
            from .camera import find_first_available_camera
            candidate = find_first_available_camera(config)
            config = {**config, "camera_index": candidate.index}
            LOGGER.info("Primera cámara funcional: índice %s. Abriendo preview...", candidate.index)
        run_preview(cv2, config, args.camera)
    except CameraSelectionCancelled:
        LOGGER.info("Selección de cámara cancelada; recursos liberados.")
        return 0
    except KeyboardInterrupt:
        LOGGER.info("Cierre solicitado con Ctrl+C.")
    except (ValueError, RuntimeError, cv2.error) as exc:
        LOGGER.error("%s", exc)
        return 1
    LOGGER.info("Vista previa finalizada; cámara liberada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
