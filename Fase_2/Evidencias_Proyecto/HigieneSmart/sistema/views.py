from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str, force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.core.mail import send_mail
from django.urls import reverse
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from usuarios.models import Usuario
from .forms import LoginForm, BanoForm, TrabajadorForm, ActivarCuentaForm, FinalizarLimpiezaForm
from .models import Bano, AsignacionBano, Alerta, IntervencionLimpieza, EventoConteo, FuenteConteo



def login_view(request):
    error_login = None

    if request.method == "POST":
        form = LoginForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]

            usuario = authenticate(
                request,
                username=email,
                password=password,
            )

            if usuario is not None:
                login(request, usuario)

                if usuario.rol == Usuario.Rol.SUPERVISOR:
                    return redirect("inicio_supervisor")

                if usuario.rol == Usuario.Rol.TRABAJADOR:
                    return redirect("inicio_trabajador")

                error_login = "El usuario no tiene un rol válido."

            else:
                usuario_existente = Usuario.objects.filter(
                    email__iexact=email
                ).first()

                if (
                    usuario_existente is not None
                    and usuario_existente.has_usable_password()
                    and usuario_existente.check_password(password)
                    and not usuario_existente.is_active
                ):
                    error_login = (
                        "Tu acceso al sistema ha sido deshabilitado. "
                        "Contacta con tu supervisor."
                    )
                else:
                    error_login = "Correo o contraseña incorrectos."

    else:
        form = LoginForm()

    return render(
        request,
        "compartido/login.html",
        {
            "form": form,
            "error_login": error_login,
        },
    )

@login_required(login_url="login")
def inicio_supervisor(request):
    if request.user.rol != Usuario.Rol.SUPERVISOR:
        return redirect("inicio_trabajador")

    hoy = timezone.localdate()

    total_banos = Bano.objects.filter(
        activo=True,
    ).count()

    trabajadores_activos = Usuario.objects.filter(
        rol=Usuario.Rol.TRABAJADOR,
        is_active=True,
    ).count()

    alertas_pendientes = Alerta.objects.filter(
        estado=Alerta.Estado.PENDIENTE,
    ).count()

    limpiezas_en_curso = IntervencionLimpieza.objects.filter(
        fecha_fin__isnull=True,
        alerta__estado=Alerta.Estado.EN_PROCESO,
    ).count()

    limpiezas_hoy = IntervencionLimpieza.objects.filter(
        fecha_fin__date=hoy,
    ).count()

    ultimas_intervenciones = (
        IntervencionLimpieza.objects
        .select_related(
            "trabajador",
            "bano",
        )
        .filter(
            fecha_fin__isnull=False,
        )
        .order_by("-fecha_fin")[:5]
    )

    
    # Conteo del baño asociado a DroidCam Demo.
    conteo_demo = None

    fuente_demo = (
        FuenteConteo.objects
        .select_related("bano")
        .filter(
            identificador="droidcam-demo",
            activa=True,
            bano__activo=True,
        )
        .first()
    )

    if fuente_demo is not None:
        bano_demo = fuente_demo.bano

        ultima_limpieza = (
            IntervencionLimpieza.objects
            .filter(
                bano=bano_demo,
                fecha_fin__isnull=False,
            )
            .order_by("-fecha_fin")
            .values_list("fecha_fin", flat=True)
            .first()
        )

        inicio_ciclo = bano_demo.inicio_ciclo_conteo

        if ultima_limpieza and ultima_limpieza > inicio_ciclo:
            inicio_ciclo = ultima_limpieza

        entradas_actuales = EventoConteo.objects.filter(
            bano=bano_demo,
            tipo=EventoConteo.Tipo.ENTRADA,
            fecha_evento__gt=inicio_ciclo,
        ).count()

        conteo_demo = {
            "bano": bano_demo.nombre,
            "entradas": entradas_actuales,
            "limite": bano_demo.umbral_entradas,
        }

    return render(
        request,
        "supervisor/inicio_supervisor.html",
        {
            "total_banos": total_banos,
            "trabajadores_activos": trabajadores_activos,
            "alertas_pendientes": alertas_pendientes,
            "limpiezas_en_curso": limpiezas_en_curso,
            "limpiezas_hoy": limpiezas_hoy,
            "ultimas_intervenciones": ultimas_intervenciones,
            "conteo_demo": conteo_demo,
        },
    )


