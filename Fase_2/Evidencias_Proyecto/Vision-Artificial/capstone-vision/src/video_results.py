"""Resultados estructurados sin imágenes; directorio exclusivo por ejecución."""

import csv
import json
import os
import uuid
from contextlib import ExitStack
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, data) -> None:
    # Solo actualiza archivos dentro del directorio exclusivo de esta ejecución.
    temporary = path.with_suffix(path.suffix + ".tmp")
    created = False
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            created = True
            json.dump(data, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if created and temporary.exists():
            temporary.unlink()


def create_run(output_root: Path) -> tuple[str, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex
    directory = output_root / run_id
    directory.mkdir(exist_ok=False)
    return run_id, directory


class VideoResults:
    timing_fields = ("frame_index", "timestamp_ms", "timestamp_source", "read_ms",
                     "processing_ms", "inference_ms", "model_processing_ms")

    def __init__(self, directory: Path):
        self.directory = directory
        self.stack = ExitStack()
        self.created = False

    def __enter__(self):
        self.directory.mkdir(exist_ok=False)
        self.created = True
        try:
            self.predictions = self.stack.enter_context(
                (self.directory / "predictions.jsonl").open("x", encoding="utf-8"))
            timings = self.stack.enter_context(
                (self.directory / "timings.csv").open("x", encoding="utf-8", newline=""))
            self.timing_stream = timings
            self.timings = csv.DictWriter(timings, fieldnames=self.timing_fields)
            self.timings.writeheader()
            return self
        except BaseException:
            self.stack.close()
            raise

    def __exit__(self, *exc):
        return self.stack.__exit__(*exc)

    def append(self, packet, result, processing_ms: float) -> None:
        tracked = hasattr(result, "tracks")
        row = {
            "schema_version": SCHEMA_VERSION,
            "frame_index": packet.index,
            "timestamp_ms": packet.timestamp_ms,
            "timestamp_source": packet.timestamp_source,
            "tracks": [asdict(item) for item in result.tracks] if tracked else [],
            "detections": [asdict(item) for item in result.detections] if not tracked else [],
            "untracked_detections": [asdict(item) for item in result.untracked_detections] if tracked else [],
        }
        self.predictions.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        self.timings.writerow(dict(zip(self.timing_fields, (
            packet.index, packet.timestamp_ms, packet.timestamp_source, packet.read_ms,
            processing_ms, result.inference_ms, result.processing_ms))))
        self.predictions.flush()
        self.timing_stream.flush()
