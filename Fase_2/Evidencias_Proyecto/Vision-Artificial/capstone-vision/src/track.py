"""Hito 3: python -m src.track. Tracking temporal local con ByteTrack."""

import logging
import os
import sys
import time

from .config import (CameraConfig, DetectionConfig, TrackingConfig, load_config,
                     load_detection_config, load_tracking_config)
from .tracker import FrameTracks, PersonTracker, TrackHistory
from .detect import _label

LOGGER = logging.getLogger(__name__)
WINDOW = "CAPSTONE - ByteTrack - q / ESC para salir"


def draw_tracks(cv2, frame, result: FrameTracks, config: TrackingConfig,
                show_confidence: bool, history: TrackHistory | None) -> None:
    """Dibuja solo observaciones actuales; el historial perdido no es un track activo."""
    height, width = frame.shape[:2]
    def clip(point):
        return (max(0, min(width - 1, round(point[0]))),
                max(0, min(height - 1, round(point[1]))))
    for item in (*result.tracks, *result.untracked_detections):
        track_id = getattr(item, "track_id", None)
        color = (0, 220, 0) if track_id is not None else (0, 180, 255)
        first, last = clip((item.x1, item.y1)), clip((item.x2, item.y2))
        cv2.rectangle(frame, first, last, color, 2)
        prefix = f"ID {track_id} | " if config["show_track_id"] and track_id is not None else ""
        label = prefix + ("person" if track_id is not None else "person | sin ID")
        if show_confidence:
            label += f" | {item.confidence:.2f}"
        _label(cv2, frame, label, (first[0], max(16, first[1] - 6)))
        if history is not None and track_id is not None:
            points = list(history.points.get(track_id, ()))
            for a, b in zip(points, points[1:]):
                cv2.line(frame, clip(a), clip(b), color, 2)


def run_tracking(cv2, camera_config: CameraConfig, detection_config: DetectionConfig,
                 tracking_config: TrackingConfig) -> None:
    """Reutiliza camera_session: libera recursos ante cierre, error o Ctrl+C."""
    from .camera import camera_info, camera_session

    try:
        with camera_session(camera_config) as (capture, frame):
            info = camera_info(capture)
            LOGGER.info("Solicitado: %s", camera_config)
            LOGGER.info("Informado por OpenCV: %s", info)
            tracker = PersonTracker(detection_config, tracking_config)
            history = (TrackHistory(tracking_config["trail_length"], tracker.bytetrack_config["track_buffer"])
                       if tracking_config["show_trail"] else None)
            LOGGER.info("Detección: %s", detection_config)
            LOGGER.info("La primera inferencia incluye inicialización; luego se mide FPS del pipeline.")
            cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
            started = None
            count = 0
            pipeline_fps = None
            while True:
                result = tracker.track(frame)
                if history is not None:
                    history.update(result.tracks)
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
                draw_tracks(cv2, frame, result, tracking_config, detection_config["show_confidence"], history)
                height, width = frame.shape[:2]
                fps_text = f"{pipeline_fps:.1f}" if pipeline_fps is not None else "midiendo"
                inference_text = f"{result.inference_ms:.1f}" if result.inference_ms is not None else "N/D"
                labels = (
                    f"{width}x{height} | cam: {camera_config['camera_index']} | {info['backend']}",
                    f"ByteTrack | Tracks activos: {len(result.tracks)} | {detection_config['model']} | {detection_config['device']}",
                    f"FPS pipeline: {fps_text} | Inferencia YOLO: {inference_text} ms",
                    f"YOLO + tracking: {result.processing_ms:.1f} ms | Cajas sin ID: {len(result.untracked_detections)}",
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
        tracking_config = load_tracking_config()
        if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            raise RuntimeError("No hay sesión gráfica disponible. Ejecuta tracking en tu equipo con escritorio y webcam.")
        run_tracking(cv2, camera_config, detection_config, tracking_config)
    except KeyboardInterrupt:
        LOGGER.info("Cierre solicitado con Ctrl+C.")
    except (ValueError, RuntimeError, cv2.error) as exc:
        LOGGER.error("%s", exc)
        return 1
    LOGGER.info("Tracking finalizado; cámara liberada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
