from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from sistema.models import EventoConteo


def obtener_eventos_entrada():
    return EventoConteo.objects.filter(
        tipo=EventoConteo.Tipo.ENTRADA,
    )


def obtener_total_usos():
    return obtener_eventos_entrada().count()


def obtener_usos_hoy():
    hoy = timezone.localdate()

    return obtener_eventos_entrada().filter(
        fecha_evento__date=hoy,
    ).count()


def obtener_usos_por_bano(fecha_desde=None, fecha_hasta=None):
    eventos = obtener_eventos_entrada()

    if fecha_desde:
        eventos = eventos.filter(
            fecha_evento__date__gte=fecha_desde,
        )

    if fecha_hasta:
        eventos = eventos.filter(
            fecha_evento__date__lte=fecha_hasta,
        )

    return (
        eventos
        .values(
            "bano_id",
            "bano__nombre",
        )
        .annotate(
            usos=Count("id"),
        )
        .order_by(
            "bano__nombre",
        )
    )


def obtener_usos_por_dia(fecha_desde=None, fecha_hasta=None):
    eventos = obtener_eventos_entrada()

    if fecha_desde:
        eventos = eventos.filter(
            fecha_evento__date__gte=fecha_desde,
        )

    if fecha_hasta:
        eventos = eventos.filter(
            fecha_evento__date__lte=fecha_hasta,
        )

    return (
        eventos
        .annotate(
            fecha=TruncDate("fecha_evento"),
        )
        .values(
            "fecha",
        )
        .annotate(
            usos=Count("id"),
        )
        .order_by(
            "fecha",
        )
    )