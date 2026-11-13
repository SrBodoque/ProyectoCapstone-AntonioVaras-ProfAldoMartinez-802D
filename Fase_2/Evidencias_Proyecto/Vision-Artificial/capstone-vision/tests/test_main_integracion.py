
"""
Pruebas de conexion entre main() y SQLite.

Todas las dependencias externas se simulan.
No se abre la camara ni se crea una base real.
"""

import sys
import unittest

from unittest.mock import DEFAULT, MagicMock, patch

from src import track_count
from src import count_outbox_config


class PruebasMainIntegracion(unittest.TestCase):

    def ejecutar_main(
        self,
        *,
        registrador=None,
        error=None,
    ):
        # Simular OpenCV sin instalarlo.
        cv2_simulado = MagicMock()

        with (
            patch.dict(
                sys.modules,
                {"cv2": cv2_simulado},
            ),
            patch.dict(
                "os.environ",
                {"DISPLAY": ":simulado"},
            ),
            patch.multiple(
                track_count,
                ZoneStore=DEFAULT,
                load_orientation=DEFAULT,
                load_counting_config=DEFAULT,
                EntryCounter=DEFAULT,
                select_tracker=DEFAULT,
                load_config=DEFAULT,
                load_detection_config=DEFAULT,
                ensure_local_models=DEFAULT,
                run_count=DEFAULT,
            ) as componentes,
            patch.object(
                count_outbox_config,
                "crear_registrador_desde_entorno",
            ) as crear_registrador,
        ):
            if error is not None:
                crear_registrador.side_effect = error
            else:
                crear_registrador.return_value = registrador

            codigo = track_count.main([])

            crear_registrador.assert_called_once_with()

            return (
                codigo,
                componentes["run_count"],
            )

    def test_sin_registrador_mantiene_modo_original(self):
        codigo, ejecutar_contador = self.ejecutar_main(
            registrador=None,
        )

        self.assertEqual(codigo, 0)
        ejecutar_contador.assert_called_once()

        self.assertIsNone(
            ejecutar_contador.call_args.kwargs["registrador"]
        )

    def test_con_registrador_lo_entrega_al_contador(self):
        registrador_ficticio = MagicMock()

        codigo, ejecutar_contador = self.ejecutar_main(
            registrador=registrador_ficticio,
        )

        self.assertEqual(codigo, 0)
        ejecutar_contador.assert_called_once()

        self.assertIs(
            ejecutar_contador.call_args.kwargs["registrador"],
            registrador_ficticio,
        )

    def test_error_sqlite_impide_iniciar_contador(self):
        codigo, ejecutar_contador = self.ejecutar_main(
            error=ValueError(
                "Configuracion SQLite invalida"
            ),
        )

        self.assertEqual(codigo, 1)
        ejecutar_contador.assert_not_called()


if __name__ == "__main__":
    unittest.main()
