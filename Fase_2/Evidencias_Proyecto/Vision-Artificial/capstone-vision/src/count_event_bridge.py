
"""
Puente entre el contador H5.2 y la cola SQLite.

Recibe los CountEvent confirmados y los registra
sin modificar la logica de deteccion o tracking.

No utiliza camara ni realiza solicitudes HTTP.
"""

from datetime import datetime, timezone

from .count_event_recorder import CountEventRecorder


def guardar_eventos_confirmados(
    eventos,
    registrador: CountEventRecorder,
    *,
    reloj_utc=None,
):
    """
    Guarda los eventos confirmados por H5.2.

    Captura una fecha real con zona horaria para
    cada movimiento y delega su persistencia
    al registrador.

    Si SQLite falla, la excepcion se propaga:
    no se informa un guardado inexistente.
    """

    if not isinstance(registrador, CountEventRecorder):
        raise TypeError(
            "Se requiere un CountEventRecorder."
        )

    if reloj_utc is None:
        reloj_utc = lambda: datetime.now(timezone.utc)

    guardados = []

    for evento in eventos:
        fecha = reloj_utc()

        if (
            not isinstance(fecha, datetime)
            or fecha.tzinfo is None
            or fecha.utcoffset() is None
        ):
            raise ValueError(
                "El reloj debe devolver una fecha "
                "con zona horaria."
            )

        datos = registrador.registrar(
            evento,
            ocurrido_en=fecha,
        )

        guardados.append(datos)

    return tuple(guardados)
