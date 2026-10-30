"""Lectura de resultados v1 en memoria; no importa OpenCV ni módulos de IA."""

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from .video_source import file_sha256


class ResultsError(ValueError):
    """Datos ilegibles, ambiguos o incompatibles; no deben visualizarse."""


@dataclass
class Notices:
    messages: list[str] = field(default_factory=list)
    count: int = 0

    def add(self, message):
        self.count += 1
        if len(self.messages) < 20 and message not in self.messages:
            self.messages.append(message)


@dataclass(frozen=True)
class Observation:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float | None = None
    track_id: int | None = None

    @property
    def center(self):
        return (self.x1 / 2 + self.x2 / 2, self.y1 / 2 + self.y2 / 2)


@dataclass(frozen=True)
class SavedFrame:
    index: int
    tracks: tuple[Observation, ...] = ()
    detections: tuple[Observation, ...] = ()
    untracked: tuple[Observation, ...] = ()
    available: bool = True


@dataclass
class SavedCase:
    directory: Path
    metadata: dict
    frames: dict[int, SavedFrame]
    notices: Notices

    def frame(self, index):
        return self.frames.get(index, SavedFrame(index, available=False))


def number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _reject_constant(value):
    raise ResultsError(f"Número JSON no finito: {value}")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ResultsError(f"Clave JSON duplicada: {key}")
        result[key] = value
    return result


def read_json(text, description):
    try:
        return json.loads(text, parse_constant=_reject_constant, object_pairs_hook=_unique_object)
    except (ValueError, RecursionError) as exc:
        raise ResultsError(f"{description}: JSON inválido o incompleto ({exc}).") from exc


def read_metadata(directory: Path):
    try:
        data = read_json((directory / "metadata.json").read_text(encoding="utf-8-sig"), "metadata.json")
    except (OSError, UnicodeError) as exc:
        raise ResultsError(f"No se puede leer metadata.json en {directory}: {exc}") from exc
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ResultsError("Se requieren metadatos del esquema v1.")
    digest = data.get("input_sha256")
    if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest)):
        raise ResultsError("input_sha256 inválido: no se sustituirá por una coincidencia de nombre.")
    if "video" in data and not isinstance(data["video"], dict):
        raise ResultsError("El campo video de los metadatos debe ser un objeto.")
    return data


def _observation(data, identity, notices, context):
    if not isinstance(data, dict):
        notices.add(f"{context}: caja no válida omitida.")
        return None
    coords = [data.get(key) for key in ("x1", "y1", "x2", "y2")]
    if not all(number(v) for v in coords) or coords[2] <= coords[0] or coords[3] <= coords[1]:
        notices.add(f"{context}: coordenadas inválidas; caja omitida.")
        return None
    confidence = data.get("confidence")
    if confidence is not None and (not number(confidence) or not 0 <= confidence <= 1):
        notices.add(f"{context}: confianza inválida; etiqueta de confianza omitida.")
        confidence = None
    identifier = data.get("track_id") if identity else None
    if identity and (type(identifier) is not int or not 0 < identifier <= 2**31 - 1):
        notices.add(f"{context}: sin ID válido; se muestra como detección sin ID.")
        identifier = None
    return Observation(*map(float, coords), confidence, identifier)