@login_required(login_url="login")
def gestion_banos(request):

    if request.user.rol != Usuario.Rol.SUPERVISOR:
        return redirect("inicio_trabajador")

    # Obtener todos los baños registrados.
    banos = list(
        Bano.objects.all().order_by("id")
    )

    # Calcular las entradas del ciclo actual de cada baño.
    for bano in banos:

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

        # Determinar desde cuándo contar entradas.
        inicio_ciclo = bano.inicio_ciclo_conteo

        if (
            ultima_limpieza is not None
            and ultima_limpieza > inicio_ciclo
        ):
            inicio_ciclo = ultima_limpieza

        # Contar las entradas del ciclo actual.
        bano.entradas_ciclo = (
            EventoConteo.objects
            .filter(
                bano=bano,
                tipo=EventoConteo.Tipo.ENTRADA,
                fecha_evento__gt=inicio_ciclo,
            )
            .count()
        )

    return render(
        request,
        "supervisor/banos.html",
        {
            "banos": banos,
        },
    )


@login_required(login_url="login")
def gestion_trabajadores(request):
    if request.user.rol != Usuario.Rol.SUPERVISOR:
        return redirect("inicio_trabajador")

    trabajadores = Usuario.objects.filter(
        rol=Usuario.Rol.TRABAJADOR
    ).order_by("id")

    return render(
        request,
        "supervisor/trabajadores.html",
        {
            "trabajadores": trabajadores,
        },
    )

@login_required(login_url="login")
def agregar_trabajador(request):
    if request.user.rol != Usuario.Rol.SUPERVISOR:
        return redirect("inicio_trabajador")

    if request.method == "POST":
        form = TrabajadorForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"]

            # Generar username interno a partir del correo.
            base_username = email.split("@")[0][:140]
            username = base_username
            contador = 1

            while Usuario.objects.filter(username=username).exists():
                username = f"{base_username}_{contador}"
                contador += 1

            trabajador = Usuario(
                username=username,
                email=email,
                rol=Usuario.Rol.TRABAJADOR,
                is_active=False,
            )

            # El trabajador todavía no tiene una contraseña.
            trabajador.set_unusable_password()
            trabajador.save()

            # Generar identificador y token seguro de activación.
            uid = urlsafe_base64_encode(
                force_bytes(trabajador.pk)
            )

            token = default_token_generator.make_token(
                trabajador
            )

            # Construir la URL completa de activación.
            ruta_activacion = reverse(
                "activar_cuenta",
                kwargs={
                    "uidb64": uid,
                    "token": token,
                },
            )

            url_activacion = request.build_absolute_uri(
                ruta_activacion
            )

            # En desarrollo, este correo aparecerá en la terminal.
            send_mail(
                subject="Activa tu cuenta de LimpIA",
                message=(
                    "Has sido registrado como trabajador en LimpIA.\n\n"
                    "Para configurar tu contraseña y activar tu cuenta, "
                    "ingresa al siguiente enlace:\n\n"
                    f"{url_activacion}\n\n"
                    "Si no esperabas esta invitación, puedes ignorar este mensaje."
                ),
                from_email=None,
                recipient_list=[trabajador.email],
                fail_silently=False,
            )

            return redirect("gestion_trabajadores")

    else:
        form = TrabajadorForm()

    return render(
        request,
        "supervisor/agregar_trabajador.html",
        {
            "form": form,
        },
    )

@require_POST
@login_required(login_url="login")
def cambiar_estado_trabajador(request, trabajador_id):
    if request.user.rol != Usuario.Rol.SUPERVISOR:
        return redirect("inicio_trabajador")

    trabajador = get_object_or_404(
        Usuario,
        id=trabajador_id,
        rol=Usuario.Rol.TRABAJADOR,
    )

    # Una cuenta pendiente de activación todavía no puede reactivarse,
    # porque aún no tiene una contraseña utilizable.
    if not trabajador.has_usable_password():
        return redirect("gestion_trabajadores")

    trabajador.is_active = not trabajador.is_active
    trabajador.save(update_fields=["is_active"])

    return redirect("gestion_trabajadores")

@login_required(login_url="login")
def crear_bano(request):
    if request.user.rol != Usuario.Rol.SUPERVISOR:
        return redirect("inicio_trabajador")

    if request.method == "POST":
        form = BanoForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect("gestion_banos")
    else:
        form = BanoForm()

    return render(
        request,
        "supervisor/crear_bano.html",
        {
            "form": form,
        },
    )

