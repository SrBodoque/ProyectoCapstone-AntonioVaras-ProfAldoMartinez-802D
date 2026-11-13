
"""Pruebas integradas sin camara ni conexiones HTTP reales."""

import unittest

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
from uuid import UUID

from src.count_engine import CountEvent
from src.count_event_adapter import adaptar_evento_conteo
from src.event_outbox import EventOutbox
from src.django_event_sender import DjangoEventSender


class PruebasIntegracionEventos(unittest.TestCase):

    def setUp(self):
        temporal = TemporaryDirectory()
        self.addCleanup(temporal.cleanup)

        self.ruta_db = Path(temporal.name) / "eventos.sqlite3"
        self.cola = EventOutbox(self.ruta_db)

        self.fecha = datetime(
            2026, 11, 13, 10, 0,
            tzinfo=timezone.utc,
        )

    def crear_evento(self, direccion):
        return CountEvent(
            number=1,
            track_id=12,
            episode=1,
            timestamp=123.5,
            direction=direccion,
            origin="A" if direccion == "IN" else "B",
            destination="B" if direccion == "IN" else "A",
        )

    def adaptar(self, direccion):
        return adaptar_evento_conteo(
            self.crear_evento(direccion),
            fuente="droidcam-demo",
            ocurrido_en=self.fecha,
        )

    def crear_emisor(self, cola, transporte):
        return DjangoEventSender(
            cola,
            url="http://127.0.0.1:8000/api/v1/eventos-conteo/",
            token="token-ficticio",
            transporte=transporte,
        )

    def test_entrada_completa_http_201(self):
        datos = self.adaptar("IN")

        self.assertEqual(datos["tipo"], "ENTRADA")
        self.assertEqual(
            UUID(datos["referencia_externa"]).version,
            4,
        )

        self.assertTrue(self.cola.guardar(datos))

        transporte = Mock(return_value=201)
        emisor = self.crear_emisor(
            self.cola, transporte
        )

        resultado = emisor.procesar_pendientes()

        self.assertEqual(resultado["entregados"], 1)
        self.assertEqual(self.cola.listar_pendientes(), [])

        transporte.assert_called_once()
        enviado = transporte.call_args.args[2]

        # Debe enviarse exactamente el mismo JSON.
        self.assertEqual(enviado, datos)

    def test_salida_completa_http_200(self):
        datos = self.adaptar("OUT")

        self.assertEqual(datos["tipo"], "SALIDA")
        self.assertTrue(self.cola.guardar(datos))

        transporte = Mock(return_value=200)
        emisor = self.crear_emisor(
            self.cola, transporte
        )

        resultado = emisor.procesar_pendientes()

        self.assertEqual(resultado["entregados"], 1)
        self.assertEqual(self.cola.listar_pendientes(), [])

        enviado = transporte.call_args.args[2]
        self.assertEqual(enviado["tipo"], "SALIDA")
        self.assertEqual(enviado, datos)

    def test_fallo_y_recuperacion_sin_perder_uuid(self):
        datos = self.adaptar("IN")
        self.cola.guardar(datos)

        # Primer intento: Django no responde correctamente.
        transporte_fallido = Mock(return_value=500)
        emisor = self.crear_emisor(
            self.cola, transporte_fallido
        )

        resultado = emisor.procesar_pendientes()

        self.assertEqual(resultado["detenidos"], 1)
        self.assertEqual(
            self.cola.listar_pendientes(),
            [datos],
        )

        # Simular cierre y reapertura del almacenamiento.
        cola_reabierta = EventOutbox(self.ruta_db)

        # Segundo intento: Django confirma el evento.
        transporte_correcto = Mock(return_value=201)
        nuevo_emisor = self.crear_emisor(
            cola_reabierta,
            transporte_correcto,
        )

        resultado = nuevo_emisor.procesar_pendientes()

        self.assertEqual(resultado["entregados"], 1)
        self.assertEqual(
            cola_reabierta.listar_pendientes(),
            [],
        )

        enviado = transporte_correcto.call_args.args[2]

        # UUID y fecha originales se conservan.
        self.assertEqual(
            enviado["referencia_externa"],
            datos["referencia_externa"],
        )
        self.assertEqual(
            enviado["ocurrido_en"],
            datos["ocurrido_en"],
        )

    def test_conflicto_http_409(self):
        datos = self.adaptar("OUT")
        self.cola.guardar(datos)

        transporte = Mock(return_value=409)
        emisor = self.crear_emisor(
            self.cola, transporte
        )

        resultado = emisor.procesar_pendientes()

        self.assertEqual(resultado["conflictos"], 1)
        self.assertEqual(self.cola.listar_pendientes(), [])

        # SQLite conserva el registro del evento.
        self.assertFalse(self.cola.guardar(datos))


if __name__ == "__main__":
    unittest.main()
