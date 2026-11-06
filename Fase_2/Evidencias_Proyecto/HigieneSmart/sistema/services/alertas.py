
from django.db import transaction

from sistema.models import (
    Alerta,
    Bano,
    EventoConteo,
    IntervencionLimpieza,
)


# ==========================================
# VERIFICAR ALERTAS POR LÍMITE DE ENTRADAS
# ==========================================

def verificar_alerta_por_entradas(bano_id, fecha_evento=None):
    """
    Comprueba si un baño alcanzó su límite de entradas
    durante el ciclo de limpieza actual.

    Si corresponde, crea una alerta PENDIENTE.

    fecha_evento permite ignorar eventos atrasados
    que pertenecen a ciclos anteriores.

    Devuelve la alerta creada o None.
    """

    with transaction.atomic():

        # 1. Bloquear el baño para evitar
        # comprobaciones simultáneas.

        bano = (
            Bano.objects
            .select_for_update()
            .filter(
                id=bano_id,
                activo=True,
            )
            .first()
        )

        if bano is None:
            return None

        # 2. Verificar si tiene límite configurado.

        if bano.umbral_entradas is None:
            return None

        # 3. Evitar generar alertas duplicadas.

        alerta_abierta = Alerta.objects.filter(
            bano=bano,
            estado__in=[
                Alerta.Estado.PENDIENTE,
                Alerta.Estado.EN_PROCESO,
            ],
        ).exists()

        if alerta_abierta:
            return None

        # 4. Buscar la última limpieza finalizada.

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

        # 5. Determinar el inicio del ciclo actual.

        inicio_ciclo = bano.inicio_ciclo_conteo

        if (
            ultima_limpieza is not None
            and ultima_limpieza > inicio_ciclo
        ):
            inicio_ciclo = ultima_limpieza

        # 6. Ignorar eventos atrasados que
        # pertenecen a un ciclo anterior.

        if (
            fecha_evento is not None
            and fecha_evento <= inicio_ciclo
        ):
            return None

        # 7. Contar solamente las entradas
        # posteriores al inicio del ciclo.

        total_entradas = EventoConteo.objects.filter(
            bano=bano,
            tipo=EventoConteo.Tipo.ENTRADA,
            fecha_evento__gt=inicio_ciclo,
        ).count()

        # 8. Comprobar si alcanzó el límite.

        if total_entradas < bano.umbral_entradas:
            return None

        # 9. Crear una alerta automática.

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
