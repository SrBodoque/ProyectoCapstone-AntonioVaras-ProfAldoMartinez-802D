"""Fixtures locales sin mkdir(mode=0o700), incompatible con algunos tokens Windows."""

import shutil
import uuid
from pathlib import Path


class temporary_directory:
    """Temporal exclusivo bajo logs; no modifica ACL ni usa temporales personales."""

    def __init__(self):
        self.root = (Path(__file__).resolve().parent.parent / "logs" / "video_test_temp").resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / uuid.uuid4().hex
        self.path.mkdir(exist_ok=False)
        self.name = str(self.path)

    def __enter__(self):
        return self.name

    def __exit__(self, *exc):
        self.cleanup()

    def cleanup(self):
        target = self.path.resolve()
        if target.parent != self.root or not target.name:
            raise RuntimeError("Temporal fuera del directorio de pruebas.")
        if target.exists():
            shutil.rmtree(target)
