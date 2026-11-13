
"""
Configuracion opcional del almacenamiento de eventos.

Por defecto NO activa SQLite.

Cuando se habilita, guarda los eventos en:
LOCALAPPDATA/limpIAvision/eventos.sqlite3

No realiza solicitudes HTTP.
"""

import os

from pathlib import Path

from .count_event_recorder import CountEventRecorder
from .event_outbox import EventOutbox


def crear_registrador_desde_entorno(*, variables=None):
    """
    Crea un registrador solo cuando
    LIMPIA_GUARDAR_CONTEOS=1.

    Devuelve None cuando esta desactivado.
    """

    if variables is None:
        variables = os.environ

    # 1. Desactivado por defecto.
    if variables.get("LIMPIA_GUARDAR_CONTEOS", "0") != "1":
        return None

    # 2. Utilizar una carpeta de datos local,
    # fuera del repositorio Git.
    localappdata = variables.get("LOCALAPPDATA")

    if not localappdata:
        raise ValueError(
            "No se encontro LOCALAPPDATA."
        )

    carpeta_base = Path(localappdata)

    if not carpeta_base.is_absolute():
        raise ValueError(
            "LOCALAPPDATA debe ser una ruta absoluta."
        )

    # 3. Validar la fuente de conteo.
    fuente = variables.get(
        "LIMPIA_FUENTE_CONTEO",
        "droidcam-demo",
    )

    if (
        not isinstance(fuente, str)
        or not fuente
        or fuente != fuente.strip()
        or len(fuente) > 80
    ):
        raise ValueError(
            "Identificador de fuente invalido."
        )

    # 4. Preparar el archivo SQLite.
    carpeta_datos = carpeta_base / "limpIAvision"

    carpeta_datos.mkdir(
        parents=True,
        exist_ok=True,
    )

    ruta_db = carpeta_datos / "eventos.sqlite3"

    # 5. Crear la cola y su registrador.
    cola = EventOutbox(ruta_db)

    return CountEventRecorder(
        cola,
        fuente=fuente,
    )
