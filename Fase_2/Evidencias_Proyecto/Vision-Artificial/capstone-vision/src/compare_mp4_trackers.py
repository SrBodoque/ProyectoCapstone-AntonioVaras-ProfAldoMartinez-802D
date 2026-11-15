"""Matriz explícita video/perfil/tracker; sin tuning ni selección de ganador."""

import argparse
import csv
import json
from pathlib import Path
import time

from .config import PROJECT_ROOT
from .count_replay import run_count_replay
from .counting_config import COUNTING_PATH, load_counting_config
from .saved_results import load_case
from .tracker_runtime import resolve_resources
from .video_results import create_run, write_json
from .video_runner import RunOptions, run_cases
from .video_source import VideoSource, discover_cases, file_sha256
from .video_zones import load_video_zones, validate_dimensions

VARIANTS = ("botsort", "botsort_reid")
FIELDS = ("video", "tracker", "status", "frames", "frames_with_tracks", "untracked_detections",
          "frames_with_untracked", "tracking_seconds", "counting_seconds", "total_seconds",
          "processing_fps", "entries", "exits", "events", "tracking_directory", "counting_directory", "error")


def validate_pairs(pairs):
    """Nombres y rutas arbitrarios; verifica todos los pares antes de inferir."""
    checked = []
    for video, profile in pairs:
        row = {"video": str(video), "zones": str(profile)}
        try:
            case = discover_cases(video=video)[0]
            zones = load_video_zones(profile, case.path)
            with VideoSource(case.path) as source:
                validate_dimensions(zones, {"video": source.metadata})
            row.update(case=case, profile=zones, status="valid")
        except (ValueError, OSError, RuntimeError) as exc:
            row.update(status="invalid", error=f"{type(exc).__name__}: {exc}")
        checked.append(row)
    return checked


