# -*- coding: utf-8 -*-
"""Rotacion explicita y unica de la credencial de droidcam-demo.

Ubicacion: capstone-vision/LimpIA_Operativo/rotar_token_droidcam_seguro.py
Ejecutar mediante HigieneSmart/.venv/Scripts/python.exe.

No modifica otros datos de negocio. Nunca escribe el token en archivos,
consola ni argumentos de linea de comandos. La GUI muestra el token hasta
que el operador lo guarda; despues deja de ser recuperable desde la BD.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
import secrets
import sys
import tkinter as tk
from tkinter import ttk, messagebox

VISION = Path(__file__).resolve().parent.parent
HIGIENE = VISION.parent.parent / "HigieneSmart"


def consultar_fuente():
    sys.path.insert(0, str(HIGIENE))
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    os.environ["DB_NAME"] = "capstone_db"

    import django
    django.setup()
    from django.db import connection
    from sistema.models import FuenteConteo

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        db_name = cursor.fetchone()[0]
    if db_name != "capstone_db":
        raise RuntimeError("Base diferente de capstone_db; no se modificara nada.")

    fuente = FuenteConteo.objects.select_related("bano").get(
        identificador="droidcam-demo"
    )
    if not fuente.activa or not fuente.bano.activo:
        raise RuntimeError("La fuente o el bano esta inactivo; no se modificara nada.")
    if fuente.bano_id != 1:
        raise RuntimeError(
            f"La fuente apunta al bano ID {fuente.bano_id}, no al ID 1 esperado "
            "por el emisor v0.5. No se modificara nada."
        )
    return fuente


def main():
    try:
        fuente = consultar_fuente()
    except Exception as exc:
        print("ERROR: no se actualizo la credencial:", exc)
        return 1

    from django.db import transaction
    from sistema.models import FuenteConteo

    # 32 bytes aleatorios -> credencial segura sin fecha de expiracion.
    nuevo_token = secrets.token_urlsafe(32)
    raiz = tk.Tk()
    raiz.title("LimpIA - Renovar token droidcam-demo")
    raiz.resizable(False, False)

    fondo = ttk.Frame(raiz, padding=18)
    fondo.pack(fill="both", expand=True)
    ttk.Label(fondo, text="Renovar credencial de DroidCam", font=("Segoe UI", 13, "bold")).pack(anchor="w")
    ttk.Label(fondo, text=f"Base: capstone_db | Fuente: droidcam-demo | Bano: {fuente.bano.nombre}").pack(anchor="w", pady=(8, 8))
    ttk.Label(
        fondo,
        text=("Esta accion reemplazara SOLO el hash de la credencial de droidcam-demo.\n"
              "El token anterior dejara de funcionar. Eventos, banos y alertas permanecen intactos."),
        justify="left"
    ).pack(anchor="w", pady=(0, 12))
    ttk.Label(fondo, text="1. Copia y guarda esta credencial en un lugar privado:").pack(anchor="w")
    entrada = ttk.Entry(fondo, width=65)
    entrada.insert(0, nuevo_token)
    entrada.configure(state="readonly")
    entrada.pack(anchor="w", pady=(5, 5))

    def copiar():
        raiz.clipboard_clear()
        raiz.clipboard_append(nuevo_token)
        raiz.update()
        mensaje.set("Token copiado. Pegalo y guardalo antes de continuar.")

    ttk.Button(fondo, text="Copiar token al portapapeles", command=copiar).pack(anchor="w", pady=(0, 10))
    ttk.Label(fondo, text="2. Pega aqui el token copiado para confirmar que lo tienes:").pack(anchor="w")
    repetido = ttk.Entry(fondo, width=65, show="*")
    repetido.pack(anchor="w", pady=(5, 8))
    guardado = tk.BooleanVar(value=False)
    ttk.Checkbutton(fondo, text="He guardado el token fuera de este programa.", variable=guardado).pack(anchor="w")
    mensaje = tk.StringVar(value="Todavia NO se ha cambiado la credencial en PostgreSQL.")
    ttk.Label(fondo, textvariable=mensaje, wraplength=470).pack(anchor="w", pady=(12, 8))
    botones = ttk.Frame(fondo)
    botones.pack(fill="x")
    resultado = {"guardado": False}

    def confirmar():
        if not guardado.get() or not hmac.compare_digest(repetido.get(), nuevo_token):
            messagebox.showwarning(
                "Falta confirmacion",
                "Debes pegar exactamente el token nuevo y confirmar que lo guardaste.",
                parent=raiz
            )
            return
        if not messagebox.askyesno(
            "Confirmar rotacion",
            "Se reemplazara la credencial actual de droidcam-demo en capstone_db.\n"
            "El token anterior dejara de servir. ¿Confirmas?", parent=raiz
        ):
            return
        try:
            with transaction.atomic():
                actual = FuenteConteo.objects.select_for_update().select_related("bano").get(pk=fuente.pk)
                if actual.identificador != "droidcam-demo" or actual.bano_id != 1 or not actual.activa or not actual.bano.activo:
                    raise RuntimeError("La fuente cambio durante la operacion; no se guardo nada.")
                actual.credencial_hash = hashlib.sha256(nuevo_token.encode("utf-8")).hexdigest()
                actual.save(update_fields=["credencial_hash"])
            resultado["guardado"] = True
            messagebox.showinfo(
                "Token configurado",
                "TOKEN NUEVO CONFIGURADO: OK\n"
                "Solo se cambio el hash de droidcam-demo.\n"
                "No se enviaron eventos ni se modificaron los conteos.",
                parent=raiz
            )
            raiz.destroy()
        except Exception as exc:
            messagebox.showerror("Sin cambios", f"No fue posible actualizar: {exc}", parent=raiz)

    ttk.Button(botones, text="Cancelar (sin cambios)", command=raiz.destroy).pack(side="left")
    ttk.Button(botones, text="Confirmar y guardar token nuevo", command=confirmar).pack(side="right")
    raiz.mainloop()
    if resultado["guardado"]:
        print("TOKEN NUEVO CONFIGURADO: OK")
        print("Eventos enviados: 0")
        print("Otras tablas de negocio: sin cambios")
        return 0
    print("OPERACION CANCELADA: no se modificaron datos")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
