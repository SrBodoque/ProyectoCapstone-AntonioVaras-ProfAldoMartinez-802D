from django.urls import path
from . import views

urlpatterns = [
    path("", views.login_view, name="login"),
    path("supervisor/", views.inicio_supervisor, name="inicio_supervisor"),
    path("trabajador/", views.inicio_trabajador, name="inicio_trabajador"),
    path("logout/", views.cerrar_sesion, name="cerrar_sesion"),      
]
