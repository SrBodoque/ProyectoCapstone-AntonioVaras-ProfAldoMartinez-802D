"""Fuentes MP4 locales; sin cámara, GUI ni dependencias de inferencia."""

import hashlib
import math
import time
from dataclasses import dataclass
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class VideoCase:
    case_id: str
    path: Path
    sha256: str
    split: str | None = None
    recording_group: str | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class FramePacket:
    index: int
    timestamp_ms: float | None
    timestamp_source: str
    frame: object
    read_ms: float


def discover_cases(*, video=None, directory=None) -> list[VideoCase]:
    if (video is None) == (directory is None):
        raise ValueError("Selecciona exactamente --video o --directory.")
    value = str(video if video is not None else directory)
    if "://" in value or value.startswith(("\\\\", "//")):
        raise ValueError("Solo se permiten archivos locales, no URLs ni rutas de red UNC.")
    path = Path(value).expanduser().resolve()
    if video is not None:
        if not path.is_file() or path.suffix.lower() != ".mp4":
            raise ValueError("--video debe ser un archivo MP4 existente.")
        paths = [path]
    else:
        if not path.is_dir():
            raise ValueError("--directory debe ser una carpeta existente.")
        paths = sorted((p.resolve() for p in path.iterdir()
                        if p.is_file() and p.suffix.lower() == ".mp4"),
                       key=lambda p: (p.name.casefold(), p.name))
        if not paths:
            raise ValueError("La carpeta no contiene archivos MP4 (búsqueda no recursiva).")
    cases = []
    for index, item in enumerate(paths):
        digest = file_sha256(item)
        # Prefijo ordinal evita colisiones por contenido duplicado y nombres similares.
        cases.append(VideoCase(f"{index:04d}-{digest[:16]}", item, digest))
    return cases


def _positive(value):
    return float(value) if math.isfinite(value) and value > 0 else None


class VideoSource:
    """Una captura por contexto; status final conservador basado en metadatos."""

    def __init__(self, path: Path):
        self.path = path
        self.capture = None
        self.metadata = {}
        self.frames_read = 0
        self.status = "incomplete"
        self.reason = "Lectura no finalizada."

    def __enter__(self):
        import cv2
        self.cv2 = cv2
        self.capture = cv2.VideoCapture(str(self.path))
        try:
            if not self.capture.isOpened():
                raise RuntimeError(f"No se pudo abrir MP4: {self.path}")
            count = _positive(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
            self.metadata = {
                "backend": self.capture.getBackendName(),
                "width": _positive(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": _positive(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "reported_fps": _positive(self.capture.get(cv2.CAP_PROP_FPS)),
                "reported_frames": int(count) if count is not None and count.is_integer() else None,
            }
            return self
        except BaseException:
            self.capture.release()
            raise

    def __exit__(self, *exc):
        self.capture.release()

    def __iter__(self):
        previous_timestamp = -1.0
        while True:
            started = time.perf_counter()
            ok, frame = self.capture.read()
            read_ms = (time.perf_counter() - started) * 1000
            if not ok:
                expected = self.metadata["reported_frames"]
                if self.frames_read == 0:
                    self.status, self.reason = "failed", "El archivo no entregó frames."
                elif expected is None:
                    self.status, self.reason = "incomplete", "EOF sin número fiable de frames."
                elif self.frames_read == expected:
                    self.status, self.reason = "completed", "EOF consistente con frames informados; no certifica integridad."
                elif self.frames_read < expected:
                    self.status, self.reason = "failed", "Lectura terminó antes de los frames informados."
                else:
                    self.status, self.reason = "incomplete", "Frames leídos exceden metadatos."
                return
            if (frame is None or frame.size == 0 or len(frame.shape) != 3 or frame.shape[2] != 3):
                raise RuntimeError("El decodificador devolvió un frame BGR inválido.")
            timestamp = self.capture.get(self.cv2.CAP_PROP_POS_MSEC)
            source = "opencv"
            if not math.isfinite(timestamp) or timestamp < 0 or timestamp <= previous_timestamp:
                fps = self.metadata["reported_fps"]
                timestamp = self.frames_read * 1000 / fps if fps else None
                source = "index/reported_fps" if fps else "unavailable"
            if timestamp is not None:
                previous_timestamp = timestamp
            packet = FramePacket(self.frames_read, timestamp, source, frame, read_ms)
            self.frames_read += 1
            yield packet
