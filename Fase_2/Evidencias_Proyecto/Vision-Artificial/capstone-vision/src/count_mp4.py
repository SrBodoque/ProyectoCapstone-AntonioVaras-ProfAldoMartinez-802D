"""H5.2: tracking MP4 seleccionable y conteo reproducible de predicciones."""

import argparse
import logging
from pathlib import Path

from .config import PROJECT_ROOT
from .count_replay import run_count_replay
from .counting_config import COUNTING_PATH, load_counting_config
from .video_source import discover_cases, file_sha256
from .video_zones import load_video_zones

LOGGER = logging.getLogger(__name__)
TRACKERS = ("bytetrack", "fasttrack", "fasttracker", "botsort", "botsort_reid", "recovery")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("track", "count", "process"):
        sub = commands.add_parser(name)
        sub.add_argument("--video", required=True, help="MP4 local; no se modifica.")
        sub.add_argument("--output", type=Path, default=PROJECT_ROOT / "results_testing")
        if name != "count":
            sub.add_argument("--tracker", choices=TRACKERS, default="bytetrack")
            sub.add_argument("--device", required=True, help="cpu o cuda:N, sin fallback.")
            sub.add_argument("--confidence", type=float, help="Override experimental explícito solo para BoT-SORT; no modifica detection.json.")
            sub.add_argument("--weights-dir", type=Path, default=PROJECT_ROOT,
                             help="Directorio local de pesos, también externo al worktree; solo lectura.")
        if name != "track":
            sub.add_argument("--zones", type=Path, required=True, help="JSON de zonas vinculado a este MP4.")
            sub.add_argument("--count-config", type=Path, default=COUNTING_PATH,
                             help="Se usan solo sus umbrales; el tracker se elige por CLI o por las predicciones.")
        if name == "count":
            sub.add_argument("--predictions", type=Path, required=True, help="Caso o lote concreto ya procesado.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        cases = discover_cases(video=args.video)
        video = cases[0].path
        settings = None
        settings_source = None
        if args.command != "track":
            load_video_zones(args.zones, video)  # Validar antes de gastar inferencia.
            settings_source = {"path": str(args.count_config.resolve()), "sha256": file_sha256(args.count_config)}
            settings = load_counting_config(args.count_config).thresholds
        if args.command != "count":
            from .video_runner import RunOptions, run_cases
            from .processing_report import print_processing_report
            options = RunOptions("tracking", args.device, args.tracker, str(args.weights_dir), args.confidence)
            directory, summary = run_cases(cases, options, args.output.resolve())
            print_processing_report(directory, summary)
            if summary["status"] != "completed":
                return 130 if summary["status"] == "interrupted" else 1
            if args.command == "track":
                print("Tracking guardado. Conteo pendiente hasta seleccionar un JSON de zonas.")
                return 0
            predictions = directory
        else:
            predictions = args.predictions
        directory, summary = run_count_replay(video, args.zones, predictions, args.output, settings, settings_source)
        print(f"Conteo: {summary['status']} | frames: {summary['frames_processed']}/{summary['expected_frames']}\n"
              f"IN: {summary['entries']} | OUT: {summary['exits']} | eventos: {summary['events']}\n"
              f"Resultados nuevos: {directory}\nSin repetir inferencia en la fase de conteo. No certifica precisión física.")
        if summary.get("error"):
            LOGGER.error("%s", summary["error"])
        return 0 if summary["status"] == "completed" else 130 if summary["status"] == "interrupted" else 1
    except KeyboardInterrupt:
        return 130
    except (ValueError, OSError, RuntimeError, ImportError) as exc:
        LOGGER.error("%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
