"""CLI independiente: python -m src.process_videos --help."""

import argparse
import logging
from pathlib import Path

from .config import PROJECT_ROOT
from .devices import validate_device_format
from .processing_report import print_processing_report
from .video_runner import RunOptions, run_cases
from .video_source import discover_cases


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Procesa MP4 locales con el baseline actual, sin cámara ni GUI.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--video", help="Archivo MP4 local.")
    source.add_argument("--directory", help="Carpeta local; MP4 no recursivos y en orden estable.")
    parser.add_argument("--mode", required=True, choices=("detection", "tracking"))
    parser.add_argument("--device", required=True, help="cpu o cuda:N; sin fallback.")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "results_testing")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        validate_device_format(args.device)
        cases = discover_cases(video=args.video, directory=args.directory)
        directory, summary = run_cases(cases, RunOptions(args.mode, args.device), args.output)
        print_processing_report(directory, summary)
        return 0 if summary["status"] == "completed" else 130 if summary["status"] == "interrupted" else 1
    except KeyboardInterrupt:
        return 130
    except (ValueError, OSError, RuntimeError) as exc:
        logging.error("%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