def load_case(directory) -> SavedCase:
    directory = Path(directory).resolve()
    metadata = read_metadata(directory)
    frames, notices = {}, Notices()
    previous = -1
    try:
        with (directory / "predictions.jsonl").open(encoding="utf-8-sig") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                context = f"predictions.jsonl, línea {line_number}"
                row = read_json(line, context)
                if not isinstance(row, dict):
                    raise ResultsError(f"{context}: se requiere un objeto.")
                index = row.get("frame_index")
                if type(index) is not int or index < 0:
                    raise ResultsError(f"{context}: frame_index debe ser un entero no negativo.")
                if index in frames:
                    raise ResultsError(f"{context}: frame_index {index} duplicado; asociación ambigua.")
                if "schema_version" in row and (type(row["schema_version"]) is not int or row["schema_version"] != 1):
                    raise ResultsError(f"{context}: esquema de predicciones no compatible.")
                if index < previous:
                    notices.add("JSONL desordenado: se indexa por frame_index, sin alterar el archivo.")
                previous = index
                groups = {}
                ids = set()
                for group in ("tracks", "detections", "untracked_detections"):
                    items = row.get(group, [])
                    if not isinstance(items, list):
                        raise ResultsError(f"{context}: {group} debe ser una lista.")
                    valid = []
                    for data in items:
                        item = _observation(data, group == "tracks", notices, context)
                        if item is None:
                            continue
                        if item.track_id is not None:
                            if item.track_id in ids:
                                raise ResultsError(f"{context}: ID {item.track_id} repetido en el mismo frame.")
                            ids.add(item.track_id)
                        valid.append(item)
                    groups[group] = valid
                without_id = [item for item in groups["tracks"] if item.track_id is None]
                frames[index] = SavedFrame(index,
                    tuple(item for item in groups["tracks"] if item.track_id is not None),
                    tuple(groups["detections"]), tuple(groups["untracked_detections"] + without_id))
    except (OSError, UnicodeError) as exc:
        raise ResultsError(f"No se puede leer predictions.jsonl: {exc}") from exc
    if not frames:
        notices.add("No hay predicciones guardadas.")
    elif min(frames) != 0 or max(frames) + 1 != len(frames):
        notices.add("Faltan registros de frames; no se reutilizan cajas de otros fotogramas.")
    if metadata.get("status") != "completed":
        notices.add(f"Resultado histórico con estado {metadata.get('status', 'no registrado')}; puede ser parcial.")
    if metadata.get("frames_processed") != len(frames):
        notices.add("La cantidad de registros no coincide con frames_processed de los metadatos.")
    return SavedCase(directory, metadata, frames, notices)


def select_case(results, video):
    """Acepta carpeta de caso o lote; no sigue output_directory histórico."""
    text = str(video)
    if "://" in text or text.startswith(("\\\\", "//")):
        raise ResultsError("Selecciona un MP4 local, no una URL ni una ruta UNC.")
    video = Path(video).expanduser().resolve()
    if not video.is_file() or video.suffix.lower() != ".mp4":
        raise ResultsError(f"MP4 inexistente o inaccesible: {video}")
    digest = file_sha256(video)
    directory = Path(results).expanduser().resolve()
    if not directory.is_dir():
        raise ResultsError(f"Directorio de resultados inexistente: {directory}")
    if (directory / "metadata.json").is_file():
        candidates = [directory]
    else:
        candidates = sorted(p for p in directory.iterdir() if p.is_dir() and (p / "metadata.json").is_file())
    metadata = [(path, read_metadata(path)) for path in candidates]
    matches = [path for path, data in metadata if (data.get("input_sha256") or "").lower() == digest]
    if not matches and len(metadata) == 1 and metadata[0][1].get("input_sha256") is None:
        matches = [metadata[0][0]]
    if len(matches) != 1:
        raise ResultsError("No hay un único caso compatible con el MP4. Selecciona su carpeta de caso o lote explícitamente.")
    case = load_case(matches[0])
    if case.metadata.get("input_sha256") is None:
        case.notices.add("Sin hash histórico: se comprobarán dimensiones y frames; no se certifica identidad del contenido.")
    return video, case


def validate_video(case, actual):
    expected = case.metadata.get("video", {})
    no_hash = case.metadata.get("input_sha256") is None
    for key in ("width", "height", "reported_frames"):
        saved, current = expected.get(key), actual.get(key)
        if no_hash and (not number(saved) or saved <= 0 or not number(current) or current <= 0):
            raise ResultsError("Sin hash se requieren dimensiones y número de frames verificables.")
        if number(saved) and saved > 0 and number(current) and current > 0 and saved != current:
            raise ResultsError(f"MP4 incompatible: {key} actual={current}, registrado={saved}.")
    count = actual.get("reported_frames")
    if number(count) and count > 0 and case.frames and max(case.frames) >= count:
        raise ResultsError("Las predicciones contienen índices fuera del MP4.")
    old_fps, fps = expected.get("reported_fps"), actual.get("reported_fps")
    if number(old_fps) and number(fps) and abs(old_fps - fps) > max(.02, old_fps * .01):
        case.notices.add("Los FPS informados difieren; se usará la temporización del MP4 actual.")
    fps = fps if number(fps) and fps > 0 else old_fps
    if not number(fps) or fps <= 0:
        raise ResultsError("No hay FPS válidos para temporizar la reproducción.")
    return float(fps)
