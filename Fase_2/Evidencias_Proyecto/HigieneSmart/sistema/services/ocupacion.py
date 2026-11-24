
from django.utils import timezone

from sistema.models import EventoConteo, ReferenciaOcupacion


def calcular_ocupacion(bano_id):
    """
    Calcula la ocupacion estimada desde la ultima
    referencia verificada para un baño.

    El saldo final se limita a cero si las salidas
    superan la ocupacion inicial mas las entradas.

    No modifica la base de datos.
    """

    referencia = (
        ReferenciaOcupacion.objects
        .filter(bano_id=bano_id)
        .order_by("-fecha_referencia", "-id")
        .first()
    )

    if referencia is None:
        return {
            "estado": "DESCONOCIDA",
            "ocupacion": None,
            "motivo": "Sin referencia inicial verificada.",
        }

    if not referencia.vigente:
        return {
            "estado": "DESCONOCIDA",
            "ocupacion": None,
            "motivo": "La ultima referencia fue invalidada.",
        }

    ahora = timezone.now()

    if referencia.fecha_referencia > ahora:
        return {
            "estado": "DESCONOCIDA",
            "ocupacion": None,
            "motivo": "La referencia tiene una fecha futura.",
        }

    eventos = (
        EventoConteo.objects
        .filter(
            bano_id=bano_id,
            fecha_evento__gt=referencia.fecha_referencia,
            fecha_evento__lte=ahora,
        )
        .values_list("tipo", flat=True)
    )

    entradas = 0
    salidas = 0

    for tipo in eventos:
        if tipo == EventoConteo.Tipo.ENTRADA:
            entradas += 1
        elif tipo == EventoConteo.Tipo.SALIDA:
            salidas += 1

    saldo = referencia.ocupacion_inicial + entradas - salidas
    salidas_excedentes = max(0, -saldo)

    if salidas_excedentes:
        motivo = (
            "Estimacion ajustada: se detectaron "
            f"{salidas_excedentes} salidas sin entradas "
        )
    else:
        motivo = None

    return {
        # Compatible con el dashboard actual.
        "estado": "CONOCIDA",
        "ocupacion": max(0, saldo),
        "motivo": motivo,
        "entradas": entradas,
        "salidas": salidas,
        "estimacion_ajustada": salidas_excedentes > 0,
        "salidas_excedentes": salidas_excedentes,
    }