@login_required(login_url="login")
def editar_bano(request, bano_id):
    if request.user.rol != Usuario.Rol.SUPERVISOR:
        return redirect("inicio_trabajador")

    bano = get_object_or_404(Bano, id=bano_id)

    if request.method == "POST":
        form = BanoForm(request.POST, instance=bano)

        if form.is_valid():
            form.save()
            return redirect("gestion_banos")
    else:
        form = BanoForm(instance=bano)

    return render(
        request,
        "supervisor/editar_bano.html",
        {
            "form": form,
            "bano": bano,
        },
    )


@login_required(login_url="login")
def inicio_trabajador(request):
    if request.user.rol != Usuario.Rol.TRABAJADOR:
        return redirect("inicio_supervisor")

    asignacion = (
        AsignacionBano.objects
        .filter(
            trabajador=request.user,
            activa=True,
        )
        .select_related("bano")
        .first()
    )

    alerta_pendiente = None

    if asignacion is not None:
        alerta_pendiente = (
            Alerta.objects
            .filter(
                bano=asignacion.bano,
                estado=Alerta.Estado.PENDIENTE,
            )
            .order_by("fecha_creacion")
            .first()
        )

    intervencion_activa = (
        IntervencionLimpieza.objects
        .filter(
            trabajador=request.user,
            fecha_fin__isnull=True,
            alerta__estado=Alerta.Estado.EN_PROCESO,
        )
        .select_related(
            "alerta",
            "bano",
        )
        .first()
    )

    return render(
        request,
        "trabajador/inicio_trabajador.html",
        {
            "asignacion": asignacion,
            "alerta_pendiente": alerta_pendiente,
            "intervencion_activa": intervencion_activa,
        },
    )

@login_required(login_url="login")
def gestion_asignaciones(request):
    if request.user.rol != Usuario.Rol.SUPERVISOR:
        return redirect("inicio_trabajador")

    trabajadores = Usuario.objects.filter(
        rol=Usuario.Rol.TRABAJADOR,
        is_active=True,
    ).order_by("id")

    banos = Bano.objects.filter(
        activo=True,
    ).order_by("id")

    asignaciones_activas = AsignacionBano.objects.filter(
        activa=True,
    ).select_related(
        "trabajador",
        "bano",
    )

    asignaciones_por_trabajador = {
        asignacion.trabajador_id: asignacion
        for asignacion in asignaciones_activas
    }

    banos_ocupados = {
        asignacion.bano_id: asignacion.trabajador
        for asignacion in asignaciones_activas
    }

    trabajadores_con_limpieza = set(
        IntervencionLimpieza.objects.filter(
            fecha_fin__isnull=True,
            alerta__estado=Alerta.Estado.EN_PROCESO,
        ).values_list(
            "trabajador_id",
            flat=True,
        )
    )

    filas_asignaciones = []

    for trabajador in trabajadores:
        asignacion_actual = asignaciones_por_trabajador.get(
            trabajador.id
        )

        opciones_banos = []

        for bano in banos:
            ocupante = banos_ocupados.get(bano.id)

            disponible = (
                ocupante is None
                or ocupante.id == trabajador.id
            )

            seleccionado = (
                asignacion_actual is not None
                and asignacion_actual.bano_id == bano.id
            )

            opciones_banos.append(
                {
                    "bano": bano,
                    "disponible": disponible,
                    "ocupante": ocupante,
                    "seleccionado": seleccionado,
                }
            )

        filas_asignaciones.append(
            {
                "trabajador": trabajador,
                "asignacion": asignacion_actual,
                "opciones_banos": opciones_banos,
                "limpieza_en_curso": (
                    trabajador.id in trabajadores_con_limpieza
                ),
            }
        )

    return render(
        request,
        "supervisor/asignaciones.html",
        {
            "filas_asignaciones": filas_asignaciones,
        },
    )

