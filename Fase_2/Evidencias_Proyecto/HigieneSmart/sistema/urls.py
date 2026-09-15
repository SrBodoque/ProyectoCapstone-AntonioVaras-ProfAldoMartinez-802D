from django.urls import path
from . import views

urlpatterns = [
    path("", views.login_view, name="login"),
    path("supervisor/", views.inicio_supervisor, name="inicio_supervisor"),
    path("supervisor/banos/", views.gestion_banos, name="gestion_banos"),
    path("supervisor/banos/crear/", views.crear_bano, name="crear_bano"),
    path("supervisor/banos/<int:bano_id>/editar/", views.editar_bano, name="editar_bano"),
    path("trabajador/", views.inicio_trabajador, name="inicio_trabajador"),
    path("logout/", views.cerrar_sesion, name="cerrar_sesion"),
]
