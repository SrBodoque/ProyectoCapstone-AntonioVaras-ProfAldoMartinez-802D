"""Hito 2: python -m src.detect. Detección en memoria sobre la webcam existente."""

import logging
import os
import sys
import time

from .config import CameraConfig, DetectionConfig, load_config, load_detection_config
from .detector import FrameDetections, PersonDetector

LOGGER = logging.getLogger(__name__)
WINDOW = "CAPSTONE - Personas - q / ESC para salir"


def draw_detections(cv2, frame, result: FrameDetections, show_confidence: bool) -> None:
    """Anota exclusivamente el frame actual sin escribir archivos."""
    height, width = frame.shape[:2]
    for detection in result.detections:
        x1 = max(0, min(width - 1, round(detection.x1)))
        y1 = max(0, min(height - 1, round(detection.y1)))
        x2 = max(0, min(width - 1, round(detection.x2)))
        y2 = max(0, min(height - 1, round(detection.y2)))
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 0), 2)
        label = f"person {detection.confidence:.2f}" if show_confidence else "person"
        _label(cv2, frame, label, (x1, max(16, y1 - 6)))


def _label(cv2, frame, text: str, position: tuple[int, int]) -> None:
    cv2.putText(frame, text, position, cv2.FONT_HERSHEY_SIMPLEX,
                0.5, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(frame, text, position, cv2.FONT_HERSHEY_SIMPLEX,
                0.5, (255, 255, 255), 1, cv2.LINE_AA)


def run_detection(cv2, camera_config: CameraConfig, detection_config: DetectionConfig) -> None:
    """Reutiliza camera_session: libera recursos ante cierre, error o Ctrl+C."""
    from .camera import camera_info, camera_session

    try:
        with camera_session(camera_config) as (capture, frame):
            info = camera_info(capture)
            LOGGER.info("Solicitado: %s", camera_config)
            LOGGER.info("Informado por OpenCV: %s", info)
            detector = PersonDetector(detection_config)
            LOGGER.info("Detección: %s", detection_config)
            LOGGER.info("La primera inferencia incluye inicialización; luego se mide FPS del pipeline.")
            cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
            started = None
            count = 0
            pipeline_fps = None
            while True:
                result = detector.detect(frame)
                now = time.perf_counter()
                if started is None:
                    LOGGER.info("Primera inferencia lista; procesamiento inicial: %.1f ms.", result.processing_ms)
                    started = now
                else:
                    count += 1
                    elapsed = now - started
                    if elapsed >= 1.0:
                        pipeline_fps = count / elapsed
                        count = 0
                        started = now
                draw_detections(cv2, frame, result, detection_config["show_confidence"])
                height, width = frame.shape[:2]
                fps_text = f"{pipeline_fps:.1f}" if pipeline_fps is not None else "midiendo"
                inference_text = f"{result.inference_ms:.1f}" if result.inference_ms is not None else "N/D"
                labels = (
                    f"{width}x{height} | cam: {camera_config['camera_index']} | {info['backend']}",
                    f"Personas/frame: {len(result.detections)} | {detection_config['model']} | {detection_config['device']}",
                    f"FPS pipeline: {fps_text} | Inferencia: {inference_text} ms",
                )
                for i, label in enumerate(labels):
                    _label(cv2, frame, label, (10, 24 + i * 24))
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


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        import cv2
    except ImportError as exc:
        LOGGER.error("No se pudo importar OpenCV: %s. Activa .venv y ejecuta python -m pip install -r requirements.txt", exc)
        return 1
    try:
        camera_config = load_config()
        detection_config = load_detection_config()
        if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            raise RuntimeError("No hay sesión gráfica disponible. Ejecuta detección en tu equipo con escritorio y webcam.")
        run_detection(cv2, camera_config, detection_config)
    except KeyboardInterrupt:
        LOGGER.info("Cierre solicitado con Ctrl+C.")
    except (ValueError, RuntimeError, cv2.error) as exc:
        LOGGER.error("%s", exc)
        return 1
    LOGGER.info("Detección finalizada; cámara liberada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
