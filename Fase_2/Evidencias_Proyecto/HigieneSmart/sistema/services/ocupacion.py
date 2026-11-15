
from django.utils import timezone

from sistema.models import EventoConteo, ReferenciaOcupacion


def calcular_ocupacion(bano_id):
    """
    Calcula la ocupacion estimada desde la ultima
    referencia registrada para un baño.

    Estados posibles:
    - CONOCIDA
    - DESCONOCIDA
    - INCONSISTENTE

    No modifica la base de datos.
    """

    # Buscar la referencia mas reciente del baño.
    referencia = (
        ReferenciaOcupacion.objects
        .filter(bano_id=bano_id)
        .order_by("-fecha_referencia", "-id")
        .first()
    )

    # Sin referencia inicial no podemos calcular
    # una ocupacion confiable.
    if referencia is None:
        return {
            "estado": "DESCONOCIDA",
            "ocupacion": None,
            "motivo": "Sin referencia inicial verificada.",
        }

    # No utilizar referencias invalidadas.
    if not referencia.vigente:
        return {
            "estado": "DESCONOCIDA",
            "ocupacion": None,
            "motivo": "La ultima referencia fue invalidada.",
        }

    # Evitar utilizar referencias con fecha futura.
    if referencia.fecha_referencia > timezone.now():
        return {
            "estado": "DESCONOCIDA",
            "ocupacion": None,
            "motivo": "La referencia tiene una fecha futura.",
        }

    # Comenzar desde la ocupacion verificada.
    ocupacion = referencia.ocupacion_inicial

    # Consultar entradas y salidas posteriores
    # a esa referencia, en orden cronologico.
    eventos = (
        EventoConteo.objects
        .filter(
            bano_id=bano_id,
            fecha_evento__gt=referencia.fecha_referencia,
            fecha_evento__lte=timezone.now(),
        )
        .order_by("fecha_evento", "id")
        .values_list("tipo", flat=True)
    )

    entradas = 0
    salidas = 0
    inconsistente = False

    for tipo in eventos:
        if tipo == EventoConteo.Tipo.ENTRADA:
            entradas += 1
            ocupacion += 1

        elif tipo == EventoConteo.Tipo.SALIDA:
            salidas += 1
            ocupacion -= 1

            # Una ocupacion negativa indica una
            # contradiccion en los eventos.
            if ocupacion < 0:
                inconsistente = True

    if inconsistente:
        return {
            "estado": "INCONSISTENTE",
            "ocupacion": None,
            "motivo": (
                "Los eventos registrados producen "
                "una ocupacion negativa."
            ),
            "entradas": entradas,
            "salidas": salidas,
        }

    return {
        "estado": "CONOCIDA",
        "ocupacion": ocupacion,
        "motivo": None,
        "entradas": entradas,
        "salidas": salidas,
    }
