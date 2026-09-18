from django.db import models
from django.utils import timezone

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

class Alerta(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        EN_PROCESO = "EN_PROCESO", "En proceso"
        ATENDIDA = "ATENDIDA", "Atendida"

    bano = models.ForeignKey(
        Bano,
        on_delete=models.PROTECT,
        related_name="alertas",
    )

    motivo = models.CharField(
        max_length=200,
        default="Umbral de uso alcanzado",
    )

    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return (
            f"{self.bano.nombre} - "
            f"{self.get_estado_display()}"
        )

class IntervencionLimpieza(models.Model):
    alerta = models.OneToOneField(
        Alerta,
        on_delete=models.PROTECT,
        related_name="intervencion",
    )

    trabajador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="intervenciones_limpieza",
        limit_choices_to={
            "rol": "TRABAJADOR",
            "is_active": True,
        },
    )

    bano = models.ForeignKey(
        Bano,
        on_delete=models.PROTECT,
        related_name="intervenciones_limpieza",
    )

    fecha_inicio = models.DateTimeField(
        auto_now_add=True,
    )

    fecha_fin = models.DateTimeField(
        null=True,
        blank=True,
    )

    evidencia = models.ImageField(
        upload_to="evidencias_limpieza/%Y/%m/%d/",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-fecha_inicio"]

    @property
    def duracion(self):
        if self.fecha_fin is not None:
            return self.fecha_fin - self.fecha_inicio

        return None


    @property
    def duracion_formateada(self):
        if self.duracion is None:
            return "En curso"

        total_segundos = int(self.duracion.total_seconds())

        minutos, _ = divmod(total_segundos, 60)
        horas, minutos = divmod(minutos, 60)

        if horas > 0:
            return f"{horas} h {minutos} min"

        return f"{minutos} min"

    def __str__(self):
        return (
            f"{self.trabajador.email} - "
            f"{self.bano.nombre}"
        )


class EventoConteo(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = "ENTRADA", "Entrada"
        SALIDA = "SALIDA", "Salida"

    class Origen(models.TextChoices):
        SIMULADO = "SIMULADO", "Simulado"
        VISION = "VISION", "Visión artificial"

    bano = models.ForeignKey(
        Bano,
        on_delete=models.PROTECT,
        related_name="eventos_conteo",
    )

    tipo = models.CharField(
        max_length=10,
        choices=Tipo.choices,
    )

    fecha_evento = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    origen = models.CharField(
        max_length=20,
        choices=Origen.choices,
        default=Origen.SIMULADO,
    )

    referencia_externa = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        unique=True,
    )

    fecha_registro = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-fecha_evento"]

    def __str__(self):
        return (
            f"{self.bano.nombre} - "
            f"{self.get_tipo_display()} - "
            f"{self.fecha_evento:%d/%m/%Y %H:%M:%S}"
        )