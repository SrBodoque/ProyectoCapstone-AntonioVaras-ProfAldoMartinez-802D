# -*- coding: utf-8 -*-
"""Emisor operativo de limpIAvision. Credencial por stdin; nunca persistida.

La opcion --comprobar NO envia HTTP ni escribe en PostgreSQL o SQLite.
El modo real se invoca solo tras confirmacion de usuario en el lanzador.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
from contextlib import closing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cola", type=Path, required=True)
    parser.add_argument("--vision", type=Path, required=True)
    parser.add_argument("--comprobar", action="store_true")
    parser.add_argument("--stop-file", type=Path, help="Marca de parada privada de esta sesion")
    args = parser.parse_args()

    # El token no figura en argumentos, entorno, archivos ni salida.
    token = sys.stdin.readline().rstrip("\r\n")
    if not token or token != token.strip():
        raise ValueError("Credencial vacia o invalida")

    ruta = args.cola.resolve(strict=True)
    if not ruta.is_file():
        raise ValueError("La cola SQLite debe ser un archivo existente")
    vision = args.vision.resolve(strict=True)
    if not (vision / "src" / "event_outbox.py").is_file():
        raise ValueError("No existe el codigo de la cola de vision")
    django_root = vision.parent.parent / "HigieneSmart"
    if not (django_root / "manage.py").is_file():
        raise ValueError("No se encontro HigieneSmart")
    sys.path.insert(0, str(django_root))
    sys.path.insert(0, str(vision))

    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    os.environ["DB_NAME"] = "capstone_db"
    import django
    django.setup()
    from django.db import connection
    from sistema.models import Bano, FuenteConteo
    from src.event_outbox import EventOutbox
    from src.django_event_sender import DjangoEventSender

    with connection.cursor() as cur:
        cur.execute("SELECT current_database()")
        database = cur.fetchone()[0]
    if database != "capstone_db":
        raise RuntimeError("La conexion Django no corresponde a capstone_db")

    fuente = FuenteConteo.objects.select_related("bano").get(
        identificador="droidcam-demo")
    if (not fuente.activa or not fuente.bano.activo
            or fuente.bano_id != 1):
        raise RuntimeError("Fuente o bano no autorizado para esta instalacion")
    if not fuente.credencial_hash or not hmac.compare_digest(
            hashlib.sha256(token.encode("utf-8")).hexdigest(),
            fuente.credencial_hash):
        raise RuntimeError("Credencial incorrecta. No se enviaron eventos")

    with closing(sqlite3.connect(ruta.as_uri() + "?mode=ro", uri=True, timeout=10)) as db:
        pendientes = [json.loads(row[0]) for row in db.execute(
            "SELECT payload_json FROM eventos WHERE estado='PENDIENTE' ORDER BY creado_en, rowid")]
        conflictos = db.execute("SELECT count(*) FROM eventos WHERE estado='CONFLICTO'").fetchone()[0]
    if pendientes:
        raise RuntimeError(
            f"Hay {len(pendientes)} eventos pendientes anteriores. "
            "Revise la cola antes de iniciar una sesion operativa")
    if conflictos:
        raise RuntimeError(
            f"Hay {conflictos} conflictos en la cola. "
            "Revise los conflictos antes de operar")

    if args.comprobar:
        print("REVISION OPERATIVA OK: capstone_db, droidcam-demo, cola sin pendientes")
        print("HTTP: 0 | SQLite: solo lectura")
        return 0

    if args.stop_file is None:
        raise ValueError("Falta marca de parada para operacion real")
    stop_file = args.stop_file.resolve()
    if stop_file.exists():
        raise RuntimeError("La marca de parada ya existe; no iniciar emisor")

    # Una sola instancia de nuestro emisor por cola. La cerradura se libera
    # automaticamente al terminar el proceso, incluso si se interrumpe.
    if os.name != "nt":
        raise RuntimeError("El bloqueo exclusivo del emisor requiere Windows")
    import msvcrt
    lock = ruta.parent / ".emisor_operativo.lock"
    with open(lock, "a+b") as file_lock:
        file_lock.seek(0, 2)
        if file_lock.tell() == 0:
            file_lock.write(b"x")
            file_lock.flush()
        file_lock.seek(0)
        try:
            msvcrt.locking(file_lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError("Ya existe otro emisor operativo usando esta cola") from exc
        cola = EventOutbox(ruta)
        sender = DjangoEventSender(
            cola, url="http://127.0.0.1:8000/api/v1/eventos-conteo/",
            token=token, timeout=5)
        token = ""
        print("EMISOR ACTIVO | capstone_db | droidcam-demo | Ctrl+C para detener", flush=True)
        try:
            while True:
                entries = cola.listar_pendientes()
                if entries:
                    if any(row.get("fuente") != "droidcam-demo"
                           or row.get("tipo") not in ("ENTRADA", "SALIDA")
                           for row in entries):
                        raise RuntimeError("Cola con eventos no autorizados; envio detenido")
                    result = sender.procesar_pendientes(max_eventos=1)
                    if result["entregados"]:
                        print("Evento entregado a Django", flush=True)
                    if result["conflictos"] or result["detenidos"]:
                        raise RuntimeError("Evento no entregado; se conservo el estado para revision")
                elif stop_file.exists():
                    print("PARADA SOLICITADA: cola vacia; emisor detenido", flush=True)
                    break
                # Dormir poco para reaccionar pronto a la parada.
                time.sleep(0.5 if stop_file.exists() else 3)
        except KeyboardInterrupt:
            print("EMISOR DETENIDO", flush=True)
        finally:
            file_lock.seek(0)
            msvcrt.locking(file_lock.fileno(), msvcrt.LK_UNLCK, 1)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("ERROR EMISOR:", exc, file=sys.stderr, flush=True)
        raise SystemExit(1)
