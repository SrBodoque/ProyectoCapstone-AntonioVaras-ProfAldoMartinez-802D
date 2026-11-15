
"""
Adaptador de eventos del contador hacia la API Django.

No realiza solicitudes HTTP.
No accede a la base de datos.
No modifica el motor de conteo.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from .count_engine import CountEvent


TIPOS_DJANGO = {
    "IN": "ENTRADA",
    "OUT": "SALIDA",
}


def adaptar_evento_conteo(
    evento: CountEvent,
    *,
    fuente: str,
    referencia_externa: UUID | None = None,
    ocurrido_en: datetime | None = None,
) -> dict:
    """
    Convierte un CountEvent en el JSON esperado por Django.

    referencia_externa y ocurrido_en pueden inyectarse
    para realizar pruebas con datos controlados.
    """

    # 1. Validar el evento del contador.
    if not isinstance(evento, CountEvent):
        raise TypeError("Se requiere un CountEvent.")

    if evento.direction not in TIPOS_DJANGO:
        raise ValueError(
            "La direccion debe ser IN u OUT."
        )

    # 2. Validar el identificador de la fuente.
    if (
        not isinstance(fuente, str)
        or not fuente
        or fuente != fuente.strip()
        or len(fuente) > 80
    ):
        raise ValueError(
            "La fuente debe tener un identificador valido."
        )

    # 3. Asignar un UUID4 al movimiento.
    identificador = (
        uuid4()
        if referencia_externa is None
        else referencia_externa
    )

    if (
        not isinstance(identificador, UUID)
        or identificador.version != 4
    ):
        raise ValueError(
            "La referencia externa debe ser un UUID4."
        )

    # 4. Capturar la fecha real en UTC.
    fecha = (
        datetime.now(timezone.utc)
        if ocurrido_en is None
        else ocurrido_en
    )

    if (
        not isinstance(fecha, datetime)
        or fecha.tzinfo is None
        or fecha.utcoffset() is None
    ):
        raise ValueError(
            "La fecha debe incluir zona horaria."
        )

    # 5. Crear el objeto compatible con Django.
    return {
        "fuente": fuente,
        "tipo": TIPOS_DJANGO[evento.direction],
        "referencia_externa": str(identificador),
        "ocurrido_en": (
            fecha.astimezone(timezone.utc).isoformat()
        ),
    }
