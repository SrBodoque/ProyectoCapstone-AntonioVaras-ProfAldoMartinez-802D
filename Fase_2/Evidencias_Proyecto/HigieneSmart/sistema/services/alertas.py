
from django.db import transaction

from sistema.models import (
    Alerta,
    Bano,
    EventoConteo,
    IntervencionLimpieza,
)


def verificar_alerta_por_entradas(bano_id):
    """
    Comprueba si un baño alcanzó su límite de entradas.

    Si corresponde, crea una alerta de limpieza.

    Devuelve la alerta creada o None si no
    es necesario generar una nueva.
    """

    with transaction.atomic():

        # Bloquear el baño para evitar que dos
        # comprobaciones creen alertas simultáneas.
        bano = (
            Bano.objects
            .select_for_update()
            .filter(
                id=bano_id,
                activo=True,
            )
            .first()
        )

        # El baño no existe o está inactivo.
        if bano is None:
            return None

        # El supervisor no configuró un límite.
        if bano.umbral_entradas is None:
            return None

        # Evitar alertas duplicadas.
        alerta_abierta = Alerta.objects.filter(
            bano=bano,
            estado__in=[
                Alerta.Estado.PENDIENTE,
                Alerta.Estado.EN_PROCESO,
            ],
        ).exists()

        if alerta_abierta:
            return None

        # Buscar la última limpieza finalizada.
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

        # Contar solamente eventos de ENTRADA.
        entradas = EventoConteo.objects.filter(
            bano=bano,
            tipo=EventoConteo.Tipo.ENTRADA,
        )

        # Si el baño ya tuvo limpiezas, contar
        # solo las entradas posteriores a la última.
        if ultima_limpieza is not None:
            entradas = entradas.filter(
                fecha_evento__gt=ultima_limpieza,
            )

        total_entradas = entradas.count()

        # Todavía no alcanza el límite.
        if total_entradas < bano.umbral_entradas:
            return None

        # Se alcanzó el límite: crear la alerta.
        alerta = Alerta.objects.create(
            bano=bano,
            motivo=(
                "Límite de entradas alcanzado: "
                f"{total_entradas} entradas "
                f"(límite: {bano.umbral_entradas})."
            ),
            estado=Alerta.Estado.PENDIENTE,
        )

        return alerta