@require_POST
@login_required(login_url="login")
def guardar_asignacion(request, trabajador_id):
    if request.user.rol != Usuario.Rol.SUPERVISOR:
        return redirect("inicio_trabajador")

    trabajador = get_object_or_404(
        Usuario,
        id=trabajador_id,
        rol=Usuario.Rol.TRABAJADOR,
        is_active=True,
    )

    intervencion_en_curso = IntervencionLimpieza.objects.filter(
        trabajador=trabajador,
        fecha_fin__isnull=True,
        alerta__estado=Alerta.Estado.EN_PROCESO,
    ).exists()

    if intervencion_en_curso:
        return redirect("gestion_asignaciones")

    bano_id = request.POST.get("bano_id")

    with transaction.atomic():
        asignacion_actual = (
            AsignacionBano.objects
            .select_for_update()
            .filter(
                trabajador=trabajador,
                activa=True,
            )
            .first()
        )

        # El supervisor seleccionó "Sin asignar".
        if not bano_id:
            if asignacion_actual:
                asignacion_actual.activa = False
                asignacion_actual.fecha_fin = timezone.now()

                asignacion_actual.save(
                    update_fields=[
                        "activa",
                        "fecha_fin",
                    ]
                )

            return redirect("gestion_asignaciones")

        bano = get_object_or_404(
            Bano.objects.select_for_update(),
            id=bano_id,
            activo=True,
        )

        # Si seleccionó nuevamente su mismo baño,
        # no hay nada que modificar.
        if (
            asignacion_actual
            and asignacion_actual.bano_id == bano.id
        ):
            return redirect("gestion_asignaciones")

        # Comprobar en backend que otro trabajador
        # no tenga actualmente ese baño.
        bano_ocupado = AsignacionBano.objects.filter(
            bano=bano,
            activa=True,
        ).exclude(
            trabajador=trabajador,
        ).exists()

        if bano_ocupado:
            return redirect("gestion_asignaciones")

        # Cerramos la asignación anterior para conservar
        # su historial.
        if asignacion_actual:
            asignacion_actual.activa = False
            asignacion_actual.fecha_fin = timezone.now()

            asignacion_actual.save(
                update_fields=[
                    "activa",
                    "fecha_fin",
                ]
            )

        # Creamos la nueva asignación.
        AsignacionBano.objects.create(
            trabajador=trabajador,
            bano=bano,
            activa=True,
        )

    return redirect("gestion_asignaciones")

def activar_cuenta(request, uidb64, token):
    try:
        usuario_id = force_str(urlsafe_base64_decode(uidb64))

        usuario = Usuario.objects.get(
            id=usuario_id,
            rol=Usuario.Rol.TRABAJADOR,
        )

    except (TypeError, ValueError, OverflowError, Usuario.DoesNotExist):
        usuario = None

    if usuario is None:
        return render(
            request,
            "compartido/activacion_invalida.html",
        )

    if not default_token_generator.check_token(usuario, token):
        return render(
            request,
            "compartido/activacion_invalida.html",
        )

    if request.method == "POST":
        form = ActivarCuentaForm(usuario, request.POST)

        if form.is_valid():
            form.save()

            usuario.is_active = True
            usuario.save(update_fields=["is_active"])

            return redirect("login")

    else:
        form = ActivarCuentaForm(usuario)

    return render(
        request,
        "compartido/activar_cuenta.html",
        {
            "form": form,
            "usuario": usuario,
        },
    )

@require_POST
@login_required(login_url="login")
def iniciar_limpieza(request, alerta_id):
    if request.user.rol != Usuario.Rol.TRABAJADOR:
        return redirect("inicio_supervisor")

    with transaction.atomic():
        alerta = get_object_or_404(
            Alerta.objects.select_for_update(),
            id=alerta_id,
            estado=Alerta.Estado.PENDIENTE,
        )

        asignacion = (
            AsignacionBano.objects
            .select_for_update()
            .filter(
                trabajador=request.user,
                bano=alerta.bano,
                activa=True,
            )
            .first()
        )

        # El trabajador solo puede iniciar una limpieza
        # del baño que tiene actualmente asignado.
        if asignacion is None:
            return redirect("inicio_trabajador")

        # Evita crear más de una intervención
        # para la misma alerta.
        if IntervencionLimpieza.objects.filter(
            alerta=alerta
        ).exists():
            return redirect("inicio_trabajador")

        IntervencionLimpieza.objects.create(
            alerta=alerta,
            trabajador=request.user,
            bano=alerta.bano,
        )

        alerta.estado = Alerta.Estado.EN_PROCESO
        alerta.save(
            update_fields=["estado"]
        )

    return redirect("inicio_trabajador")

