"""Hito 5.1: python -m src.track_count. Contador de entradas local por sesión."""

import logging
import os
import sys
import textwrap
import time
import unicodedata

from .config import load_config, load_detection_config
from .count_engine import EntryCounter, Observation
from .counting_config import load_counting_config, select_tracker
from .detect import _label
from .track import draw_tracks
from .track_zones import draw_positions
from .tracker import PersonTracker, TrackHistory
from .zones import ZoneStore, ZoneObservations, bottom_center, draw_regions

LOGGER = logging.getLogger(__name__)
WINDOW = "HIGIENESMART - CONTEO DE ENTRADAS - q / ESC"


def frame_observations(tracks, width, height):
    """Adaptador de las cajas comunes; la FSM no conoce PersonTracker."""
    result = []
    for track in tracks:
        x, y = bottom_center(track)
        result.append(Observation(track.track_id, (x / width, y / height)))
    return tuple(result)


def run_count(cv2, camera_config, detection_config, selection, counter, *, clock=None):
    from .camera import camera_info, camera_session
    clock = time.monotonic if clock is None else clock
    profile = counter.geometry.profile
    tracking_config = selection.tracking_config
    try:
        with camera_session(camera_config) as (capture, frame):
            h, w = frame.shape[:2]
            profile.check_camera(camera_config["camera_index"], w, h)
            info = camera_info(capture)
            tracker = PersonTracker(detection_config, tracking_config, **selection.constructor_options())
            history = (TrackHistory(tracking_config["trail_length"], tracker.bytetrack_config["track_buffer"])
                       if tracking_config["show_trail"] else None)
            visual_observations = ZoneObservations()
            LOGGER.info("Conteo: %s | perfil: %s | cámara: %s | dispositivo efectivo: %s",
                        selection.label, profile.name, camera_config["camera_index"], tracker.config["device"])
            LOGGER.warning("H5.1 interpreta A como exterior y B como zona cercana al baño. Revise físicamente esa orientación; no se cambia el perfil.")
            cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
            fps_start, frames, fps = None, 0, None
            diagnostic = None
            while True:
                h, w = frame.shape[:2]
                profile.check_camera(camera_config["camera_index"], w, h)
                # Inferencia única sobre imagen sin superposiciones.
                result = tracker.track(frame)
                now = clock()
                previous = {identifier: (state.phase, state.reason, state.episode)
                            for identifier, state in counter.states.items()}
                counter.update(now, frame_observations(result.tracks, w, h))
                # Mostrar el motivo que ya decidió la FSM, sin alterar sus reglas.
                # Incluye cancelaciones por pérdida aunque no haya una caja visible.
                for identifier, state in counter.states.items():
                    if previous.get(identifier) != (state.phase, state.reason, state.episode):
                        LOGGER.info("Conteo | ID %s | episodio %s | zona %s | %s | %s",
                                    identifier, state.episode, state.zone,
                                    state.phase.value, state.reason)
                        diagnostic = f"Ultimo cambio ID {identifier}: {state.phase.value} | {state.reason}"
                if history is not None: history.update(result.tracks)
                if fps_start is None: fps_start = now
                else:
                    frames += 1
                    if now - fps_start >= 1:
                        fps, frames, fps_start = frames / (now - fps_start), 0, now
                draw_regions(cv2, frame, {"A": profile.a, "B": profile.b})
                draw_tracks(cv2, frame, result, tracking_config, detection_config["show_confidence"], history)
                draw_positions(cv2, frame, result, profile, visual_observations)
                for item in result.tracks:
                    state = counter.states[item.track_id]
                    x, y = bottom_center(item)
                    _label(cv2, frame, state.phase.value,
                           (max(0, min(w - 240, round(x))), max(18, min(h - 8, round(y) + 42))))
                fps_text = f"{fps:.1f}" if fps is not None else "midiendo"
                inference = f"{result.inference_ms:.1f}" if result.inference_ms is not None else "N/D"
                labels = (
                    "HIGIENESMART - CONTEO DE ENTRADAS",
                    f"ENTRADAS AL BANO: {counter.total_entries}",  # Hershey no representa Ñ.
                    f"Tracker: {selection.label} | {tracker.config['device']} | conf: {tracker.tracking_confidence:.2f}",
                    f"Cam: {camera_config['camera_index']} | {w}x{h} | {info['backend']} | perfil: {profile.name}",
                    f"FPS: {fps_text} | YOLO: {inference} ms | YOLO + tracking: {result.processing_ms:.1f} ms",
                    f"A: exterior -> B: bano | tracks: {len(result.tracks)} | sin ID: {len(result.untracked_detections)}",
                )
                for i, label in enumerate(labels): _label(cv2, frame, label, (10, 26 + i * 25))
                if diagnostic is not None:
                    # Hershey no representa tildes; la consola conserva el texto completo.
                    display = unicodedata.normalize("NFKD", diagnostic).encode("ascii", "ignore").decode("ascii")
                    for i, line in enumerate(textwrap.wrap(display, width=max(12, (w - 20) // 10))):
                        y = 26 + (len(labels) + i) * 25
                        if y > h - 8: break
                        _label(cv2, frame, line, (10, y))
                cv2.imshow(WINDOW, frame)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27): break
                try:
                    if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1: break
                except cv2.error:
                    break
                ok, frame = capture.read()
                if not ok or frame is None or frame.size == 0:
                    raise RuntimeError("La cámara dejó de entregar frames. Conteo finalizado sin persistir resultados.")
    finally:
        try: cv2.destroyAllWindows()
        except cv2.error as exc: LOGGER.warning("No se pudieron cerrar las ventanas: %s", exc)
    return counter.total_entries


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        profile = ZoneStore().load_active()
        config = load_counting_config()
        counter = EntryCounter(profile, config.thresholds)
        selection = select_tracker(config.tracker)
        camera_config, detection_config = load_config(), load_detection_config()
        import cv2
    except (ValueError, OSError, ImportError) as exc:
        LOGGER.error("%s", exc)
        return 1
    try:
        if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            raise RuntimeError("Ejecute track_count en un escritorio con webcam y OpenCV gráfico.")
        run_count(cv2, camera_config, detection_config, selection, counter)
    except KeyboardInterrupt:
        LOGGER.info("Cierre solicitado con Ctrl+C. Total de la sesión: %s", counter.total_entries)
    except (ValueError, RuntimeError, OSError, cv2.error) as exc:
        LOGGER.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
