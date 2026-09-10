from django.contrib import admin
from .models import Bano


@admin.register(Bano)
class BanoAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "ubicacion", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre", "ubicacion")