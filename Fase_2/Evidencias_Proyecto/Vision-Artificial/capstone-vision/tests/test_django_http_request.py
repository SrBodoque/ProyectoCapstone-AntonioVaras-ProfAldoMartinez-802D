
"""Pruebas de solicitudes HTTP sin usar la red."""

import json
import unittest

from unittest.mock import patch
from urllib.error import HTTPError, URLError
from uuid import uuid4

from src.django_event_sender import DjangoEventSender


class PruebasSolicitudHTTP(unittest.TestCase):

    def setUp(self):
        self.url = (
            "http://127.0.0.1:8000/"
            "api/v1/eventos-conteo/"
        )
        self.token = "token-ficticio-de-pruebas"

        self.datos = {
            "fuente": "droidcam-demo",
            "tipo": "ENTRADA",
            "referencia_externa": str(uuid4()),
            "ocurrido_en": "2026-11-13T13:15:30+00:00",
        }

    def enviar(self):
        return DjangoEventSender._enviar_http(
            self.url,
            self.token,
            self.datos,
            5,
        )

    def test_solicitud_usa_post_y_json(self):
        with patch(
            "src.django_event_sender.urlopen"
        ) as abrir:
            abrir.return_value.__enter__.return_value.status = 201

            codigo = self.enviar()

            solicitud = abrir.call_args.args[0]

        self.assertEqual(codigo, 201)
        self.assertEqual(solicitud.get_method(), "POST")
        self.assertEqual(
            solicitud.get_header("Content-type"),
            "application/json",
        )
        self.assertEqual(
            json.loads(solicitud.data.decode("utf-8")),
            self.datos,
        )

    def test_autenticacion_bearer(self):
        with patch(
            "src.django_event_sender.urlopen"
        ) as abrir:
            abrir.return_value.__enter__.return_value.status = 201

            self.enviar()

            solicitud = abrir.call_args.args[0]

        self.assertEqual(
            solicitud.get_header("Authorization"),
            f"Bearer {self.token}",
        )

        # El secreto no debe aparecer dentro del JSON.
        self.assertNotIn(
            self.token,
            solicitud.data.decode("utf-8"),
        )

    def test_url_y_timeout(self):
        with patch(
            "src.django_event_sender.urlopen"
        ) as abrir:
            abrir.return_value.__enter__.return_value.status = 201

            self.enviar()

            solicitud = abrir.call_args.args[0]
            tiempo_limite = abrir.call_args.kwargs["timeout"]

        self.assertEqual(solicitud.full_url, self.url)
        self.assertEqual(tiempo_limite, 5)

    def test_respuestas_exitosas(self):
        for codigo in (200, 201):
            with self.subTest(codigo=codigo):
                with patch(
                    "src.django_event_sender.urlopen"
                ) as abrir:
                    abrir.return_value.__enter__.return_value.status = codigo

                    resultado = self.enviar()

                self.assertEqual(resultado, codigo)

    def test_respuestas_http_de_error(self):
        for codigo in (401, 409, 500):
            with self.subTest(codigo=codigo):
                error = HTTPError(
                    self.url,
                    codigo,
                    "Error simulado",
                    None,
                    None,
                )

                with patch(
                    "src.django_event_sender.urlopen",
                    side_effect=error,
                ):
                    resultado = self.enviar()

                self.assertEqual(resultado, codigo)

    def test_error_de_red_se_propaga(self):
        with patch(
            "src.django_event_sender.urlopen",
            side_effect=URLError("Sin conexion"),
        ):
            with self.assertRaises(URLError):
                self.enviar()


if __name__ == "__main__":
    unittest.main()
