
from datetime import datetime, time, timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from sistema.models import EventoConteo


def obtener_historial_conteos(
    bano_id,
    fecha_inicio,
    fecha_fin,
):
    """
    Obtiene entradas y salidas diarias de un baño.

    - Usa días calendario (00:00 a 00:00).
    - Respeta la zona horaria de Django.
    - Incluye fechas sin movimientos con cero.
    - Devuelve los días más recientes primero.
    - No modifica PostgreSQL.
    """

    if fecha_inicio > fecha_fin:
        raise ValueError(
            "La fecha inicial no puede ser posterior "
            "a la fecha final."
        )

    if (fecha_fin - fecha_inicio).days > 366:
        raise ValueError(
            "El período máximo de consulta es de 367 días."
        )

    zona = timezone.get_default_timezone()
    ahora = timezone.now()

    if fecha_fin > timezone.localdate(ahora, zona):
        raise ValueError(
            "No se pueden consultar fechas futuras."
        )

    # Límites del intervalo en hora local.
    inicio = timezone.make_aware(
        datetime.combine(fecha_inicio, time.min),
        zona,
    )

    fin_exclusivo = timezone.make_aware(
        datetime.combine(
            fecha_fin + timedelta(days=1),
            time.min,
        ),
        zona,
    )

    # Agrupar los movimientos que ya existen
    # en PostgreSQL por fecha local.
    registros = (
        EventoConteo.objects
        .filter(
            bano_id=bano_id,
            fecha_evento__gte=inicio,
            fecha_evento__lt=fin_exclusivo,
            fecha_evento__lte=ahora,
        )
        .annotate(
            fecha=TruncDate(
                "fecha_evento",
                tzinfo=zona,
            )
        )
        .values("fecha")
        .annotate(
            entradas=Count(
                "id",
                filter=Q(
                    tipo=EventoConteo.Tipo.ENTRADA
                ),
            ),
            salidas=Count(
                "id",
                filter=Q(
                    tipo=EventoConteo.Tipo.SALIDA
                ),
            ),
        )
    )

    # Convertir los resultados en un diccionario.
    movimientos_por_fecha = {
        registro["fecha"]: registro
        for registro in registros
    }

    historial = []

    # Incluir todos los días, aunque no existan
    # eventos almacenados para algunos de ellos.
    fecha = fecha_inicio

    while fecha <= fecha_fin:
        registro = movimientos_por_fecha.get(fecha)

        entradas = (
            registro["entradas"]
            if registro else 0
        )

        salidas = (
            registro["salidas"]
            if registro else 0
        )

        historial.append({
            "fecha": fecha,
            "entradas": entradas,
            "salidas": salidas,
            "total_movimientos": entradas + salidas,
        })

        fecha += timedelta(days=1)

    # Mostrar primero las fechas más recientes.
    historial.reverse()

    return historial
