"""Compatibilidad del auxiliar que importan los tests H4 del ZIP recibido.

El ZIP no incluía este archivo. Solo provee temporales locales con cleanup;
no implementa video, no sustituye tests y no altera permisos ni paquetes.
"""

import shutil
import uuid
from pathlib import Path

from src.config import PROJECT_ROOT


class temporary_directory:
    def __init__(self):
        path = PROJECT_ROOT / "logs" / "test_temp" / uuid.uuid4().hex
        path.mkdir(parents=True, exist_ok=False)
        self.name = str(path)

    def __enter__(self):
        return self.name

    def __exit__(self, *args):
        self.cleanup()

    def cleanup(self):
        if Path(self.name).exists(): shutil.rmtree(self.name)
