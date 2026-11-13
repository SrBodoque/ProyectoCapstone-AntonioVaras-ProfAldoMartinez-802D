
import unittest

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID

from src.count_engine import CountEvent
from src.count_event_adapter import adaptar_evento_conteo


class PruebasAdaptadorConteo(unittest.TestCase):

    def setUp(self):
        # Evento ficticio confirmado por el contador.
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

        self.uuid = UUID(
            "550e8400-e29b-41d4-a716-446655440000"
        )

    # PRUEBA 1: IN SE CONVIERTE EN ENTRADA
    def test_entrada(self):
        datos = adaptar_evento_conteo(
            self.evento,
            fuente="droidcam-demo",
            referencia_externa=self.uuid,
            ocurrido_en=self.fecha,
        )

        self.assertEqual(datos, {
            "fuente": "droidcam-demo",
            "tipo": "ENTRADA",
            "referencia_externa": str(self.uuid),
            "ocurrido_en": "2026-11-13T13:15:30+00:00",
        })

    # PRUEBA 2: OUT SE CONVIERTE EN SALIDA
    def test_salida(self):
        evento_salida = replace(
            self.evento,
            direction="OUT",
            origin="B",
            destination="A",
        )

        datos = adaptar_evento_conteo(
            evento_salida,
            fuente="droidcam-demo",
            referencia_externa=self.uuid,
            ocurrido_en=self.fecha,
        )

        self.assertEqual(datos["tipo"], "SALIDA")
        self.assertEqual(datos["fuente"], "droidcam-demo")

    # PRUEBA 3: GENERAR UUID4
    def test_uuid4_automatico(self):
        datos = adaptar_evento_conteo(
            self.evento,
            fuente="droidcam-demo",
            ocurrido_en=self.fecha,
        )

        identificador = UUID(datos["referencia_externa"])

        self.assertEqual(identificador.version, 4)

    # PRUEBA 4: FECHA CON ZONA HORARIA
    def test_fecha_utc(self):
        datos = adaptar_evento_conteo(
            self.evento,
            fuente="droidcam-demo",
            ocurrido_en=self.fecha,
        )

        self.assertEqual(
            datos["ocurrido_en"],
            "2026-11-13T13:15:30+00:00",
        )

        # El timestamp monotónico original
        # no debe convertirse en fecha de calendario.
        self.assertNotIn("timestamp", datos)

    # PRUEBA 5: RECHAZAR DIRECCION DESCONOCIDA
    def test_direccion_invalida(self):
        evento_invalido = replace(
            self.evento,
            direction="OTRO",
        )

        with self.assertRaises(ValueError):
            adaptar_evento_conteo(
                evento_invalido,
                fuente="droidcam-demo",
            )

    # PRUEBA 6: RECHAZAR FECHA SIN ZONA HORARIA
    def test_fecha_sin_zona_horaria(self):
        fecha_invalida = datetime(
            2026, 11, 13, 10, 15, 30
        )

        with self.assertRaises(ValueError):
            adaptar_evento_conteo(
                self.evento,
                fuente="droidcam-demo",
                ocurrido_en=fecha_invalida,
            )

    # PRUEBA 7: RECHAZAR FUENTE VACIA
    def test_fuente_vacia(self):
        with self.assertRaises(ValueError):
            adaptar_evento_conteo(
                self.evento,
                fuente="",
            )


if __name__ == "__main__":
    unittest.main()
