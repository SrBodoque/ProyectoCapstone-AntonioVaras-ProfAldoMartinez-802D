"""Hito 4: BoT-SORT existente + zonas activas; sin conteo ni recuperación de identidad."""

import logging
import os
import sys
import time

from .config import load_config, load_detection_config, load_tracking_config
from .detect import _label
from .track import draw_tracks
from .track_botsort_reid import BOTSORT_CONFIG
from .tracker import PersonTracker, TrackHistory
from .zones import ZoneStore, ZoneObservations, bottom_center, draw_regions

LOGGER = logging.getLogger(__name__)
WINDOW = "CAPSTONE - BoT-SORT + ReID + Zonas - q / ESC"


def draw_positions(cv2, frame, result, profile, observations):
    height, width = frame.shape[:2]
    classified = [(item, bottom_center(item), profile.classify(bottom_center(item), width, height))
                  for item in (*result.tracks, *result.untracked_detections)]
    transitions = observations.update((item.track_id, zone) for item, _, zone in classified if hasattr(item, "track_id"))
    for item, point, zone in classified:
        x, y = max(0, min(width - 1, round(point[0]))), max(0, min(height - 1, round(point[1])))
        cv2.circle(frame, (x, y), 5, (255, 255, 255), -1)
        identifier = getattr(item, "track_id", None)
        prefix = f"ID {identifier}" if identifier is not None else "Sin ID"
        label = f"{prefix} | {'ZONA ' + zone if zone != 'FUERA' else zone}"
        recent = transitions.get(identifier)
        if recent: label += f" | obs: {recent}"
        _label(cv2, frame, label, (min(x + 8, max(0, width - 240)), max(16, min(height - 6, y + 20))))


def run_zones(cv2, camera_config, detection_config, tracking_config, profile):
    from .camera import camera_info, camera_session
    try:
        with camera_session(camera_config) as (capture, frame):
            h, w = frame.shape[:2]
            profile.check_camera(camera_config["camera_index"], w, h)
            info = camera_info(capture)
            # Misma clase y YAML actual: no overrides ni cambios de parámetros/dispositivo.
            engine = PersonTracker(detection_config, tracking_config)
            history = (TrackHistory(tracking_config["trail_length"], engine.bytetrack_config["track_buffer"])
                       if tracking_config["show_trail"] else None)
            observations = ZoneObservations()
            LOGGER.info("Zonas activas: %s | cámara: %s | dispositivo efectivo: %s", profile.name,
                        camera_config["camera_index"], engine.config["device"])
            LOGGER.info("El índice no certifica identidad física; recalibre si movió la cámara o cambió su perspectiva.")
            cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
            started, count, fps = None, 0, None
            while True:
                h, w = frame.shape[:2]
                profile.check_camera(camera_config["camera_index"], w, h)
                result = engine.track(frame)  # Inferencia siempre antes de pintar sobre el frame.
                if history is not None: history.update(result.tracks)
                now = time.perf_counter()
                if started is None: started = now
                else:
                    count += 1
                    if now - started >= 1:
                        fps, count, started = count / (now - started), 0, now
                draw_regions(cv2, frame, {"A": profile.a, "B": profile.b})
                draw_tracks(cv2, frame, result, tracking_config, detection_config["show_confidence"], history)
                draw_positions(cv2, frame, result, profile, observations)
                fps_text = f"{fps:.1f}" if fps is not None else "midiendo"
                inference = f"{result.inference_ms:.1f}" if result.inference_ms is not None else "N/D"
                labels = (f"{w}x{h} | cam: {camera_config['camera_index']} | {info['backend']} | perfil: {profile.name}",
                          f"BoT-SORT + ReID + Zonas | Tracks activos: {len(result.tracks)} | {engine.config['device']}",
                          f"FPS pipeline: {fps_text} | Inferencia YOLO: {inference} ms",
                          f"YOLO + tracking: {result.processing_ms:.1f} ms | Cajas sin ID: {len(result.untracked_detections)}",
                          "Zonas y transiciones observadas; sin conteo IN/OUT")
                for i, label in enumerate(labels): _label(cv2, frame, label, (10, 24 + i * 24))
                cv2.imshow(WINDOW, frame)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27): break
                try:
                    if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1: break
                except cv2.error:
                    break  # Ventana ya destruida al cerrar con X.
                ok, frame = capture.read()
                if not ok or frame is None or frame.size == 0:
                    raise RuntimeError("La webcam dejó de entregar frames. Revise la conexión.")
    finally:
        try: cv2.destroyAllWindows()
        except cv2.error as exc: LOGGER.warning("No se pudieron cerrar las ventanas: %s", exc)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        # Ausencia/corrupción de perfil se informa antes de abrir cámara o cargar IA.
        profile = ZoneStore().load_active()
        camera_config, detection_config = load_config(), load_detection_config()
        tracking_config = {**load_tracking_config(), "tracker_config": BOTSORT_CONFIG}
        import cv2
    except (ValueError, OSError, ImportError) as exc:
        LOGGER.error("%s", exc); return 1
    try:
        if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            raise RuntimeError("Ejecute track_zones en un escritorio con webcam y OpenCV gráfico.")
        run_zones(cv2, camera_config, detection_config, tracking_config, profile)
    except KeyboardInterrupt:
        LOGGER.info("Cierre solicitado con Ctrl+C.")
    except (ValueError, RuntimeError, OSError, cv2.error) as exc:
        LOGGER.error("%s", exc); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
