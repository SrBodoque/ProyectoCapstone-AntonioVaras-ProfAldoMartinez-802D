from django.db import models


class Bano(models.Model):
    nombre = models.CharField(max_length=100)
    ubicacion = models.CharField(max_length=150)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} - {self.ubicacion}"
