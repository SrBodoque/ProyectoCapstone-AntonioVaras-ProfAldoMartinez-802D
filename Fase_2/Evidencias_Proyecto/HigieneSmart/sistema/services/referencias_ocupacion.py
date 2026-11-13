
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from sistema.models import Bano, ReferenciaOcupacion


def registrar_verificacion_bano_vacio(
    *,
    bano_id,
    supervisor,
    observacion="",
):
    """
    Registra una referencia de ocupacion cero.

    Solo debe ejecutarse cuando un supervisor
    haya confirmado que el baño esta vacio.

    No elimina eventos historicos ni reinicia
    el contador del ciclo de limpieza.
    """

    # 1. Comprobar que el usuario es supervisor.
    if (
        not getattr(supervisor, "is_authenticated", False)
        or not supervisor.is_active
        or supervisor.rol != "SUPERVISOR"
    ):
        raise PermissionDenied(
            "Solo un supervisor activo puede "
            "verificar la ocupacion."
        )

    # 2. Validar la observacion opcional.
    if not isinstance(observacion, str):
        raise ValueError(
            "La observacion debe ser texto."
        )

    observacion = observacion.strip()

    if len(observacion) > 250:
        raise ValueError(
            "La observacion no puede superar "
            "los 250 caracteres."
        )

    # 3. Registrar el cambio de forma segura.
    with transaction.atomic():

        bano = (
            Bano.objects
            .select_for_update()
            .get(
                id=bano_id,
                activo=True,
            )
        )

        ahora = timezone.now()

        # 4. Conservar las referencias anteriores,
        # pero marcarlas como no vigentes.
        ReferenciaOcupacion.objects.filter(
            bano=bano,
            vigente=True,
        ).update(
            vigente=False,
            fecha_invalidacion=ahora,
            motivo_invalidacion=(
                "Reemplazada por una nueva "
                "verificacion de baño vacio."
            ),
        )

        # 5. Crear la nueva referencia verificada.
        referencia = ReferenciaOcupacion.objects.create(
            bano=bano,
            ocupacion_inicial=0,
            fecha_referencia=ahora,
            verificada_por=supervisor,
            vigente=True,
            observacion=observacion,
        )

        return referencia