def write_reports(directory, rows, inputs):
    report = dict(schema_version=1, kind="limpia_explicit_tracker_comparison", inputs=inputs,
                  accuracy_validated=False, winner_selected=False, results=rows)
    write_json(directory / "comparison.json", report)
    with (directory / "comparison.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    def text(value):
        return str(value if value is not None else "pendiente").replace("|", "/").replace("\n", " ")
    lines = ["# Comparación explícita BoT-SORT", "",
             "Condiciones solicitadas: YOLO26n, cuda:0, confianza experimental 0.25.",
             "FPS = frames / tiempo de tracking (incluye carga y E/S); no es precisión ni FPS de cámara.",
             "El tiempo total incluye preflight de variante, tracking y conteo. No se selecciona ganador.", "",
             "| Video | Tracker | Estado | Frames | Con tracks | Sin ID (cajas/frames) | s tracking / total | FPS | IN/OUT/eventos |",
             "|---|---|---|---:|---:|---|---|---:|---|"]
    for row in rows:
        lines.append("| " + " | ".join(map(text, (Path(row["video"]).name, row["tracker"], row["status"],
            row.get("frames"), row.get("frames_with_tracks"),
            f"{row.get('untracked_detections', 'N/D')}/{row.get('frames_with_untracked', 'N/D')}",
            f"{row.get('tracking_seconds', 'N/D')}/{row.get('total_seconds', 'N/D')}",
            row.get("processing_fps"), f"{row.get('entries', 'N/D')}/{row.get('exits', 'N/D')}/{row.get('events', 'N/D')}"))) + " |")
    for row in rows:
        lines.extend(("", f"## {Path(row['video']).name} — {row['tracker']}",
                      f"Estado: {row['status']}. {row.get('error', '')}",
                      f"Zonas: {row['zones']}",
                      f"Tracking: {row.get('tracking_directory', 'no generado')}",
                      f"Conteo/visor: {row.get('counting_directory', 'pendiente')}"))
        if row.get("configuration_effective"):
            lines.extend(("```json", json.dumps(row["configuration_effective"], ensure_ascii=False, indent=2), "```"))
    lines.extend(("", "Los eventos son resultados del contador; no son ground truth.",
                  "Revise visualmente cajas, IDs, zonas y eventos; faltan anotaciones reales para evaluar precisión.",
                  "Use src.view_count_results --video <MP4> --count-results <carpeta de conteo>."))
    (directory / "comparison.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


def run_comparison(pairs, weights_dir, output_root, trackers=VARIANTS, count_config=COUNTING_PATH):
    if not pairs or not trackers or any(t not in VARIANTS for t in trackers):
        raise ValueError("Seleccione pares video/perfil y variantes BoT-SORT explícitas.")
    # Ninguna modificación de detection.json: las condiciones son overrides de sesión.
    checked = validate_pairs(pairs)
    source = {"path": str(Path(count_config).resolve()), "sha256": file_sha256(Path(count_config))}
    settings = load_counting_config(count_config).thresholds
    _, directory = create_run(Path(output_root).resolve() / "comparisons")
    inputs = []
    for item in checked:
        entry = {k:v for k,v in item.items() if k not in ("case", "profile")}
        if item["status"] == "valid":
            entry.update(video_sha256=item["case"].sha256, zones_sha256=item["profile"].file_sha256)
        inputs.append(entry)
    rows = []
    write_reports(directory, rows, inputs)
    interrupted = False
    for item in checked:
        for name in trackers:
            if interrupted:
                break
            row = dict(video=item["video"], zones=item["zones"], tracker=name,
                       model_requested="yolo26n.pt", device_requested="cuda:0", confidence_requested=.25,
                       status="pending", accuracy_validated=False)
            rows.append(row)
            started = time.perf_counter()
            try:
                if item["status"] != "valid":
                    row.update(status="invalid_input", error=item["error"])
                    continue
                try:
                    resolve_resources(name, weights_dir, "yolo26n.pt")
                except RuntimeError as exc:
                    row["error"] = str(exc)
                    continue
                tracking, summary = run_cases([item["case"]],
                    RunOptions("tracking", "cuda:0", name, str(weights_dir), .25), directory / "runs")
                row["tracking_directory"] = str(tracking)
                if summary["status"] != "completed":
                    row.update(status=summary["status"] if summary["results"] or summary["status"] == "interrupted" else "pending", error=summary.get("error") or
                               "; ".join(r.get("error") or r["status"] for r in summary["results"]))
                    interrupted = summary["status"] == "interrupted"
                    continue
                case = load_case(Path(summary["results"][0]["output_directory"]))
                meta = case.metadata
                config = meta["configuration"]
                effective = dict(model=config["model"], device=meta["device_effective"],
                    confidence=config["tracking_confidence_effective"], tracker=config["tracker_name"],
                    backend_class=config["backend_class"], tracker_parameters=config["tracker_parameters"],
                    tracker_yaml_sha256=config["tracker_yaml_sha256"], weights=meta["weights_used"],
                    reid_model=meta.get("reid_model_effective"), versions=config["versions"],
                    detection=meta["effective_detection_config"], config_files=config["config_files"])
                row["configuration_effective"] = effective
                if (effective["model"] != "yolo26n.pt" or effective["device"] != "cuda:0"
                        or effective["confidence"] != .25
                        or effective["tracker_parameters"]["with_reid"] != (name == "botsort_reid")):
                    raise ValueError("Las condiciones efectivas no corresponden a la comparación solicitada.")
                seconds = meta["elapsed_ms"] / 1000
                row.update(frames=meta["frames_processed"], tracking_seconds=seconds,
                    processing_fps=meta["frames_processed"] / seconds if seconds > 0 else None,
                    frames_with_tracks=sum(bool(f.tracks) for f in case.frames.values()),
                    untracked_detections=sum(len(f.untracked) for f in case.frames.values()),
                    frames_with_untracked=sum(bool(f.untracked) for f in case.frames.values()))
                counting_started = time.perf_counter()
                counting, counted = run_count_replay(item["case"].path, item["profile"].path, tracking,
                                                     directory / "runs", settings, source)
                row.update(counting_directory=str(counting), counting_seconds=time.perf_counter()-counting_started,
                           status=counted["status"], entries=counted["entries"], exits=counted["exits"],
                           events=counted["events"])
                if counted.get("error"):
                    row["error"] = counted["error"]
                row["event_records"] = [json.loads(line) for line in (counting/"events.jsonl").read_text(encoding="utf-8").splitlines()]
                interrupted = counted["status"] == "interrupted"
            except KeyboardInterrupt:
                row.update(status="interrupted", error="Interrupción solicitada; no se continúa con inferencia.")
                interrupted = True
            except (ValueError, OSError, RuntimeError, ImportError) as exc:
                row.update(status="failed", error=f"{type(exc).__name__}: {exc}")
            finally:
                row["total_seconds"] = time.perf_counter()-started
                write_reports(directory, rows, inputs)
            if interrupted:
                break
        if interrupted:
            break
    if interrupted:
        plan = [(item, name) for item in checked for name in trackers]
        for item, name in plan[len(rows):]:
            rows.append(dict(video=item["video"], zones=item["zones"], tracker=name, status="pending",
                             accuracy_validated=False, model_requested="yolo26n.pt",
                             device_requested="cuda:0", confidence_requested=.25,
                             error="No ejecutado tras la interrupción de la matriz."))
        write_reports(directory, rows, inputs)
    return directory, rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", nargs=2, action="append", required=True, metavar=("MP4", "ZONES_JSON"))
    parser.add_argument("--tracker", choices=VARIANTS, action="append")
    parser.add_argument("--weights-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT/"results_testing")
    parser.add_argument("--count-config", type=Path, default=COUNTING_PATH)
    args = parser.parse_args(argv)
    directory, rows = run_comparison(args.case, args.weights_dir, args.output,
                                     args.tracker or VARIANTS, args.count_config)
    print(f"Informe nuevo: {directory}")
    for row in rows:
        print(f"{Path(row['video']).name} | {row['tracker']} | {row['status']} | "
              f"IN={row.get('entries', 'pendiente')} OUT={row.get('exits', 'pendiente')} {row.get('error', '')}")
    return 130 if any(r["status"] == "interrupted" for r in rows) else 0 if all(r["status"] == "completed" for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
