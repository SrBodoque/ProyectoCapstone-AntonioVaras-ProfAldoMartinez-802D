from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str, force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.core.mail import send_mail
from django.urls import reverse

from usuarios.models import Usuario
from .forms import LoginForm, BanoForm, TrabajadorForm, ActivarCuentaForm
from .models import Bano


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

    return render(request, "supervisor/inicio_supervisor.html")

@login_required(login_url="login")
def gestion_banos(request):
    if request.user.rol != Usuario.Rol.SUPERVISOR:
        return redirect("inicio_trabajador")

    banos = Bano.objects.all().order_by("id")

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
                subject="Activa tu cuenta de HigieneSmart",
                message=(
                    "Has sido registrado como trabajador en HigieneSmart.\n\n"
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

    return render(request, "trabajador/inicio_trabajador.html")

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
def cerrar_sesion(request):
    logout(request)
    return redirect("login")

