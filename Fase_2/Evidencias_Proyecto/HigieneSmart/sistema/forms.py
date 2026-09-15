from django import forms
from .models import Bano


class LoginForm(forms.Form):
    email = forms.EmailField(
        label="Correo electrónico",
        max_length=254,
        error_messages={
            "required": "Debes ingresar tu correo electrónico.",
            "invalid": "Ingresa un correo electrónico válido.",
        },
    )

    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput,
        error_messages={
            "required": "Debes ingresar tu contraseña.",
        },
    )

class BanoForm(forms.ModelForm):
    class Meta:
        model = Bano
        fields = ["nombre", "ubicacion", "activo"]

        labels = {
            "nombre": "Nombre del baño",
            "ubicacion": "Ubicación",
            "activo": "Baño activo",
        }