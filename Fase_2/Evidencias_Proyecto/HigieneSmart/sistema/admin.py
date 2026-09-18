from django.contrib import admin

from .models import (
    Alerta,
    AsignacionBano,
    Bano,
    EventoConteo,
    IntervencionLimpieza,
)


@admin.register(Bano)
class BanoAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "ubicacion", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre", "ubicacion")


@admin.register(AsignacionBano)
class AsignacionBanoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "trabajador",
        "bano",
        "activa",
        "fecha_asignacion",
        "fecha_fin",
    )

    list_filter = (
        "activa",
        "bano",
    )

    search_fields = (
        "trabajador__email",
        "trabajador__username",
        "bano__nombre",
        "bano__ubicacion",
    )

    readonly_fields = (
        "fecha_asignacion",
    )


@admin.register(Alerta)
class AlertaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "bano",
        "motivo",
        "estado",
        "fecha_creacion",
    )

    list_filter = (
        "estado",
        "bano",
    )

    search_fields = (
        "bano__nombre",
        "bano__ubicacion",
        "motivo",
    )

    readonly_fields = (
        "fecha_creacion",
    )


@admin.register(IntervencionLimpieza)
class IntervencionLimpiezaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "alerta",
        "trabajador",
        "bano",
        "fecha_inicio",
        "fecha_fin",
        "duracion_formateada",
    )

    list_filter = (
        "bano",
    )

    search_fields = (
        "trabajador__email",
        "trabajador__username",
        "bano__nombre",
        "bano__ubicacion",
    )

    readonly_fields = (
        "fecha_inicio",
        "duracion_formateada",
    )

    @admin.display(description="Duración")
    def duracion_formateada(self, obj):
        if obj.duracion is None:
            return "En curso"

        total_segundos = int(obj.duracion.total_seconds())

        minutos, segundos = divmod(total_segundos, 60)
        horas, minutos = divmod(minutos, 60)

        if horas:
            return f"{horas} h {minutos} min"

        return f"{minutos} min {segundos} s"


@admin.register(EventoConteo)
class EventoConteoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "bano",
        "tipo",
        "fecha_evento",
        "origen",
        "referencia_externa",
        "fecha_registro",
    )

    list_filter = (
        "tipo",
        "origen",
        "bano",
    )

    search_fields = (
        "bano__nombre",
        "bano__ubicacion",
        "referencia_externa",
    )

    readonly_fields = (
        "fecha_registro",
    )

    ordering = (
        "-fecha_evento",
    )