from django.urls import path
from . import views

urlpatterns = [
    path("", views.login_view, name="login"),
    path("activar-cuenta/<uidb64>/<token>/", views.activar_cuenta, name="activar_cuenta"),
    path("supervisor/", views.inicio_supervisor, name="inicio_supervisor"),
    path("supervisor/banos/", views.gestion_banos, name="gestion_banos"),
    path("supervisor/banos/crear/", views.crear_bano, name="crear_bano"),
    path("supervisor/banos/<int:bano_id>/editar/", views.editar_bano, name="editar_bano"),
    path("supervisor/trabajadores/", views.gestion_trabajadores, name="gestion_trabajadores"),
    path("supervisor/trabajadores/agregar/", views.agregar_trabajador, name="agregar_trabajador"),
    path("supervisor/trabajadores/<int:trabajador_id>/estado/", views.cambiar_estado_trabajador, name="cambiar_estado_trabajador"),
    path("supervisor/asignaciones/", views.gestion_asignaciones, name="gestion_asignaciones"),
    path("supervisor/asignaciones/<int:trabajador_id>/guardar/", views.guardar_asignacion, name="guardar_asignacion"),
    path("trabajador/", views.inicio_trabajador, name="inicio_trabajador"),
    path("trabajador/alertas/<int:alerta_id>/iniciar/", views.iniciar_limpieza, name="iniciar_limpieza"),
    path("trabajador/limpiezas/<int:intervencion_id>/finalizar/", views.finalizar_limpieza, name="finalizar_limpieza"),
    path("logout/", views.cerrar_sesion, name="cerrar_sesion"),
]
