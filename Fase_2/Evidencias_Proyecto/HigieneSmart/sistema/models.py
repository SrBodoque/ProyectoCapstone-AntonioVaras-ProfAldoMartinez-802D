from django.db import models

from django.conf import settings
from django.db.models import Q


class Bano(models.Model):
    nombre = models.CharField(max_length=100)
    ubicacion = models.CharField(max_length=150)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} - {self.ubicacion}"


class AsignacionBano(models.Model):
    trabajador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asignaciones_banos",
        limit_choices_to={"rol": "TRABAJADOR"},
    )

    bano = models.ForeignKey(
        Bano,
        on_delete=models.PROTECT,
        related_name="asignaciones",
    )

    fecha_asignacion = models.DateTimeField(auto_now_add=True)

    fecha_fin = models.DateTimeField(
        null=True,
        blank=True,
    )

    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["-fecha_asignacion"]

        constraints = [
            models.UniqueConstraint(
                fields=["bano"],
                condition=Q(activa=True),
                name="un_bano_una_asignacion_activa",
            ),

            models.UniqueConstraint(
                fields=["trabajador"],
                condition=Q(activa=True),
                name="un_trabajador_una_asignacion_activa",
            ),
        ]

    def __str__(self):
        return f"{self.trabajador.email} → {self.bano.nombre}"