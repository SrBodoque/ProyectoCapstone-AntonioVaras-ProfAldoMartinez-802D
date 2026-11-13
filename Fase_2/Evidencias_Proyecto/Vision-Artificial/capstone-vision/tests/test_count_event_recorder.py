
"""Pruebas aisladas del registro de eventos en SQLite."""

import sqlite3
import unittest

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import UUID

from src.count_engine import CountEvent
from src.count_event_recorder import CountEventRecorder
from src.event_outbox import EventOutbox


class PruebasRegistradorEventos(unittest.TestCase):

    def setUp(self):
        temporal = TemporaryDirectory()
        self.addCleanup(temporal.cleanup)

        self.ruta = Path(temporal.name) / "eventos.sqlite3"

        self.cola = EventOutbox(self.ruta)

        self.registrador = CountEventRecorder(
            self.cola,
            fuente="droidcam-demo",
        )

        self.evento = CountEvent(
            number=1,
            track_id=7,
            episode=1,
            timestamp=124.35,
            direction="IN",
            origin="A",
            destination="B",
        )

        self.fecha = datetime(
            2026, 11, 13, 10, 15, 30,
            tzinfo=timezone(timedelta(hours=-3)),
        )

    # PRUEBA 1: Registrar una entrada.
    def test_registrar_entrada(self):
        datos = self.registrador.registrar(
            self.evento,
            ocurrido_en=self.fecha,
        )

        self.assertEqual(datos["fuente"], "droidcam-demo")
        self.assertEqual(datos["tipo"], "ENTRADA")

        self.assertEqual(
            UUID(datos["referencia_externa"]).version,
            4,
        )

        self.assertEqual(
            self.cola.listar_pendientes(),
            [datos],
        )

    # PRUEBA 2: Registrar una salida.
    def test_registrar_salida(self):
        evento_salida = replace(
            self.evento,
            direction="OUT",
            origin="B",
            destination="A",
        )

        datos = self.registrador.registrar(
            evento_salida,
            ocurrido_en=self.fecha,
        )

        self.assertEqual(datos["tipo"], "SALIDA")
        self.assertEqual(
            self.cola.listar_pendientes(),
            [datos],
        )

    # PRUEBA 3: Conservar la fecha real en UTC.
    def test_conservar_fecha(self):
        datos = self.registrador.registrar(
            self.evento,
            ocurrido_en=self.fecha,
        )

        self.assertEqual(
            datos["ocurrido_en"],
            "2026-11-13T13:15:30+00:00",
        )

        # El tiempo monotónico de H5.2 no es
        # una fecha de calendario.
        self.assertNotIn("timestamp", datos)

    # PRUEBA 4: El evento sobrevive a una reapertura.
    def test_persistencia_tras_reapertura(self):
        datos = self.registrador.registrar(
            self.evento,
            ocurrido_en=self.fecha,
        )

        nueva_cola = EventOutbox(self.ruta)

        self.assertEqual(
            nueva_cola.listar_pendientes(),
            [datos],
        )

    # PRUEBA 5: Rechazar un evento inválido.
    def test_rechazar_evento_invalido(self):
        with self.assertRaises(TypeError):
            self.registrador.registrar(
                {"direction": "IN"},
                ocurrido_en=self.fecha,
            )

        self.assertEqual(
            self.cola.listar_pendientes(),
            [],
        )

    # PRUEBA 6: Rechazar fechas sin zona horaria.
    def test_rechazar_fecha_sin_zona(self):
        fecha_invalida = datetime(
            2026, 11, 13, 10, 15, 30
        )

        with self.assertRaises(ValueError):
            self.registrador.registrar(
                self.evento,
                ocurrido_en=fecha_invalida,
            )

        self.assertEqual(
            self.cola.listar_pendientes(),
            [],
        )

    # PRUEBA 7: No informar éxito si falla SQLite.
    def test_error_sqlite_se_propaga(self):
        with patch.object(
            self.cola,
            "guardar",
            side_effect=sqlite3.OperationalError(
                "Fallo de almacenamiento simulado"
            ),
        ):
            with self.assertRaises(sqlite3.OperationalError):
                self.registrador.registrar(
                    self.evento,
                    ocurrido_en=self.fecha,
                )

        self.assertEqual(
            self.cola.listar_pendientes(),
            [],
        )


    def test_mismo_evento_no_se_duplica(self):
        primero = self.registrador.registrar(
            self.evento,
            ocurrido_en=self.fecha,
        )

        segundo = self.registrador.registrar(
            self.evento,
            ocurrido_en=self.fecha,
        )

        # Debe conservar exactamente el mismo UUID.
        self.assertEqual(primero, segundo)
        self.assertEqual(
            len(self.cola.listar_pendientes()),
            1,
        )

    def test_mismo_numero_otro_evento_se_rechaza(self):
        self.registrador.registrar(
            self.evento,
            ocurrido_en=self.fecha,
        )

        evento_distinto = replace(
            self.evento,
            direction="OUT",
            origin="B",
            destination="A",
        )

        with self.assertRaises(ValueError):
            self.registrador.registrar(
                evento_distinto,
                ocurrido_en=self.fecha,
            )

        self.assertEqual(
            len(self.cola.listar_pendientes()),
            1,
        )

    def test_fallo_sqlite_no_bloquea_reintento(self):
        with patch.object(
            self.cola,
            "guardar",
            side_effect=sqlite3.OperationalError(
                "Fallo simulado"
            ),
        ):
            with self.assertRaises(sqlite3.OperationalError):
                self.registrador.registrar(
                    self.evento,
                    ocurrido_en=self.fecha,
                )

        # Despues de recuperarse SQLite,
        # el evento puede guardarse normalmente.
        datos = self.registrador.registrar(
            self.evento,
            ocurrido_en=self.fecha,
        )

        self.assertEqual(
            self.cola.listar_pendientes(),
            [datos],
        )



    def test_sesiones_distintas_pueden_reutilizar_numero(self):
        # Primera sesion del contador.
        primero = self.registrador.registrar(
            self.evento,
            ocurrido_en=self.fecha,
        )

        # Simular una segunda ejecucion del contador.
        nuevo_registrador = CountEventRecorder(
            self.cola,
            fuente="droidcam-demo",
        )

        # El contador vuelve a comenzar desde el evento 1,
        # pero corresponde a un movimiento diferente.
        evento_nueva_sesion = replace(
            self.evento,
            track_id=99,
            timestamp=3.0,
        )

        segundo = nuevo_registrador.registrar(
            evento_nueva_sesion,
            ocurrido_en=self.fecha,
        )

        # Ambos movimientos deben conservarse.
        self.assertNotEqual(
            primero["referencia_externa"],
            segundo["referencia_externa"],
        )

        self.assertEqual(
            len(self.cola.listar_pendientes()),
            2,
        )



    def test_reinicio_recupera_uuid_y_fecha_originales(self):
        primero = self.registrador.registrar(
            self.evento,
            ocurrido_en=self.fecha,
        )

        # Simular cierre y reapertura de SQLite
        # recuperando la MISMA sesion.
        nueva_cola = EventOutbox(self.ruta)

        nuevo_registrador = CountEventRecorder(
            nueva_cola,
            fuente="droidcam-demo",
            sesion_id=self.registrador.sesion_id,
        )

        segundo = nuevo_registrador.registrar(
            self.evento,
            ocurrido_en=datetime(
                2030, 1, 1,
                tzinfo=timezone.utc,
            ),
        )

        # Debe recuperar el JSON original,
        # sin generar otro UUID ni otra fecha.
        self.assertEqual(primero, segundo)
        self.assertEqual(
            len(nueva_cola.listar_pendientes()),
            1,
        )

    def test_reinicio_rechaza_movimiento_diferente(self):
        original = self.registrador.registrar(
            self.evento,
            ocurrido_en=self.fecha,
        )

        nueva_cola = EventOutbox(self.ruta)

        nuevo_registrador = CountEventRecorder(
            nueva_cola,
            fuente="droidcam-demo",
            sesion_id=self.registrador.sesion_id,
        )

        # Conserva numero y direccion,
        # pero cambia el movimiento original.
        movimiento_distinto = replace(
            self.evento,
            track_id=99,
        )

        with self.assertRaises(ValueError):
            nuevo_registrador.registrar(
                movimiento_distinto,
                ocurrido_en=self.fecha,
            )

        # El evento original permanece intacto.
        self.assertEqual(
            nueva_cola.listar_pendientes(),
            [original],
        )



if __name__ == "__main__":
    unittest.main()