@require_POST
@login_required(login_url="login")
def finalizar_limpieza(request, intervencion_id):
    if request.user.rol != Usuario.Rol.TRABAJADOR:
        return redirect("inicio_supervisor")

    intervencion = get_object_or_404(
        IntervencionLimpieza.objects.select_related(
            "alerta",
            "bano",
        ),
        id=intervencion_id,
        trabajador=request.user,
        fecha_fin__isnull=True,
        alerta__estado=Alerta.Estado.EN_PROCESO,
    )

    form = FinalizarLimpiezaForm(
        request.POST,
        request.FILES,
    )

    if not form.is_valid():
        return redirect("inicio_trabajador")

    with transaction.atomic():
        intervencion = (
            IntervencionLimpieza.objects
            .select_for_update()
            .select_related("alerta")
            .get(
                id=intervencion.id,
                trabajador=request.user,
                fecha_fin__isnull=True,
                alerta__estado=Alerta.Estado.EN_PROCESO,
            )
        )

        intervencion.evidencia = form.cleaned_data["evidencia"]
        intervencion.fecha_fin = timezone.now()

        intervencion.save(
            update_fields=[
                "evidencia",
                "fecha_fin",
            ]
        )

        alerta = intervencion.alerta
        alerta.estado = Alerta.Estado.ATENDIDA

        alerta.save(
            update_fields=["estado"]
        )

    return redirect("inicio_trabajador")

@require_POST
def cerrar_sesion(request):
    logout(request)
    return redirect("login")

@login_required(login_url="login")
def historial_limpiezas(request):
    if request.user.rol != Usuario.Rol.SUPERVISOR:
        return redirect("inicio_trabajador")

    intervenciones = (
        IntervencionLimpieza.objects
        .select_related(
            "trabajador",
            "bano",
            "alerta",
        )
        .order_by("-fecha_inicio")
    )

    trabajador_id = request.GET.get("trabajador")
    bano_id = request.GET.get("bano")
    estado = request.GET.get("estado")
    fecha_desde = request.GET.get("fecha_desde")
    fecha_hasta = request.GET.get("fecha_hasta")

    if trabajador_id:
        intervenciones = intervenciones.filter(
            trabajador_id=trabajador_id
        )

    if bano_id:
        intervenciones = intervenciones.filter(
            bano_id=bano_id
        )

    if estado == "FINALIZADA":
        intervenciones = intervenciones.filter(
            fecha_fin__isnull=False
        )

    elif estado == "EN_PROCESO":
        intervenciones = intervenciones.filter(
            fecha_fin__isnull=True
        )

    fecha_desde_valida = parse_date(fecha_desde) if fecha_desde else None
    fecha_hasta_valida = parse_date(fecha_hasta) if fecha_hasta else None

    if fecha_desde_valida:
        intervenciones = intervenciones.filter(
            fecha_inicio__date__gte=fecha_desde_valida
        )

    if fecha_hasta_valida:
        intervenciones = intervenciones.filter(
            fecha_inicio__date__lte=fecha_hasta_valida
        )

    trabajadores = (
        Usuario.objects
        .filter(
            rol=Usuario.Rol.TRABAJADOR,
            intervenciones_limpieza__isnull=False,
        )
        .distinct()
        .order_by("email")
    )

    banos = (
        Bano.objects
        .filter(
            intervenciones_limpieza__isnull=False,
        )
        .distinct()
        .order_by("nombre")
    )

    return render(
        request,
        "supervisor/historial_limpiezas.html",
        {
            "intervenciones": intervenciones,
            "trabajadores": trabajadores,
            "banos": banos,
            "filtro_trabajador": trabajador_id or "",
            "filtro_bano": bano_id or "",
            "filtro_estado": estado or "",
            "filtro_fecha_desde": fecha_desde or "",
            "filtro_fecha_hasta": fecha_hasta or "",
        },
    )


# =========================
# GESTIÓN DE ALERTAS
# =========================

@login_required(login_url="login")
def gestion_alertas(request):
    if request.user.rol != Usuario.Rol.SUPERVISOR:
        return redirect("inicio_trabajador")

    alertas = (
        Alerta.objects
        .select_related("bano")
        .order_by("-fecha_creacion")
    )

    banos = Bano.objects.filter(
        activo=True,
    ).order_by("nombre", "id")

    return render(
        request,
        "supervisor/alertas.html",
        {
            "alertas": alertas,
            "banos": banos,
        },
    )


# =========================
# CREAR ALERTA MANUAL
# =========================

