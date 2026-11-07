"""Recursos locales y protección de pesos para el runner MP4; ningún motor nuevo."""

import os
import sys
from contextlib import contextmanager
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .counting_config import select_tracker
from .detector import _load_yolo
from .video_source import file_sha256

ALIASES = {"fasttrack": "fasttracker"}
_protected = []
_hook_installed = False


def canonical_tracker(name):
    return ALIASES.get(name, name)


def _key(value):
    if not isinstance(value, (str, bytes, os.PathLike)):
        return None
    return os.path.normcase(str(Path(os.fsdecode(value)).resolve()))


def _audit(event, args):
    if not _protected:
        return
    if event in ("socket.connect", "socket.getaddrinfo", "urllib.Request"):
        raise RuntimeError("Red bloqueada durante el procesamiento local; no se descargan recursos.")
    paths = set().union(*_protected)
    if event == "open" and _key(args[0]) in paths:
        mode, flags = args[1:3]
        if (isinstance(mode, str) and any(c in mode for c in "wax+")
                or isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            raise RuntimeError("No se permite modificar un peso o video de entrada.")
    if event in ("os.remove", "os.rename") and any(_key(v) in paths for v in args[:2]):
        raise RuntimeError("No se permite eliminar ni reemplazar pesos o videos de entrada.")


@contextmanager
def local_processing(files, working_directory=None):
    """Sin parches a Ultralytics; la protección se desactiva al salir del contexto."""
    global _hook_installed
    if not _hook_installed:
        sys.addaudithook(_audit)
        _hook_installed = True
    keys = {_key(p) for p in files}
    old_directory = Path.cwd()
    _protected.append(keys)
    try:
        if working_directory is not None:
            os.chdir(working_directory)
        yield
    finally:
        try:
            os.chdir(old_directory)
        finally:
            _protected.pop()


def local_weights_root(value):
    text = str(value)
    if "://" in text or text.startswith(("\\\\", "//")):
        raise ValueError("Los pesos deben estar en un directorio local, no una URL o ruta UNC.")
    return Path(value).expanduser().resolve()


def resolve_resources(name, weights_root, model):
    """Primero archivos locales, antes de importar/inicializar cualquier backend."""
    name = canonical_tracker(name)
    selection = select_tracker(name)
    root = local_weights_root(weights_root)
    required = [("detector", root / model)]
    if name == "botsort_reid":
        required.append(("reid", root / "yolo26n-cls.pt"))
    missing = [str(p) for _, p in required if not p.is_file() or p.stat().st_size == 0]
    if missing:
        raise RuntimeError("Faltan pesos locales no vacíos: " + ", ".join(missing) + ". No se descargarán.")
    weights = [{"role": role, "path": str(p), "sha256": file_sha256(p)} for role, p in required]
    return selection, weights


def check_backend(kind):
    missing = []
    for package in ("ultralytics", "torch", "torchvision", "opencv-python", "numpy", "PyYAML", "lap"):
        try:
            installed = version(package)
        except PackageNotFoundError:
            missing.append(package)
            continue
        if package == "ultralytics" and installed != "8.4.163":
            raise RuntimeError(f"Ultralytics incompatible: {installed}; se requiere 8.4.163. No se instala otra versión.")
    if missing:
        raise RuntimeError("Faltan dependencias locales: " + ", ".join(missing) + ". No se instalan automáticamente.")
    _load_yolo()  # Aplica la política local existente antes del import de Ultralytics.
    from ultralytics.trackers.track import TRACKER_MAP
    if kind not in TRACKER_MAP:
        raise RuntimeError(f"Backend {kind} no disponible en la instalación; no se cambia de tracker.")
    return TRACKER_MAP[kind].__name__
