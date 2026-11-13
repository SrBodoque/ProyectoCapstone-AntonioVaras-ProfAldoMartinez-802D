
from sistema.models import (
    EventoConteo,
    IntervencionLimpieza,
)

from sistema.services.conteos_diarios import (
    obtener_conteos_diarios,
)

from sistema.services.ocupacion import (
    calcular_ocupacion,
)


def obtener_resumen_bano(bano):
    """
    Reune los indicadores de conteo de un baño.

    No modifica registros ni reinicia contadores.
    """

    # 1. Identificar el ciclo de limpieza actual.
    ultima_limpieza = (
        IntervencionLimpieza.objects
        .filter(
            bano=bano,
            fecha_fin__isnull=False,
        )
        .order_by("-fecha_fin")
        .values_list("fecha_fin", flat=True)
        .first()
    )

    inicio_ciclo = bano.inicio_ciclo_conteo

    if (
        ultima_limpieza is not None
        and ultima_limpieza > inicio_ciclo
    ):
        inicio_ciclo = ultima_limpieza

    # 2. Contar solo las entradas para limpieza.
    entradas_ciclo = EventoConteo.objects.filter(
        bano=bano,
        tipo=EventoConteo.Tipo.ENTRADA,
        fecha_evento__gt=inicio_ciclo,
    ).count()

    # 3. Obtener entradas y salidas de la jornada.
    jornada = obtener_conteos_diarios(bano.id)

    # 4. Calcular la ocupacion estimada.
    ocupacion = calcular_ocupacion(bano.id)

    # 5. Reunir los resultados.
    return {
        "bano_id": bano.id,
        "bano": bano.nombre,
        "entradas_ciclo": entradas_ciclo,
        "limite": bano.umbral_entradas,
        "entradas_jornada": jornada["entradas"],
        "salidas_jornada": jornada["salidas"],
        "inicio_jornada": jornada["inicio_jornada"],
        "ocupacion_estado": ocupacion["estado"],
        "ocupacion_estimada": ocupacion["ocupacion"],
        "ocupacion_motivo": ocupacion["motivo"],
    }
