from django import forms
from usuarios.models import Usuario
from .models import Bano
from django.contrib.auth.forms import SetPasswordForm


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

class TrabajadorForm(forms.Form):
    email = forms.EmailField(
        label="Correo electrónico",
        max_length=254,
        error_messages={
            "required": "Debes ingresar el correo electrónico del trabajador.",
            "invalid": "Ingresa un correo electrónico válido.",
        },
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Ya existe un usuario registrado con este correo electrónico."
            )

        return email

class ActivarCuentaForm(SetPasswordForm):
    pass