from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from usuarios.models import Usuario
from .forms import LoginForm




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

                if usuario.rol == "SUPERVISOR":
                    return redirect("inicio_supervisor")

                if usuario.rol == "TRABAJADOR":
                    return redirect("inicio_trabajador")

                error_login = "El usuario no tiene un rol válido."
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
def inicio_trabajador(request):
    if request.user.rol != Usuario.Rol.TRABAJADOR:
        return redirect("inicio_supervisor")

    return render(request, "trabajador/inicio_trabajador.html")

@require_POST
def cerrar_sesion(request):
    logout(request)
    return redirect("login")