@require_POST
@login_required(login_url="login")
def crear_alerta_manual(request):
    if request.user.rol != Usuario.Rol.SUPERVISOR:
        return redirect("inicio_trabajador")

    bano_id = (request.POST.get("bano") or "").strip()
    motivo = (request.POST.get("motivo") or "").strip()

    # Validar que se haya seleccionado un baño.
    if not bano_id.isdecimal():
        messages.error(
            request,
            "Debes seleccionar un baño válido.",
        )
        return redirect("gestion_alertas")

    # El motivo es obligatorio.
    if not motivo:
        messages.error(
            request,
            "Debes indicar el motivo de la alerta.",
        )
        return redirect("gestion_alertas")

    # Respetar el máximo definido en el modelo Alerta.
    if len(motivo) > 200:
        messages.error(
            request,
            "El motivo no puede superar los 200 caracteres.",
        )
        return redirect("gestion_alertas")

    with transaction.atomic():

        # Bloquear el baño durante la comprobación
        # para evitar alertas duplicadas simultáneas.
        bano = get_object_or_404(
            Bano.objects.select_for_update(),
            id=int(bano_id),
            activo=True,
        )

        # No crear otra alerta si ya existe una
        # pendiente o en proceso para este baño.
        alerta_existente = Alerta.objects.filter(
            bano=bano,
            estado__in=[
                Alerta.Estado.PENDIENTE,
                Alerta.Estado.EN_PROCESO,
            ],
        ).exists()

        if alerta_existente:
            messages.warning(
                request,
                "Este baño ya tiene una alerta pendiente "
                "o en proceso.",
            )
            return redirect("gestion_alertas")

        # Crear la alerta con estado PENDIENTE.
        Alerta.objects.create(
            bano=bano,
            motivo=motivo,
            estado=Alerta.Estado.PENDIENTE,
        )

    messages.success(
        request,
        "La alerta de limpieza se creó correctamente.",
    )

    return redirect("gestion_alertas")



# =========================
# CONFIGURAR LÍMITE DE ENTRADAS
# =========================

@require_POST
@login_required(login_url="login")
def guardar_limite_entradas(request):
    if request.user.rol != Usuario.Rol.SUPERVISOR:
        return redirect("inicio_trabajador")

    bano_id = (request.POST.get("bano") or "").strip()
    limite_texto = (
        request.POST.get("limite_entradas") or ""
    ).strip()

    # Validar que se haya seleccionado un baño.
    if not bano_id.isdecimal():
        messages.error(
            request,
            "Debes seleccionar un baño válido.",
        )
        return redirect("gestion_alertas")

    # Un campo vacío significa que el baño
    # queda sin límite automático configurado.
    if not limite_texto:
        limite = None
    else:
        try:
            limite = int(limite_texto)
        except ValueError:
            messages.error(
                request,
                "El límite debe ser un número entero.",
            )
            return redirect("gestion_alertas")

        # Validar que el límite sea positivo
        # y compatible con PostgreSQL.
        if limite < 1 or limite > 2147483647:
            messages.error(
                request,
                "El límite debe ser un número entero "
                "entre 1 y 2147483647.",
            )
            return redirect("gestion_alertas")

    # Buscar el baño y comprobar que esté activo.
    bano = get_object_or_404(
        Bano,
        id=int(bano_id),
        activo=True,
    )

    # Guardar el límite configurado.
    bano.umbral_entradas = limite
    bano.save(update_fields=["umbral_entradas"])

    if limite is None:
        messages.success(
            request,
            f"Se desactivó el límite automático "
            f"del baño {bano.nombre}.",
        )
    else:
        messages.success(
            request,
            f"El límite del baño {bano.nombre} "
            f"se configuró en {limite} entradas.",
        )

    return redirect("gestion_alertas")



# ==========================================
# DATOS DEL DASHBOARD EN TIEMPO CASI REAL
# ==========================================

