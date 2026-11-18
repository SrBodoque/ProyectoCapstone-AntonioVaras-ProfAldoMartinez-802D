# -*- coding: utf-8 -*-
"""Procesos del lanzador: sin consola visible, logs locales y parada controlada.

No cambia las aplicaciones de vision ni Django. No almacena credenciales.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import time
from datetime import datetime


def carpeta_logs() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    return base / "HigieneSmart" / "lanzador_operativo" / "logs"


def iniciar_oculto(argv: list[str], *, cwd: Path, env: dict, etiqueta: str,
                   con_stdin: bool = False) -> tuple[subprocess.Popen, Path]:
    """Inicia Python sin consola adicional. OpenCV conserva su ventana GUI."""
    if not etiqueta.replace("_", "").isalnum():
        raise ValueError("Nombre de registro invalido.")
    destino = carpeta_logs()
    destino.mkdir(parents=True, exist_ok=True)
    nombre = f"{etiqueta}_{datetime.now():%Y%m%d_%H%M%S_%f}.log"
    ruta_log = destino / nombre
    with ruta_log.open("ab") as registro:
        proc = subprocess.Popen(
            argv,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.PIPE if con_stdin else subprocess.DEVNULL,
            stdout=registro,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            close_fds=True,
        )
    return proc, ruta_log


def terminar_proceso(proc: subprocess.Popen | None, *, espera: float = 3.0) -> bool:
    """Finaliza solo el proceso recibido. Devuelve True si ya termino."""
    if proc is None or proc.poll() is not None:
        return True
    try:
        proc.terminate()
        proc.wait(timeout=espera)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            return False
    except OSError:
        return proc.poll() is not None
    return True


def esperar_emisor(proc: subprocess.Popen | None, marca_fin: Path | None,
                   *, espera: float = 15.0) -> bool:
    """Solicita salida cooperativa; eventos en SQLite quedan persistidos."""
    if proc is None or proc.poll() is not None:
        return True
    if marca_fin is not None:
        # El emisor comprueba esta marca ANTES de esperar el siguiente lote.
        marca_fin.parent.mkdir(parents=True, exist_ok=True)
        marca_fin.touch(exist_ok=True)
    try:
        proc.wait(timeout=espera)
        return True
    except subprocess.TimeoutExpired:
        return terminar_proceso(proc)
