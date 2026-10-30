"""Fixtures sintéticos propios de Etapa 1.5; nunca usa recursos históricos."""

import json
from pathlib import Path

from src.video_source import file_sha256


def box(identifier=1, confidence=.9, **changes):
    result = dict(x1=10, y1=80, x2=50, y2=130, confidence=confidence, track_id=identifier)
    result.update(changes)
    return result


def row(index=0, tracks=None, **changes):
    result = dict(schema_version=1, frame_index=index, tracks=tracks or [],
                  detections=[], untracked_detections=[])
    result.update(changes)
    return result


def write_case(directory, video_path, rows=None, **changes):
    directory = Path(directory)
    directory.mkdir(parents=True)
    rows = [row()] if rows is None else rows
    metadata = dict(schema_version=1, input_path=str(video_path), input_sha256=file_sha256(video_path),
        status="completed", mode="tracking", frames_processed=len(rows), frames_read=len(rows),
        device_requested="cuda:0", device_effective="cuda:0", elapsed_ms=1000,
        video=dict(width=160, height=160, reported_frames=max((r["frame_index"] for r in rows), default=-1) + 1, reported_fps=25),
        configuration=dict(model="yolo26n.pt", profile="bytetrack_baseline", device_name="NVIDIA RTX 5060",
                           tracker_parameters=dict(tracker_type="bytetrack")))
    metadata.update(changes)
    (directory / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (directory / "predictions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return directory
