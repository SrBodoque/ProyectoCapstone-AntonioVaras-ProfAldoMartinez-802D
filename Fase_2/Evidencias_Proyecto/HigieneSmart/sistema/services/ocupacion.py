
from django.utils import timezone

from sistema.models import EventoConteo, ReferenciaOcupacion


def calcular_ocupacion(bano_id):
    """
    Calcula la ocupacion estimada desde la ultima
    referencia verificada para un baño.

    La ocupacion nunca baja de cero.

    Si hay salidas excedentes, mantiene el calculo
    funcionando, pero informa que fue ajustado.

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

    ocupacion = referencia.ocupacion_inicial

    eventos = (
        EventoConteo.objects
        .filter(
            bano_id=bano_id,
            fecha_evento__gt=referencia.fecha_referencia,
            fecha_evento__lte=ahora,
        )
        .order_by("fecha_evento", "id")
        .values_list("tipo", flat=True)
    )

    entradas = 0
    salidas = 0
    salidas_excedentes = 0

    for tipo in eventos:
        if tipo == EventoConteo.Tipo.ENTRADA:
            entradas += 1
            ocupacion += 1

        elif tipo == EventoConteo.Tipo.SALIDA:
            salidas += 1

            if ocupacion > 0:
                ocupacion -= 1
            else:
                # Nunca mostrar ocupacion negativa.
                # Conservar un aviso del desajuste.
                salidas_excedentes += 1

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
        "ocupacion": ocupacion,
        "motivo": motivo,
        "entradas": entradas,
        "salidas": salidas,
        "estimacion_ajustada": salidas_excedentes > 0,
        "salidas_excedentes": salidas_excedentes,
    }
