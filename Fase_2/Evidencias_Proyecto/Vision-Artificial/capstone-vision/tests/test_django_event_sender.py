
"""Pruebas del emisor HTTP sin conexiones reales."""

import unittest

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
from urllib.error import URLError
from uuid import uuid4

from src.event_outbox import EventOutbox
from src.django_event_sender import DjangoEventSender


class PruebasEmisorDjango(unittest.TestCase):

    def setUp(self):
        temporal = TemporaryDirectory()
        self.addCleanup(temporal.cleanup)

        ruta = Path(temporal.name) / "eventos_test.sqlite3"
        self.cola = EventOutbox(ruta)

        self.evento = {
            "fuente": "droidcam-demo",
            "tipo": "ENTRADA",
            "referencia_externa": str(uuid4()),
            "ocurrido_en": "2026-11-13T13:15:30+00:00",
        }

        self.cola.guardar(self.evento)

    def crear_emisor(self, transporte):
        return DjangoEventSender(
            self.cola,
            url="http://127.0.0.1:8000/api/v1/eventos-conteo/",
            token="token-ficticio-de-pruebas",
            transporte=transporte,
        )

    def agregar_segundo_evento(self):
        segundo = {
            "fuente": "droidcam-demo",
            "tipo": "SALIDA",
            "referencia_externa": str(uuid4()),
            "ocurrido_en": "2026-11-13T13:16:00+00:00",
        }
        self.cola.guardar(segundo)
        return segundo

    # PRUEBA 1: Django crea el evento.
    def test_http_201_marca_entregado(self):
        transporte = Mock(return_value=201)
        emisor = self.crear_emisor(transporte)

        resumen = emisor.procesar_pendientes()

        self.assertEqual(resumen["entregados"], 1)
        self.assertEqual(self.cola.listar_pendientes(), [])

        # Confirmar que conserva el JSON original.
        argumentos = transporte.call_args.args
        self.assertEqual(argumentos[2], self.evento)
        self.assertEqual(
            argumentos[2]["referencia_externa"],
            self.evento["referencia_externa"],
        )

    # PRUEBA 2: Django ya tenia el evento.
    def test_http_200_marca_entregado(self):
        emisor = self.crear_emisor(
            Mock(return_value=200)
        )

        resumen = emisor.procesar_pendientes()

        self.assertEqual(resumen["entregados"], 1)
        self.assertEqual(self.cola.listar_pendientes(), [])

    # PRUEBA 3: UUID existente con datos diferentes.
    def test_http_409_marca_conflicto(self):
        emisor = self.crear_emisor(
            Mock(return_value=409)
        )

        resumen = emisor.procesar_pendientes()

        self.assertEqual(resumen["conflictos"], 1)
        self.assertEqual(self.cola.listar_pendientes(), [])

        # El evento sigue registrado en SQLite.
        self.assertFalse(self.cola.guardar(self.evento))

    # PRUEBA 4: Django tiene un error interno.
    def test_http_500_conserva_pendiente(self):
        emisor = self.crear_emisor(
            Mock(return_value=500)
        )

        resumen = emisor.procesar_pendientes()

        self.assertEqual(resumen["detenidos"], 1)
        self.assertEqual(
            self.cola.listar_pendientes(),
            [self.evento],
        )

    # PRUEBA 5: Token rechazado por Django.
    def test_http_401_conserva_pendiente(self):
        emisor = self.crear_emisor(
            Mock(return_value=401)
        )

        resumen = emisor.procesar_pendientes()

        self.assertEqual(resumen["detenidos"], 1)
        self.assertEqual(
            self.cola.listar_pendientes(),
            [self.evento],
        )

    # PRUEBA 6: No hay conexion con Django.
    def test_error_red_conserva_pendiente(self):
        transporte = Mock(
            side_effect=URLError("Servidor inaccesible")
        )
        emisor = self.crear_emisor(transporte)

        resumen = emisor.procesar_pendientes()

        self.assertEqual(resumen["detenidos"], 1)
        self.assertEqual(resumen["entregados"], 0)
        self.assertEqual(
            self.cola.listar_pendientes(),
            [self.evento],
        )

    # PRUEBA 7: Detener lote si falla el primer envio.
    def test_fallo_detiene_siguientes_eventos(self):
        self.agregar_segundo_evento()

        transporte = Mock(return_value=500)
        emisor = self.crear_emisor(transporte)

        resumen = emisor.procesar_pendientes()

        self.assertEqual(resumen["detenidos"], 1)
        self.assertEqual(
            len(self.cola.listar_pendientes()),
            2,
        )

        # No intenta enviar el segundo evento.
        transporte.assert_called_once()

    # PRUEBA 8: Respetar el limite de eventos.
    def test_maximo_un_evento_por_lote(self):
        segundo = self.agregar_segundo_evento()

        transporte = Mock(return_value=201)
        emisor = self.crear_emisor(transporte)

        resumen = emisor.procesar_pendientes(
            max_eventos=1
        )

        self.assertEqual(resumen["entregados"], 1)
        self.assertEqual(
            self.cola.listar_pendientes(),
            [segundo],
        )
        transporte.assert_called_once()


if __name__ == "__main__":
    unittest.main()