@require_GET
@login_required(login_url="login")
def datos_dashboard_supervisor(request):

    if request.user.rol != Usuario.Rol.SUPERVISOR:
        return JsonResponse(
            {"error": "No autorizado"},
            status=403,
        )

    # Obtener las alertas pendientes actuales.
    alertas_pendientes = Alerta.objects.filter(
        estado=Alerta.Estado.PENDIENTE,
    ).count()

    # Obtener las limpiezas en curso.
    limpiezas_en_curso = IntervencionLimpieza.objects.filter(
        fecha_fin__isnull=True,
        alerta__estado=Alerta.Estado.EN_PROCESO,
    ).count()

    # Contar las limpiezas finalizadas hoy.
    hoy = timezone.localdate()

    limpiezas_hoy = IntervencionLimpieza.objects.filter(
        fecha_fin__date=hoy,
    ).count()

    # Buscar el baño conectado a DroidCam Demo.
    fuente = (
        FuenteConteo.objects
        .select_related("bano")
        .filter(
            identificador="droidcam-demo",
            activa=True,
            bano__activo=True,
        )
        .first()
    )

    conteo_demo = None

    if fuente is not None:
        bano = fuente.bano

        # Buscar la última limpieza terminada.
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

        # Calcular el inicio del ciclo actual.
        inicio_ciclo = bano.inicio_ciclo_conteo

        if ultima_limpieza and ultima_limpieza > inicio_ciclo:
            inicio_ciclo = ultima_limpieza

        # Contar entradas del ciclo actual.
        entradas = EventoConteo.objects.filter(
            bano=bano,
            tipo=EventoConteo.Tipo.ENTRADA,
            fecha_evento__gt=inicio_ciclo,
        ).count()

        conteo_demo = {
            "bano": bano.nombre,
            "entradas": entradas,
            "limite": bano.umbral_entradas,
        }

    respuesta = JsonResponse({
        "alertas_pendientes": alertas_pendientes,
        "limpiezas_en_curso": limpiezas_en_curso,
        "limpiezas_hoy": limpiezas_hoy,
        "conteo_demo": conteo_demo,
    })

    respuesta["Cache-Control"] = "no-store"

    return respuesta


# ==========================================
# DATOS ACTUALIZADOS DEL PANEL DEL TRABAJADOR
# ==========================================

@require_GET
@login_required(login_url="login")
def datos_inicio_trabajador(request):

    # Solo los trabajadores pueden consultar estos datos.
    if request.user.rol != Usuario.Rol.TRABAJADOR:
        return JsonResponse(
            {"error": "No autorizado"},
            status=403,
        )

    # Buscar la asignación activa del trabajador.
    asignacion = (
        AsignacionBano.objects
        .filter(
            trabajador=request.user,
            activa=True,
        )
        .first()
    )

    # Buscar la alerta pendiente de su baño asignado.
    alerta_pendiente_id = None

    if asignacion is not None:
        alerta_pendiente_id = (
            Alerta.objects
            .filter(
                bano_id=asignacion.bano_id,
                estado=Alerta.Estado.PENDIENTE,
            )
            .order_by("fecha_creacion")
            .values_list("id", flat=True)
            .first()
        )

    # Buscar una limpieza que el trabajador tenga en curso.
    intervencion_activa_id = (
        IntervencionLimpieza.objects
        .filter(
            trabajador=request.user,
            fecha_fin__isnull=True,
            alerta__estado=Alerta.Estado.EN_PROCESO,
        )
        .values_list("id", flat=True)
        .first()
    )

    respuesta = JsonResponse({
        "asignacion_id": asignacion.id if asignacion else None,
        "alerta_pendiente_id": alerta_pendiente_id,
        "intervencion_activa_id": intervencion_activa_id,
    })

    respuesta["Cache-Control"] = "no-store"

    return respuesta


# ==========================================
# DATOS ACTUALIZADOS DE GESTIÓN DE BAÑOS
# ==========================================

@require_GET
@login_required(login_url="login")
def datos_gestion_banos(request):

    if request.user.rol != Usuario.Rol.SUPERVISOR:
        return JsonResponse(
            {"error": "No autorizado"},
            status=403,
        )

    datos_banos = []

    for bano in Bano.objects.all().order_by("id"):

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

        # Calcular el inicio del ciclo actual.
        inicio_ciclo = bano.inicio_ciclo_conteo

        if ultima_limpieza and ultima_limpieza > inicio_ciclo:
            inicio_ciclo = ultima_limpieza

        # Contar las entradas del ciclo.
        entradas = EventoConteo.objects.filter(
            bano=bano,
            tipo=EventoConteo.Tipo.ENTRADA,
            fecha_evento__gt=inicio_ciclo,
        ).count()

        datos_banos.append({
            "id": bano.id,
            "entradas": entradas,
            "limite": bano.umbral_entradas,
        })

    respuesta = JsonResponse({
        "banos": datos_banos,
    })

    respuesta["Cache-Control"] = "no-store"

    return respuesta
