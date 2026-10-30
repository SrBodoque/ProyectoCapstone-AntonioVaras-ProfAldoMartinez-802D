"""Reproductor MP4 + predicciones existentes. No importa ni ejecuta IA."""

import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass

from .result_overlay import TrailHistory, render_frame
from .saved_results import ResultsError, select_case, validate_video
from .video_source import VideoSource

LOGGER = logging.getLogger(__name__)
WINDOW = "LimpIA - resultados offline"


@dataclass
class PlaybackControls:
    paused: bool = False

    def handle(self, key):
        if key in (ord("q"), 27):
            return "quit"
        if key == ord(" "):
            self.paused = not self.paused
            return "redraw"
        if self.paused and key in (ord("n"), ord(".")):
            return "next"
        return "wait"


def play(cv2, video, case, *, trail_frames=30, clock=time.monotonic):
    history = TrailHistory(trail_frames)
    controls = PlaybackControls()
    decoded = 0
    missing = 0
    try:
        with VideoSource(video) as source:
            fps = validate_video(case, source.metadata)
            period = 1 / fps
            for message in case.notices.messages:
                LOGGER.warning("%s", message)
            cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
            for packet in source:
                decoded += 1
                expected = case.metadata.get("video", {})
                height, width = packet.frame.shape[:2]
                if expected.get("width") not in (None, width) or expected.get("height") not in (None, height):
                    raise ResultsError("El tamaño decodificado no coincide con las coordenadas guardadas.")
                saved = case.frame(packet.index)
                missing += not saved.available
                history.update(saved)
                deadline = clock() + period
                dirty = True
                while True:
                    if dirty:
                        shown = render_frame(cv2, packet.frame, saved, history,
                            total=source.metadata.get("reported_frames"),
                            timestamp_ms=packet.timestamp_ms, paused=controls.paused)
                        cv2.imshow(WINDOW, shown)
                        dirty = False
                    remaining = max(0.0, deadline - clock())
                    delay = 20 if controls.paused else max(1, min(20, round(remaining * 1000)))
                    key = cv2.waitKey(delay) & 0xFF
                    action = controls.handle(key)
                    if action == "quit" or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                        return decoded
                    if action == "redraw":
                        deadline = clock() + period
                        dirty = True
                    elif action == "next":
                        break
                    elif not controls.paused and clock() >= deadline:
                        break
            if source.status != "completed":
                raise ResultsError(f"Lectura del MP4 {source.status}: {source.reason}")
            if decoded == 0:
                raise ResultsError("El MP4 no entregó frames.")
            return decoded
    finally:
        if missing:
            LOGGER.warning("%s frames mostrados no tienen predicciones registradas; no se reutilizaron cajas.", missing)
        try:
            cv2.destroyWindow(WINDOW)
        except cv2.error:
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="Visualiza un MP4 y resultados guardados, sin inferencia.")
    parser.add_argument("--video", required=True, help="MP4 local original o copia idéntica.")
    parser.add_argument("--results", required=True, help="Carpeta de un caso (metadata/JSONL) o de un lote concreto.")
    parser.add_argument("--trail-frames", type=int, default=30, help="Historial visual de 1 a 300 frames; predeterminado 30.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        TrailHistory(args.trail_frames)
        video, case = select_case(args.results, args.video)
        if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            raise ResultsError("No hay sesión gráfica. Ejecuta el visualizador en un escritorio local.")
        import cv2
        count = play(cv2, video, case, trail_frames=args.trail_frames)
        LOGGER.info("Visualización finalizada: %s frames leídos; sin inferencia ni cambios en resultados.", count)
        return 0
    except KeyboardInterrupt:
        LOGGER.info("Visualización interrumpida; recursos liberados.")
        return 130
    except Exception as exc:
        LOGGER.error("No se pudo visualizar: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
