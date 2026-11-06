
import hashlib
import hmac
import json

from datetime import timedelta
from uuid import UUID

from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Bano, EventoConteo, FuenteConteo


# ==========================================
# API - RECEPCIÓN DE EVENTOS DE CONTEO
# ==========================================

@csrf_exempt
@require_POST
def recibir_evento_conteo(request):
    """
    Recibe una entrada confirmada por visión artificial.

    - Autentica la fuente mediante Bearer token.
    - Valida los datos recibidos.
    - Asocia la entrada al baño configurado.
    - Evita registrar eventos duplicados.
    """

    # 1. Comprobar el formato de la solicitud.

    if request.content_type != "application/json":
        return JsonResponse(
            {"error": "Se requiere Content-Type application/json."},
            status=415,
        )

    if len(request.body) > 4096:
        return JsonResponse(
            {"error": "La solicitud supera el tamaño permitido."},
            status=413,
        )

    try:
        datos = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "El contenido JSON no es válido."},
            status=400,
        )

    if not isinstance(datos, dict):
        return JsonResponse(
            {"error": "Se esperaba un objeto JSON."},
            status=400,
        )

    # 2. Obtener la fuente y la credencial.

    identificador = datos.get("fuente")
    autorizacion = request.headers.get("Authorization", "")

    esquema, separador, credencial = autorizacion.partition(" ")

    if (
        esquema.lower() != "bearer"
        or not separador
        or not credencial.strip()
    ):
        return JsonResponse(
            {"error": "Credencial de autenticación requerida."},
            status=401,
        )

    if not isinstance(identificador, str) or not identificador:
        return JsonResponse(
            {"error": "Debes indicar una fuente válida."},
            status=400,
        )

    fuente = FuenteConteo.objects.filter(
        identificador=identificador,
    ).first()

    if fuente is None or not fuente.credencial_hash:
        return JsonResponse(
            {"error": "Fuente o credencial no autorizada."},
            status=401,
        )

    hash_recibido = hashlib.sha256(
        credencial.encode("utf-8")
    ).hexdigest()

    if not hmac.compare_digest(
        hash_recibido,
        fuente.credencial_hash,
    ):
        return JsonResponse(
            {"error": "Fuente o credencial no autorizada."},
            status=401,
        )

    if not fuente.activa:
        return JsonResponse(
            {"error": "La fuente de conteo está desactivada."},
            status=403,
        )

    # 3. Validar el tipo de evento.

    if datos.get("tipo") != EventoConteo.Tipo.ENTRADA:
        return JsonResponse(
            {"error": "Solamente se aceptan eventos ENTRADA."},
            status=400,
        )

    # 4. Validar el identificador único.

    referencia_original = datos.get("referencia_externa")

    if not isinstance(referencia_original, str):
        return JsonResponse(
            {"error": "La referencia externa debe ser un UUID."},
            status=400,
        )

    try:
        uuid_evento = UUID(referencia_original)
    except (ValueError, AttributeError):
        return JsonResponse(
            {"error": "La referencia externa no es un UUID válido."},
            status=400,
        )

    if (
        uuid_evento.version != 4
        or str(uuid_evento) != referencia_original.lower()
    ):
        return JsonResponse(
            {"error": "Se requiere un UUID versión 4 válido."},
            status=400,
        )

    referencia = str(uuid_evento)

    # 5. Validar la fecha de ocurrencia.

    ocurrido_en = datos.get("ocurrido_en")

    if not isinstance(ocurrido_en, str):
        return JsonResponse(
            {"error": "Debes indicar la fecha de la entrada."},
            status=400,
        )

    try:
        fecha_evento = parse_datetime(ocurrido_en)
    except ValueError:
        fecha_evento = None

    if fecha_evento is None or timezone.is_naive(fecha_evento):
        return JsonResponse(
            {"error": "La fecha debe incluir zona horaria."},
            status=400,
        )

    if fecha_evento > timezone.now() + timedelta(minutes=5):
        return JsonResponse(
            {"error": "La fecha del evento está demasiado adelantada."},
            status=400,
        )

    # 6. Guardar el evento de manera segura.

    with transaction.atomic():

        # Bloquear el baño mientras se procesa
        # la entrada para serializar las operaciones.
        bano = Bano.objects.select_for_update().get(
            id=fuente.bano_id,
        )

        if not bano.activo:
            return JsonResponse(
                {"error": "El baño asociado está inactivo."},
                status=403,
            )

        # La referencia externa tiene UNIQUE
        # en PostgreSQL: un evento solo se guarda una vez.
        evento, creado = EventoConteo.objects.get_or_create(
            referencia_externa=referencia,
            defaults={
                "bano": bano,
                "fuente": fuente,
                "tipo": EventoConteo.Tipo.ENTRADA,
                "origen": EventoConteo.Origen.VISION,
                "fecha_evento": fecha_evento,
            },
        )

        if not creado:

            # El mismo UUID debe corresponder
            # exactamente al mismo evento.
            coincide = (
                evento.bano_id == bano.id
                and evento.fuente_id == fuente.id
                and evento.tipo == EventoConteo.Tipo.ENTRADA
                and evento.origen == EventoConteo.Origen.VISION
                and evento.fecha_evento == fecha_evento
            )

            if not coincide:
                return JsonResponse(
                    {
                        "error": (
                            "La referencia ya existe "
                            "con datos diferentes."
                        ),
                    },
                    status=409,
                )

    # 7. Responder al programa de visión artificial.

    if creado:
        return JsonResponse(
            {
                "estado": "creado",
                "referencia_externa": referencia,
                "bano_id": bano.id,
            },
            status=201,
        )

    return JsonResponse(
        {
            "estado": "ya_registrado",
            "referencia_externa": referencia,
            "bano_id": bano.id,
        },
        status=200,
    )
