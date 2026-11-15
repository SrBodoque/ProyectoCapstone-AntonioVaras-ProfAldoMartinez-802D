"""Capas de conteo guardado sobre el reproductor offline existente; sin inferencia."""

import argparse
from bisect import bisect_right
from dataclasses import dataclass
import logging
from pathlib import Path
import textwrap
import unicodedata

from .count_engine import Phase
from .count_replay import validate_case
from .saved_results import ResultsError, number, read_json, select_case
from .video_source import file_sha256
from .video_zones import load_video_zones
from .view_results import play

LOGGER = logging.getLogger(__name__)


def _json(path):
    return read_json(path.read_text(encoding="utf-8-sig"), str(path))


def _rows(path, count):
    rows = []
    with path.open(encoding="utf-8-sig") as stream:
        for line in stream:
            row = read_json(line, str(path))
            if (not isinstance(row, dict) or type(row.get("frame_index")) is not int
                    or not 0 <= row["frame_index"] < count
                    or type(row.get("track_id")) is not int or row["track_id"] <= 0
                    or not number(row.get("timestamp")) or row["timestamp"] < 0
                    or rows and row["frame_index"] < rows[-1]["frame_index"]):
                raise ResultsError("Evento/diagnóstico inválido o fuera de orden.")
            rows.append(row)
    return rows


@dataclass
class CountingView:
    video: Path
    case: object
    zones: object
    events: list
    diagnostics: list
    hashes: dict

    def verify_unchanged(self):
        if any(file_sha256(path) != digest for path, digest in self.hashes.items()):
            raise ResultsError("Un recurso cambió durante la visualización; revise los archivos originales.")


def load_view(video, directory, *, zones_path=None, predictions=None):
    directory = Path(directory).resolve()
    paths = [directory / name for name in ("run.json", "summary.json", "events.jsonl", "diagnostics.jsonl")]
    hashes = {p: file_sha256(p) for p in paths}
    manifest, summary = _json(paths[0]), _json(paths[1])
    if (not isinstance(manifest, dict) or not isinstance(summary, dict)
            or manifest.get("kind") != "limpia_counting_run"
            or summary.get("kind") != "limpia_counting_summary"
            or manifest.get("schema_version") != 1 or summary.get("schema_version") != 1
            or manifest.get("status") != "completed" or summary.get("status") != "completed"
            or not manifest.get("run_id") or manifest["run_id"] != summary.get("run_id")):
        raise ResultsError("Seleccione una ejecución de conteo completa y compatible.")
    video, case = select_case(predictions or manifest.get("predictions_directory", ""), video)
    zones = load_video_zones(zones_path or manifest.get("zones_file", ""), video)
    validate_case(case, zones)
    if (manifest.get("video_sha256") != zones.video_sha256
            or manifest.get("zones_file_sha256") != zones.file_sha256
            or manifest.get("orientation") != {"A": "exterior", "B": "puerta"}
            or summary.get("frames_processed") != len(case.frames)
            or summary.get("expected_frames") != len(case.frames)):
        raise ResultsError("El conteo, las zonas y el tracking no corresponden entre sí.")
    hashes.update({video: zones.video_sha256, zones.path: zones.file_sha256})
    for name in ("metadata.json", "predictions.jsonl"):
        path = case.directory / name
        digest = file_sha256(path)
        if (manifest.get("predictions_hashes") or {}).get(name) != digest:
            raise ResultsError("Las predicciones cambiaron después del conteo.")
        hashes[path] = digest
    events, diagnostics = (_rows(path, len(case.frames)) for path in paths[2:])
    for index, event in enumerate(events, 1):
        direction = event.get("direction")
        expected = ("A", "B") if direction == "IN" else ("B", "A")
        if (direction not in ("IN", "OUT") or event.get("number") != index
                or type(event.get("episode")) is not int or event["episode"] < 1
                or (event.get("origin"), event.get("destination")) != expected):
            raise ResultsError("Evento IN/OUT inválido.")
    for row in diagnostics:
        if (row.get("phase") not in {phase.value for phase in Phase}
                or not isinstance(row.get("reason"), str)
                or row.get("reset_reason") is not None and not isinstance(row["reset_reason"], str)):
            raise ResultsError("Diagnóstico de transición inválido.")
    totals = dict(events=len(events), entries=sum(e["direction"] == "IN" for e in events),
                  exits=sum(e["direction"] == "OUT" for e in events))
    if any(type(summary.get(k)) is not int or summary[k] != v for k, v in totals.items()):
        raise ResultsError("El resumen no coincide con los eventos guardados.")
    view = CountingView(video, case, zones, events, diagnostics, hashes)
    view.verify_unchanged()
    return view


