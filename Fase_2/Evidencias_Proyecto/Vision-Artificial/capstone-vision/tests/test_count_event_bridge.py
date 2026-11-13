
"""Pruebas del puente H5.2 -> SQLite, sin camara."""

import sqlite3
import unittest

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.count_engine import CountEvent
from src.count_event_bridge import guardar_eventos_confirmados
from src.count_event_recorder import CountEventRecorder
from src.event_outbox import EventOutbox


class PruebasPuenteConteo(unittest.TestCase):

    def setUp(self):
        temporal = TemporaryDirectory()
        self.addCleanup(temporal.cleanup)

        ruta = Path(temporal.name) / "eventos.sqlite3"

        self.cola = EventOutbox(ruta)
        self.registrador = CountEventRecorder(
            self.cola,
            fuente="droidcam-demo",
        )

        self.fecha = datetime(
            2026, 11, 13, 13, 15, 30,
            tzinfo=timezone.utc,
        )

        self.entrada = CountEvent(
            number=1,
            track_id=7,
            episode=1,
            timestamp=124.35,
            direction="IN",
            origin="A",
            destination="B",
        )

        self.salida = CountEvent(
            number=2,
            track_id=7,
            episode=2,
            timestamp=130.20,
            direction="OUT",
            origin="B",
            destination="A",
        )

    def guardar(self, eventos):
        return guardar_eventos_confirmados(
            eventos,
            self.registrador,
            reloj_utc=lambda: self.fecha,
        )

    def test_guarda_entrada_y_salida(self):
        resultado = self.guardar(
            (self.entrada, self.salida)
        )

        self.assertEqual(len(resultado), 2)

        self.assertEqual(
            [item["tipo"] for item in resultado],
            ["ENTRADA", "SALIDA"],
        )

        self.assertEqual(
            list(resultado),
            self.cola.listar_pendientes(),
        )

        self.assertTrue(
            all(
                item["ocurrido_en"]
                == "2026-11-13T13:15:30+00:00"
                for item in resultado
            )
        )

    def test_no_duplica_eventos_repetidos(self):
        primero = self.guardar((self.entrada,))
        segundo = self.guardar((self.entrada,))

        self.assertEqual(primero, segundo)
        self.assertEqual(
            len(self.cola.listar_pendientes()),
            1,
        )

    def test_no_guarda_fecha_sin_zona_horaria(self):
        fecha_invalida = datetime(
            2026, 11, 13, 10, 15, 30
        )

        with self.assertRaises(ValueError):
            guardar_eventos_confirmados(
                (self.entrada,),
                self.registrador,
                reloj_utc=lambda: fecha_invalida,
            )

        self.assertEqual(
            self.cola.listar_pendientes(),
            [],
        )

    def test_error_sqlite_no_se_oculta(self):
        with patch.object(
            self.cola,
            "guardar",
            side_effect=sqlite3.OperationalError(
                "Error simulado de SQLite"
            ),
        ):
            with self.assertRaises(
                sqlite3.OperationalError
            ):
                self.guardar((self.entrada,))

        self.assertEqual(
            self.cola.listar_pendientes(),
            [],
        )


if __name__ == "__main__":
    unittest.main()
