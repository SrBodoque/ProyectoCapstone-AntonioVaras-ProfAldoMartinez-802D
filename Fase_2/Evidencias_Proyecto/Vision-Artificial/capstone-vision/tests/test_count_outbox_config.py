
"""Pruebas de configuracion SQLite sin camara."""

import unittest

from pathlib import Path
from tempfile import TemporaryDirectory

from src.count_outbox_config import (
    crear_registrador_desde_entorno,
)
from src.count_event_recorder import CountEventRecorder


class PruebasConfiguracionSQLite(unittest.TestCase):

    def setUp(self):
        temporal = TemporaryDirectory()
        self.addCleanup(temporal.cleanup)

        self.carpeta = Path(temporal.name)

    def test_desactivado_por_defecto(self):
        variables = {
            "LOCALAPPDATA": str(self.carpeta),
        }

        registrador = crear_registrador_desde_entorno(
            variables=variables,
        )

        self.assertIsNone(registrador)
        self.assertFalse(
            (self.carpeta / "limpIAvision").exists()
        )

    def test_activado_crea_sqlite(self):
        variables = {
            "LIMPIA_GUARDAR_CONTEOS": "1",
            "LOCALAPPDATA": str(self.carpeta),
        }

        registrador = crear_registrador_desde_entorno(
            variables=variables,
        )

        self.assertIsInstance(
            registrador,
            CountEventRecorder,
        )

        self.assertEqual(
            registrador.fuente,
            "droidcam-demo",
        )

        self.assertTrue(
            (
                self.carpeta
                / "limpIAvision"
                / "eventos.sqlite3"
            ).is_file()
        )

    def test_sin_localappdata_no_activa(self):
        variables = {
            "LIMPIA_GUARDAR_CONTEOS": "1",
        }

        with self.assertRaises(ValueError):
            crear_registrador_desde_entorno(
                variables=variables,
            )


if __name__ == "__main__":
    unittest.main()
