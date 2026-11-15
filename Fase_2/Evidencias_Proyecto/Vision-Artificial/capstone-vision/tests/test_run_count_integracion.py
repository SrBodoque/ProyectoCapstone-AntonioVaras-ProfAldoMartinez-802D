
"""
Pruebas de la conexion H5.2 -> SQLite.

Simula la camara, el tracker y el guardado.
No utiliza hardware ni realiza solicitudes HTTP.
"""

import sqlite3
import sys
import unittest

from contextlib import contextmanager
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from src import track_count
from src.count_engine import CountEvent


class PruebasBucleIntegracion(unittest.TestCase):

    def setUp(self):
        self.evento = CountEvent(
            number=1,
            track_id=7,
            episode=1,
            timestamp=10.0,
            direction="IN",
            origin="A",
            destination="B",
        )

        self.contador = MagicMock()
        self.contador.states = {}
        self.contador.total_entries = 1
        self.contador.total_exits = 0
        self.contador.update.return_value = (self.evento,)

        self.contador.settings.zone_dwell_seconds = 0.12
        self.contador.settings.min_observations = 2
        self.contador.settings.max_gap_seconds = 2.0

        self.ui = MagicMock()
        self.ui.WINDOW_NORMAL = 0
        self.ui.error = RuntimeError
        self.ui.waitKey.return_value = ord("q")

        self.tracker = MagicMock()
        self.tracker.config = {"device": "cpu"}
        self.tracker.tracking_confidence = 0.65
        self.tracker.track.return_value = SimpleNamespace(
            tracks=(),
            untracked_detections=(),
            inference_ms=1.0,
            processing_ms=2.0,
        )

        self.seleccion = MagicMock()
        self.seleccion.label = "Tracker simulado"
        self.seleccion.tracking_config = {
            "show_trail": False,
        }
        self.seleccion.constructor_options.return_value = {}

        self.guardar_simulado = Mock()
        self.registrador = object()

    def ejecutar(self, registrador):
        camara_simulada = ModuleType("src.camera")

        @contextmanager
        def sesion_simulada(configuracion):
            captura = MagicMock()
            imagen = SimpleNamespace(
                shape=(480, 480, 3),
            )
            yield captura, imagen

        camara_simulada.camera_session = sesion_simulada
        camara_simulada.camera_info = (
            lambda captura: {"backend": "simulado"}
        )

        configuracion_camara = {
            "camera_index": 0,
        }

        configuracion_deteccion = {
            "show_confidence": False,
        }

        with (
            patch.dict(
                sys.modules,
                {"src.camera": camara_simulada},
            ),
            patch.object(
                track_count,
                "PersonTracker",
                return_value=self.tracker,
            ),
            patch.object(track_count, "draw_regions"),
            patch.object(track_count, "draw_tracks"),
            patch.object(track_count, "draw_positions"),
            patch.object(track_count, "_label"),
            patch(
                "src.count_event_bridge.guardar_eventos_confirmados",
                self.guardar_simulado,
            ),
        ):
            return track_count.run_count(
                self.ui,
                configuracion_camara,
                configuracion_deteccion,
                self.seleccion,
                self.contador,
                clock=lambda: 10.0,
                registrador=registrador,
            )

    def test_desactivado_no_guarda_eventos(self):
        resultado = self.ejecutar(
            registrador=None,
        )

        self.assertEqual(resultado, 1)
        self.guardar_simulado.assert_not_called()
        self.ui.destroyAllWindows.assert_called_once()

    def test_activado_guarda_evento_confirmado(self):
        resultado = self.ejecutar(
            registrador=self.registrador,
        )

        self.assertEqual(resultado, 1)

        self.guardar_simulado.assert_called_once_with(
            (self.evento,),
            self.registrador,
        )

        self.ui.destroyAllWindows.assert_called_once()

    def test_sin_movimientos_no_guarda(self):
        self.contador.update.return_value = ()

        self.ejecutar(
            registrador=self.registrador,
        )

        self.guardar_simulado.assert_not_called()

    def test_error_sqlite_no_se_oculta(self):
        self.guardar_simulado.side_effect = (
            sqlite3.OperationalError(
                "Error SQLite simulado"
            )
        )

        with self.assertRaises(sqlite3.OperationalError):
            self.ejecutar(
                registrador=self.registrador,
            )

        # Aunque falle SQLite, se intenta
        # cerrar la ventana de la camara.
        self.ui.destroyAllWindows.assert_called_once()


    def test_bucle_guarda_evento_real_en_sqlite(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from uuid import UUID

        from src.count_event_bridge import (
            guardar_eventos_confirmados,
        )
        from src.count_event_recorder import CountEventRecorder
        from src.event_outbox import EventOutbox

        # Crear una base SQLite temporal.
        with TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "eventos_test.sqlite3"

            cola = EventOutbox(ruta)

            registrador = CountEventRecorder(
                cola,
                fuente="droidcam-demo",
            )

            # El bucle sigue usando camara simulada,
            # pero el guardado ahora sera real.
            self.guardar_simulado.side_effect = (
                guardar_eventos_confirmados
            )

            resultado = self.ejecutar(
                registrador=registrador,
            )

            self.assertEqual(resultado, 1)

            # Reabrir SQLite para verificar persistencia.
            nueva_cola = EventOutbox(ruta)
            pendientes = nueva_cola.listar_pendientes()

            self.assertEqual(len(pendientes), 1)

            evento_guardado = pendientes[0]

            self.assertEqual(
                evento_guardado["tipo"],
                "ENTRADA",
            )

            self.assertEqual(
                evento_guardado["fuente"],
                "droidcam-demo",
            )

            self.assertEqual(
                UUID(
                    evento_guardado["referencia_externa"]
                ).version,
                4,
            )

            self.assertIn(
                "+00:00",
                evento_guardado["ocurrido_en"],
            )

            # Solo hubo una llamada de guardado.
            self.guardar_simulado.assert_called_once()



if __name__ == "__main__":
    unittest.main()