class Annotations:
    """Consulta por índice de frame: redibujar o pausar nunca suma eventos."""

    def __init__(self, view):
        self.view = view
        self.indices = [e["frame_index"] for e in view.events]
        self.entries = [0]
        self.exits = [0]
        for event in view.events:
            self.entries.append(self.entries[-1] + (event["direction"] == "IN"))
            self.exits.append(self.exits[-1] + (event["direction"] == "OUT"))
        self.by_id = {}
        for row in view.diagnostics:
            self.by_id.setdefault(row["track_id"], []).append(row)
        self.frames_by_id = {i: [r["frame_index"] for r in rows] for i, rows in self.by_id.items()}

    def lines(self, saved):
        n = bisect_right(self.indices, saved.index)
        result = [f"IN: {self.entries[n]} | OUT: {self.exits[n]} | A exterior -> B puerta = IN",
                  "Conteo guardado; sin inferencia. Precision e identidades NO certificadas."]
        if n:
            e = self.view.events[n-1]
            result.append(f"Ultimo evento: {e['direction']} ID {e['track_id']} | frame {e['frame_index']+1} | t={e['timestamp']:.3f}s")
        rows = []
        visible = {o.track_id for o in saved.tracks}
        for identifier, history in self.by_id.items():
            j = bisect_right(self.frames_by_id[identifier], saved.index)
            if j:
                row = history[j-1]
                if identifier in visible or row["phase"] == Phase.MISSING.value:
                    rows.append(row)
        rows.sort(key=lambda r: (r["track_id"] not in visible, -r["frame_index"], r["track_id"]))
        for row in rows[:4]:
            reason = row["reason"].replace("_", " ")
            if row.get("reset_reason"):
                reason += "; reinicio: " + row["reset_reason"].replace("_", " ")
            result.append(f"ID {row['track_id']} {row['phase']} (actualizado frame {row['frame_index']+1}): {reason}")
        if len(rows) > 4:
            result.append(f"Mostrando 4/{len(rows)} diagnosticos; todos en diagnostics.jsonl.")
        return result


def render_count_overlay(cv2, frame, saved, annotations):
    """Recibe la copia con cajas/IDs/trayectorias dibujada por el reproductor."""
    height, width = frame.shape[:2]
    output = cv2.copyMakeBorder(frame, 0, 0, 0, max(0, 960-width), cv2.BORDER_CONSTANT, value=(24,24,24))
    profile = annotations.view.zones.profile
    for label, polygon, color in (("A exterior", profile.a, (0,220,255)), ("B puerta", profile.b, (255,180,0))):
        points = [(round(x*(width-1)), round(y*(height-1))) for x, y in polygon]
        for first, last in zip(points, points[1:]+points[:1]):
            cv2.line(output, first, last, color, 2)
        cv2.putText(output, label, points[0], cv2.FONT_HERSHEY_SIMPLEX, .55, color, 2, cv2.LINE_AA)
    lines = []
    for line in annotations.lines(saved):
        ascii_text = unicodedata.normalize("NFKD", line).encode("ascii", "replace").decode()
        lines.extend(textwrap.wrap(ascii_text, width=max(40, (output.shape[1]-20)//8)))
    output = cv2.copyMakeBorder(output, 0, 24*len(lines)+12, 0, 0, cv2.BORDER_CONSTANT, value=(24,24,24))
    for i, line in enumerate(lines):
        cv2.putText(output, line, (8,height+24*(i+1)), cv2.FONT_HERSHEY_SIMPLEX, .45, (255,255,255), 1, cv2.LINE_AA)
    return output


def play_count(cv2, view, **kwargs):
    annotations = Annotations(view)

    class CaseAdapter:
        current = None

        def __getattr__(self, name):
            return getattr(view.case, name)

        def frame(self, index):
            self.current = view.case.frame(index)
            return self.current

    case = CaseAdapter()

    class DisplayAdapter:
        def __getattr__(self, name):
            return getattr(cv2, name)

        def imshow(self, window, frame):
            cv2.imshow(window, render_count_overlay(cv2, frame, case.current, annotations))

    try:
        return play(DisplayAdapter(), view.video, case, **kwargs)
    finally:
        view.verify_unchanged()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--count-results", required=True, help="Carpeta concreta de conteo completo.")
    parser.add_argument("--zones", help="Ruta alternativa al mismo JSON, con hash idéntico.")
    parser.add_argument("--predictions", help="Ruta alternativa al mismo tracking guardado.")
    parser.add_argument("--trail-frames", type=int, default=30)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        view = load_view(args.video, args.count_results, zones_path=args.zones, predictions=args.predictions)
        import cv2
        count = play_count(cv2, view, trail_frames=args.trail_frames)
        LOGGER.info("%s frames visualizados; no certifica precisión del conteo ni identidades.", count)
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        LOGGER.error("No se pudo visualizar el conteo: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
