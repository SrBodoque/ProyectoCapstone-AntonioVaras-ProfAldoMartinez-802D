"""Perfil A exterior/B puerta vinculado a un MP4; sin parámetros de tracking."""

import json
from dataclasses import dataclass
from pathlib import Path

from .count_orientation import profile_hash
from .saved_results import ResultsError, number, read_json
from .video_source import file_sha256
from .zones import ZoneProfile


@dataclass(frozen=True)
class VideoZones:
    path: Path
    profile: ZoneProfile
    video_sha256: str
    file_sha256: str


def export_video_zones(output, video, profile, frame_index, reviewer):
    output, video = Path(output), Path(video).resolve()
    if output.suffix.lower() != ".json" or output.is_symlink():
        raise ValueError("Seleccione un JSON nuevo y no enlazado.")
    if type(frame_index) is not int or frame_index < 0 or not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("Se requieren frame de referencia y responsable de la revisión.")
    data = dict(schema_version=1, kind="limpia_video_zones", video_sha256=file_sha256(video),
                orientation={"A": "exterior", "B": "puerta"}, orientation_confirmed=True,
                reviewer=reviewer.strip(), reference_frame_index=frame_index,
                profile=profile.to_dict(), profile_sha256=profile_hash(profile))
    with output.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")
    return output


def load_video_zones(path, video):
    path = Path(path).expanduser().resolve()
    if not path.is_file() or path.stat().st_size > 262144:
        raise ResultsError("Perfil de video inexistente o demasiado grande.")
    profile_file_hash = file_sha256(path)
    data = read_json(path.read_text(encoding="utf-8-sig"), "perfil de video")
    keys = {"schema_version", "kind", "video_sha256", "orientation", "orientation_confirmed",
            "reviewer", "reference_frame_index", "profile", "profile_sha256"}
    if (not isinstance(data, dict) or set(data) != keys or type(data["schema_version"]) is not int
            or data["schema_version"] != 1 or data["kind"] != "limpia_video_zones"
            or data["orientation"] != {"A": "exterior", "B": "puerta"}
            or data["orientation_confirmed"] is not True
            or not isinstance(data["reviewer"], str) or not data["reviewer"].strip()
            or type(data["reference_frame_index"]) is not int or data["reference_frame_index"] < 0):
        raise ResultsError("Se requiere un perfil MP4 con orientación A exterior/B puerta confirmada; no se reinterpreta un perfil de cámara.")
    digest = file_sha256(Path(video))
    if data["video_sha256"] != digest:
        raise ResultsError("El JSON de zonas no corresponde al hash de este MP4.")
    profile = ZoneProfile.from_dict(data["profile"])
    if profile_hash(profile) != data["profile_sha256"]:
        raise ResultsError("El perfil de zonas cambió después de su confirmación.")
    if file_sha256(path) != profile_file_hash:
        raise ResultsError("El JSON cambió mientras se leía.")
    return VideoZones(path, profile, digest, profile_file_hash)


def validate_dimensions(zones, metadata):
    video = metadata.get("video") or {}
    width, height = video.get("width"), video.get("height")
    if not number(width) or not number(height) or width <= 0 or height <= 0:
        raise ResultsError("No hay resolución válida para normalizar las cajas.")
    if width != zones.profile.width or height != zones.profile.height:
        raise ResultsError("Las dimensiones del tracking no coinciden con el perfil del MP4.")
    return width, height
