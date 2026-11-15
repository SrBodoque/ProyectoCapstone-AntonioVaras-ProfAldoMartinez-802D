
from datetime import datetime, time, timedelta

from django.utils import timezone

from sistema.models import EventoConteo


# Hora de inicio de la jornada operativa.
HORA_INICIO_JORNADA = 6


def obtener_conteos_diarios(bano_id, ahora=None):
    """
    Cuenta entradas y salidas de la jornada actual.

    - Utiliza la zona horaria configurada en Django.
    - No modifica ni elimina eventos.
    - No reinicia la ocupacion ni el ciclo de limpieza.
    """

    if ahora is None:
        ahora = timezone.now()

    zona = timezone.get_default_timezone()
    ahora_local = timezone.localtime(ahora, zona)

    fecha_jornada = ahora_local.date()

    # Antes de las 06:00 seguimos en la jornada anterior.
    if ahora_local.hour < HORA_INICIO_JORNADA:
        fecha_jornada -= timedelta(days=1)

    inicio = datetime.combine(
        fecha_jornada,
        time(hour=HORA_INICIO_JORNADA),
        tzinfo=zona,
    )

    fin = datetime.combine(
        fecha_jornada + timedelta(days=1),
        time(hour=HORA_INICIO_JORNADA),
        tzinfo=zona,
    )

    # Consultar solo eventos que ya ocurrieron.
    eventos = EventoConteo.objects.filter(
        bano_id=bano_id,
        fecha_evento__gte=inicio,
        fecha_evento__lt=fin,
        fecha_evento__lte=ahora,
    )

    entradas = eventos.filter(
        tipo=EventoConteo.Tipo.ENTRADA,
    ).count()

    salidas = eventos.filter(
        tipo=EventoConteo.Tipo.SALIDA,
    ).count()

    return {
        "entradas": entradas,
        "salidas": salidas,
        "inicio_jornada": inicio.isoformat(),
        "fin_jornada": fin.isoformat(),
    }
