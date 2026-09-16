from django.contrib import admin

from .models import AsignacionBano, Bano


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