"""Adaptador de un frame MP4 al editor H4 existente. No abre cámara ni ejecuta IA."""

import argparse
import logging
from pathlib import Path

from .config import PROJECT_ROOT
from .video_results import create_run
from .video_source import VideoSource, discover_cases, file_sha256
from .video_zones import export_video_zones
from .zone_calibrator import CalibrationEditor, preview_size, render_editor
from .zones import ZoneError, ZoneStore

LOGGER = logging.getLogger(__name__)
WINDOW = "LimpIA MP4 - A exterior / B puerta"


def reference_frame(video, index):
    if type(index) is not int or index < 0:
        raise ValueError("--frame debe ser un índice no negativo.")
    with VideoSource(video) as source:
        for packet in source:
            if packet.index == index:
                return packet.frame
    raise ValueError("El frame solicitado no se pudo leer en el MP4.")


def edit_frame(cv2, frame, store):
    height, width = frame.shape[:2]
    editor = CalibrationEditor(store, 0, width, height)
    editor.status = "VIDEO: dibuje A exterior y B puerta. S guarda; q/Esc cierra."
    display = preview_size(frame)

    def mouse(event, x, y, flags, parameter):
        actions = {cv2.EVENT_LBUTTONDOWN: "down", cv2.EVENT_LBUTTONUP: "up",
                   cv2.EVENT_MOUSEMOVE: "move", cv2.EVENT_RBUTTONDOWN: "right"}
        if event in actions:
            editor.mouse(actions[event], x, y, *display)

    def open_window():
        cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(WINDOW, mouse)

    try:
        open_window()
        while not editor.exit_requested:
            cv2.imshow(WINDOW, render_editor(cv2, frame, editor))
            editor.key(cv2.waitKey(20) & 0xFF)
            if not editor.exit_requested:
                try:
                    visible = cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE)
                except cv2.error:
                    visible = -1
                if visible < 1:
                    editor.request_exit()
                    if not editor.exit_requested:
                        open_window()
    finally:
        try:
            cv2.destroyAllWindows()
        except cv2.error as exc:
            LOGGER.warning("No se pudieron cerrar las ventanas: %s", exc)
    try:
        return store.load_active()
    except ZoneError as exc:
        raise ValueError("No se guardó un perfil MP4. Use S para guardar A exterior/B puerta antes de cerrar; no se exportó un JSON.") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--output", type=Path, required=True, help="JSON nuevo de zonas del video.")
    parser.add_argument("--frame", type=int, default=0, help="Frame desde cero; se muestra fijo, sin guardar imágenes.")
    parser.add_argument("--reviewer", required=True)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        case = discover_cases(video=args.video)[0]
        if (args.output.exists() or args.output.is_symlink() or not args.output.parent.is_dir()
                or args.output.suffix.lower() != ".json" or not args.reviewer.strip()):
            raise ValueError("La salida debe ser nueva y su directorio debe existir.")
        frame = reference_frame(case.path, args.frame)
        _, workspace = create_run(PROJECT_ROOT / "results_testing" / "calibration")
        import cv2
        profile = edit_frame(cv2, frame, ZoneStore(workspace / "profiles"))
        if file_sha256(case.path) != case.sha256:
            raise ValueError("El MP4 cambió durante la calibración; no se exportan zonas.")
        export_video_zones(args.output, case.path, profile, args.frame, args.reviewer)
        print(f"Perfil MP4 nuevo: {args.output}\nA exterior / B puerta; sin cámara ni inferencia.")
        return 0
    except KeyboardInterrupt:
        LOGGER.info("Calibración interrumpida; no se exportó el perfil final.")
        return 130
    except Exception as exc:
        LOGGER.error("%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
