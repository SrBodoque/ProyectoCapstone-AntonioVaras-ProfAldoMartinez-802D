# -*- coding: utf-8 -*-
"""Preparacion independiente del lanzador operativo.

Reutiliza el probe del instalador original sin editarlo. Solo crea un
entorno Django nuevo con consentimiento; no toca PostgreSQL ni sus datos.
"""
from __future__ import annotations
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

VISION = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(VISION))
DJANGO = VISION.parent.parent / "HigieneSmart"


def seleccionar_vision():
    import instalar_limpia
    explicit = os.environ.get("LIMPIA_PYTHON_VISION")
    for python in instalar_limpia.candidates(explicit):
        if not python.is_file():
            continue
        try:
            instalar_limpia.probe(python, "cuda:0")
            return python
        except (OSError, subprocess.SubprocessError, ValueError):
            continue
    raise RuntimeError(
        "La comprobacion original finalizo, pero no encontramos el "
        "interprete validado. Configure LIMPIA_PYTHON_VISION y reintente."
    )


def validar_django(python):
    if not python.is_file():
        return False, "Entorno Django no existe"
    test = subprocess.run(
        [str(python), "-B", "-c",
         "import django, psycopg, dotenv, PIL; print('Django', django.get_version())"],
        cwd=str(DJANGO), capture_output=True, text=True,
    )
    return test.returncode == 0, (test.stdout.strip() if test.returncode == 0 else test.stderr.strip())


def instalar_django_si_falta(python_vision, python_django, *, solo_verificar):
    if python_django.exists():
        ok, detail = validar_django(python_django)
        if not ok:
            raise RuntimeError(
                "Ya existe .venv de HigieneSmart, pero le faltan dependencias. "
                "No se modifica automaticamente un entorno existente. "
                "Revise el error: " + detail[-500:]
            )
        return python_django, detail
    if solo_verificar:
        raise RuntimeError("Falta .venv de HigieneSmart. Modo --verificar: no se instala nada.")
    if not DJANGO.is_dir() or not (DJANGO / "manage.py").is_file():
        raise RuntimeError("Falta el proyecto Django en " + str(DJANGO))
    print("No existe el entorno Django en", python_django.parent.parent)
    if input("Crear entorno Django e instalar requirements.txt? [s/N]: ").strip().lower() != "s":
        raise RuntimeError("Preparacion Django cancelada; no se creo un entorno.")
    if python_django.parent.parent.exists():
        raise RuntimeError("La carpeta .venv ya existe, no se sobrescribe.")
    req = DJANGO / "requirements.txt"
    if not req.is_file():
        raise RuntimeError("No se encontro requirements.txt de Django.")
    subprocess.run([str(python_vision), "-m", "venv", str(python_django.parent.parent)], check=True)
    # El requirements.txt del ZIP fue guardado en UTF-16LE. Crear solo una
    # copia temporal UTF-8 para pip; nunca cambiar el original del companero.
    raw = req.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        contents = raw.decode("utf-16")
    else:
        contents = raw.decode("utf-8-sig")
    with tempfile.TemporaryDirectory() as temp:
        sanitized = Path(temp) / "requirements.txt"
        sanitized.write_text(contents, encoding="utf-8")
        subprocess.run([str(python_django), "-m", "pip", "install", "-r", str(sanitized)], check=True)
    subprocess.run([str(python_django), "-m", "pip", "check"], check=True)
    ok, detail = validar_django(python_django)
    if not ok:
        raise RuntimeError("El entorno Django nuevo no paso la comprobacion: " + detail[-500:])
    return python_django, detail


def main():
    verificar = "--verificar" in sys.argv[1:]
    try:
        python_vision = seleccionar_vision()
        print("Vision validada:", python_vision, flush=True)
        python_django = DJANGO / ".venv" / "Scripts" / "python.exe"
        python_django, detail = instalar_django_si_falta(
            python_vision, python_django, solo_verificar=verificar
        )
        print("HigieneSmart validado:", detail, flush=True)
        env = os.environ.copy()
        env["LIMPIA_PYTHON_VISION"] = str(python_vision)
        env["LIMPIA_PYTHON_DJANGO"] = str(python_django)
        print("Configuraciones comprobadas. PostgreSQL NO se ha modificado.", flush=True)
        programa = Path(__file__).resolve().parent / "lanzador_operativo.py"
        if not programa.is_file():
            raise RuntimeError("No se encontro lanzador_operativo.py dentro de LimpIA_Operativo.")
        argumentos = sys.argv[1:]
        if "--verificar" in argumentos or "--listar-perfiles" in argumentos:
            # Modo diagnostico: muestra el resultado en PowerShell y no abre ventanas.
            return subprocess.run(
                [str(python_vision), "-B", str(programa), *argumentos],
                cwd=str(VISION), env=env,
            ).returncode

        # La ventana grafica no debe depender de que permanezca abierto el .bat.
        # pythonw evita una consola persistente; los fallos se guardan en un log.
        pythonw = python_vision.with_name("pythonw.exe")
        ejecutable = pythonw if os.name == "nt" and pythonw.is_file() else python_vision
        logs = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "HigieneSmart" / "lanzador_operativo" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        ruta_log = logs / f"interfaz_{datetime.now():%Y%m%d_%H%M%S_%f}.log"
        with ruta_log.open("ab") as registro:
            proceso = subprocess.Popen(
                [str(ejecutable), "-B", str(programa), *argumentos],
                cwd=str(VISION), env=env,
                stdin=subprocess.DEVNULL, stdout=registro, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                close_fds=True,
            )
        time.sleep(1.0)
        if proceso.poll() is not None:
            detalle = ruta_log.read_text(encoding="utf-8", errors="replace")[-800:]
            raise RuntimeError("La interfaz no arranco. Log: " + str(ruta_log) + "\n" + detalle)
        print("Lanzador grafico iniciado sin consola permanente.", flush=True)
        print("Puedes cerrar PowerShell; mantén abierta la ventana del lanzador.", flush=True)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print("ERROR PREPARACION OPERATIVA:", exc, file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("Preparacion cancelada.")
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
