"""Orquestación secuencial MP4: sesiones independientes, baseline sin tuning."""

import gc
import platform
import sys
import time
from dataclasses import asdict, dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .config import (PROJECT_ROOT, load_detection_config, load_tracking_config,
                     load_tracker_config, resolve_tracker_path)
from .detector import PersonDetector
from .devices import load_torch, validate_device
from .tracker import PersonTracker
from .video_results import SCHEMA_VERSION, VideoResults, create_run, utc_now, write_json
from .video_source import VideoCase, VideoSource, file_sha256


@dataclass(frozen=True)
class RunOptions:
    mode: str
    device: str


@dataclass(frozen=True)
class VideoRunResult:
    case_id: str
    status: str
    frames_processed: int
    output_directory: str
    error: str | None = None


@dataclass
class PreparedRun:
    detection: dict
    tracking: dict | None
    provenance: dict
    torch: object

    def synchronize(self, device):
        if device.startswith("cuda:"):
            self.torch.cuda.synchronize(int(device[5:]))


def prepare_runtime(options: RunOptions) -> PreparedRun:
    if options.mode not in ("detection", "tracking"):
        raise ValueError("mode debe ser detection o tracking.")
    detection = load_detection_config()
    tracking = load_tracking_config() if options.mode == "tracking" else None
    tracker_path = resolve_tracker_path(tracking["tracker_config"]) if tracking else None
    tracker_params = load_tracker_config(tracker_path) if tracker_path else None
    if tracker_path and tracker_path != (PROJECT_ROOT / "config/bytetrack_capstone.yaml").resolve():
        raise ValueError("Etapa 1 solo admite el perfil ByteTrack baseline actual.")
    if tracker_params and tracker_params["tracker_type"] != "bytetrack":
        raise ValueError("Etapa 1 requiere ByteTrack baseline.")
    model_path = PROJECT_ROOT / detection["model"]
    if not model_path.is_file() or model_path.stat().st_size == 0:
        raise RuntimeError(f"Faltan pesos locales no vacíos: {model_path}. No se descargarán.")
    # No se instancia YOLO antes de verificar recursos locales y dispositivo.
    torch = load_torch()
    validate_device(options.device, torch_module=torch)
    import cv2
    versions = {}
    for name in ("opencv-python", "ultralytics", "torch", "torchvision", "numpy", "PyYAML", "lap"):
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            versions[name] = None
    provenance = {
        "profile": "bytetrack_baseline" if tracking else "detection_baseline",
        "model": detection["model"], "model_sha256": file_sha256(model_path),
        "detection_config": dict(detection),
        "tracking_config": dict(tracking) if tracking else None,
        "tracker_parameters": tracker_params,
        "tracker_yaml_sha256": file_sha256(tracker_path) if tracker_path else None,
        "versions": versions, "python": sys.version, "python_executable": sys.executable,
        "platform": platform.platform(), "cuda_build": torch.version.cuda,
        "device_name": torch.cuda.get_device_name(int(options.device[5:]))
                       if options.device.startswith("cuda:") else "CPU",
        "opencv_version": cv2.__version__, "ultralytics_version": versions["ultralytics"],
    }
    return PreparedRun(detection, tracking, provenance, torch)


