"""Conteo de predicciones completas guardadas; sin inferencia ni cámara."""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from .count_engine import CountSettings, Observation, TransitionCounter
from .count_orientation import profile_hash
from .saved_results import ResultsError, load_case, number, select_case
from .video_results import create_run, utc_now, write_json
from .video_source import file_sha256
from .video_zones import load_video_zones, validate_dimensions


def _timeline(case):
    frames = [case.frames[i] for i in range(len(case.frames))]
    times = [frame.timestamp_ms for frame in frames]
    if all(number(t) and t >= 0 for t in times) and all(a < b for a, b in zip(times, times[1:])):
        return (t / 1000 for t in times), "predictions.timestamp_ms"
    fps = case.metadata.get("video", {}).get("reported_fps")
    if not number(fps) or fps <= 0:
        raise ResultsError("No hay timestamps crecientes ni FPS válidos para el conteo.")
    return (i / fps for i in range(len(frames))), "frame_index/reported_fps"


def validate_case(case, zones):
    meta = case.metadata
    if meta.get("mode") != "tracking" or meta.get("status") != "completed":
        raise ResultsError("Seleccione predicciones de tracking completas; detección sin IDs o resultados parciales no acreditan conteo.")
    if str(meta.get("input_sha256", "")).lower() != zones.video_sha256:
        raise ResultsError("El tracking no corresponde al hash del MP4 y sus zonas.")
    n = len(case.frames)
    if (n == 0 or type(meta.get("frames_processed")) is not int or meta["frames_processed"] != n
            or min(case.frames) != 0 or max(case.frames) + 1 != n):
        raise ResultsError("Faltan filas de frames; no se sustituyen predicciones ausentes por frames vacíos.")
    expected = meta.get("video", {}).get("reported_frames")
    if number(expected) and expected > 0 and expected != n:
        raise ResultsError("El número de frames no coincide con el video registrado.")
    if case.notices.codes - {"out_of_order", "timestamp"}:
        raise ResultsError("Predicciones inconsistentes: " + "; ".join(case.notices.messages))
    return validate_dimensions(zones, meta)


def run_count_replay(video, zones_path, predictions, output_root, settings=None, settings_source=None):
    zones = load_video_zones(zones_path, video)
    video, selected = select_case(predictions, video)
    source_paths = {name: selected.directory / name for name in ("metadata.json", "predictions.jsonl")}
    source_hashes = {name: file_sha256(path) for name, path in source_paths.items()}
    case = load_case(selected.directory)  # Lectura vinculada a los hashes anteriores.
    width, height = validate_case(case, zones)
    times, time_source = _timeline(case)
    counter = TransitionCounter(zones.profile, settings or CountSettings())
    if settings_source and file_sha256(Path(settings_source["path"])) != settings_source["sha256"]:
        raise ResultsError("La configuración del contador cambió antes de contar.")
    run_id, directory = create_run(Path(output_root).resolve() / "counting")
    config = case.metadata.get("configuration") or {}
    historical_weights = ([{"role": "detector", "model": config.get("model"),
                            "sha256": config.get("model_sha256"), "source": "historical_metadata"}]
                          if not case.metadata.get("weights_used") else case.metadata["weights_used"])
    manifest = dict(schema_version=1, kind="limpia_counting_run", run_id=run_id, status="running",
                    started_at=utc_now(), video=str(video), video_sha256=zones.video_sha256,
                    zones_file=str(zones.path), zones_file_sha256=zones.file_sha256,
                    profile=zones.profile.to_dict(), profile_sha256=profile_hash(zones.profile),
                    orientation={"A": "exterior", "B": "puerta"},
                    thresholds=asdict(counter.settings), timestamp_source=time_source,
                    thresholds_sha256=hashlib.sha256(json.dumps(asdict(counter.settings), sort_keys=True).encode()).hexdigest(),
                    thresholds_source=settings_source,
                    predictions_directory=str(case.directory), predictions_hashes=source_hashes,
                    tracking_configuration=config, weights_used=historical_weights,
                    device_effective_for_tracking=case.metadata.get("device_effective"),
                    device_for_counting="CPU; sin inferencia", inference_repeated=False,
                    warnings=case.notices.messages)
    summary = dict(schema_version=1, kind="limpia_counting_summary", run_id=run_id,
                   status="running", frames_processed=0, expected_frames=len(case.frames),
                   entries=0, exits=0, events=0, rejected_point_frames=0,
                   inference_repeated=False, accuracy_validated=False)
    write_json(directory / "run.json", manifest)
    write_json(directory / "summary.json", summary)
    try:
        with (directory / "events.jsonl").open("x", encoding="utf-8") as stream, \
                (directory / "diagnostics.jsonl").open("x", encoding="utf-8") as diagnostics:
            for index, timestamp in enumerate(times):
                saved = case.frames[index]
                observations = [Observation(o.track_id, ((o.x1 / 2 + o.x2 / 2) / width, o.y2 / height))
                                for o in saved.tracks]
                previous = {identifier: (s.phase, s.reason, s.episode, s.reset_reason)
                            for identifier, s in counter.states.items()}
                events = counter.update(timestamp, observations)
                for identifier, state in counter.states.items():
                    if previous.get(identifier) != (state.phase, state.reason, state.episode, state.reset_reason):
                        diagnostics.write(json.dumps(dict(frame_index=index, timestamp=timestamp,
                            track_id=identifier, phase=state.phase.value, reason=state.reason,
                            reset_reason=state.reset_reason), ensure_ascii=False, allow_nan=False) + "\n")
                if any(counter.states[o.track_id].zone == "INVALIDO" for o in observations):
                    summary["rejected_point_frames"] += 1
                for event in events:
                    stream.write(json.dumps({**asdict(event), "frame_index": index},
                                            ensure_ascii=False, allow_nan=False) + "\n")
                summary["frames_processed"] += 1
        for name, path in source_paths.items():
            if file_sha256(path) != source_hashes[name]:
                raise ResultsError(f"{name} cambió durante el conteo.")
        if file_sha256(zones.path) != zones.file_sha256 or file_sha256(video) != zones.video_sha256:
            raise ResultsError("El perfil o el video cambió durante el conteo.")
        if settings_source and file_sha256(Path(settings_source["path"])) != settings_source["sha256"]:
            raise ResultsError("La configuración del contador cambió durante el conteo.")
        summary["status"] = "completed"
    except KeyboardInterrupt:
        summary["status"], summary["error"] = "interrupted", "Interrupción solicitada; resultados parciales."
    except Exception as exc:
        summary["status"], summary["error"] = "failed", f"{type(exc).__name__}: {exc}"
    summary.update(entries=counter.total_entries, exits=counter.total_exits, events=counter.total_events)
    manifest.update(status=summary["status"], finished_at=utc_now())
    write_json(directory / "run.json", manifest)
    write_json(directory / "summary.json", summary)
    return directory, summary