def process_case(case: VideoCase, options: RunOptions, prepared: PreparedRun,
                 run_directory: Path) -> VideoRunResult:
    directory = run_directory / case.case_id
    metadata = {
        "schema_version": SCHEMA_VERSION, "run_id": run_directory.name,
        "case_id": case.case_id, "input_path": str(case.path), "input_sha256": case.sha256,
        "split": case.split, "recording_group": case.recording_group, "tags": case.tags,
        "mode": options.mode, "device_requested": options.device, "device_effective": None,
        "configuration": prepared.provenance, "started_at": utc_now(),
        "status": "failed", "frames_processed": 0, "frames_read": 0,
    }
    source = None
    engine = None
    output = VideoResults(directory)
    started = time.perf_counter()
    try:
        with output:
            write_json(directory / "metadata.json", metadata)
            # Es un archivo local mutable: detectar cambios posteriores a la enumeración.
            if file_sha256(case.path) != case.sha256:
                raise RuntimeError("El video cambió después de seleccionar los casos.")
            with VideoSource(case.path) as source:
                metadata["video"] = dict(source.metadata)
                loading = time.perf_counter()
                if options.mode == "detection":
                    engine = PersonDetector(prepared.detection, device_override=options.device)
                    process = engine.detect
                else:
                    engine = PersonTracker(prepared.detection, prepared.tracking,
                                           device_override=options.device)
                    process = engine.track
                prepared.synchronize(options.device)
                metadata["model_load_ms"] = (time.perf_counter() - loading) * 1000
                effective = engine.device_resolution.effective_device
                metadata["device_effective"] = effective
                metadata["effective_detection_config"] = dict(engine.config)
                if effective != options.device or engine.device_resolution.fallback:
                    raise RuntimeError("El dispositivo efectivo no coincide con el solicitado; se aborta.")
                for packet in source:
                    prepared.synchronize(effective)
                    before = time.perf_counter()
                    result = process(packet.frame)
                    prepared.synchronize(effective)
                    processing_ms = (time.perf_counter() - before) * 1000
                    output.append(packet, result, processing_ms)
                    metadata["frames_processed"] += 1
                    if packet.index == 0:
                        metadata["first_frame_processing_ms"] = processing_ms
                metadata["status"] = source.status
                metadata["termination_reason"] = source.reason
    except KeyboardInterrupt:
        metadata["status"] = "interrupted"
        metadata["error"] = "Interrupción solicitada por el usuario."
    except Exception as exc:
        metadata["status"] = "failed"
        metadata["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        metadata["frames_read"] = source.frames_read if source else 0
        metadata["elapsed_ms"] = (time.perf_counter() - started) * 1000
        metadata["finished_at"] = utc_now()
        # Sin invocar métodos privados de Ultralytics ni reutilizar sesiones.
        process = None
        engine = None
        gc.collect()  # Libera ciclos del modelo/callbacks antes de la siguiente sesión.
    if output.created:
        write_json(directory / "metadata.json", metadata)
    return VideoRunResult(case.case_id, metadata["status"], metadata["frames_processed"],
                          str(directory), metadata.get("error") or (
                              metadata.get("termination_reason") if metadata["status"] != "completed" else None))


def run_cases(cases: list[VideoCase], options: RunOptions,
              output_root: Path = PROJECT_ROOT / "results_testing") -> tuple[Path, dict]:
    if not cases:
        raise ValueError("No hay casos que procesar.")
    identifiers = [case.case_id for case in cases]
    if len(set(identifiers)) != len(identifiers) or any(
            not item or item in (".", "..") or "/" in item or "\\" in item or ":" in item
            for item in identifiers):
        raise ValueError("Los identificadores de casos deben ser únicos y nombres locales seguros.")
    run_id, directory = create_run(Path(output_root))
    manifest = {"schema_version": SCHEMA_VERSION, "run_id": run_id,
                "started_at": utc_now(), "options": asdict(options),
                "status": "running", "cases": [
                    {**asdict(case), "path": str(case.path)} for case in cases]}
    summary = {"schema_version": SCHEMA_VERSION, "run_id": run_id,
               "status": "failed", "results": [], "not_processed": identifiers.copy()}
    write_json(directory / "run.json", manifest)
    write_json(directory / "summary.json", summary)
    try:
        prepared = prepare_runtime(options)
        manifest["configuration"] = prepared.provenance
        write_json(directory / "run.json", manifest)
        for case in cases:
            result = process_case(case, options, prepared, directory)
            summary["results"].append(asdict(result))
            summary["not_processed"].remove(case.case_id)
            write_json(directory / "summary.json", summary)
            if result.status == "interrupted":
                break
        states = [item["status"] for item in summary["results"]]
        summary["status"] = ("interrupted" if "interrupted" in states else
                             "failed" if "failed" in states else
                             "incomplete" if "incomplete" in states else "completed")
    except KeyboardInterrupt:
        summary["status"] = "interrupted"
        summary["error"] = "Interrupción solicitada por el usuario."
    except Exception as exc:
        summary["status"] = "failed"
        summary["error"] = f"{type(exc).__name__}: {exc}"
    manifest["status"] = summary["status"]
    manifest["finished_at"] = utc_now()
    write_json(directory / "run.json", manifest)
    write_json(directory / "summary.json", summary)
    return directory, summary
