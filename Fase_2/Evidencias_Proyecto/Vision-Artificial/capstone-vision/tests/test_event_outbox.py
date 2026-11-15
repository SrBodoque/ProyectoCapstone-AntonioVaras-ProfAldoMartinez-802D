
"""Pruebas aisladas de persistencia para EventOutbox."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from src.event_outbox import EventOutbox


class PruebasColaSQLite(unittest.TestCase):

    def setUp(self):
        # La base de pruebas se crea fuera del proyecto.
        temporal = TemporaryDirectory()
        self.addCleanup(temporal.cleanup)

        self.ruta = Path(temporal.name) / "eventos_test.sqlite3"
        self.cola = EventOutbox(self.ruta)

        self.evento = {
            "fuente": "droidcam-demo",
            "tipo": "ENTRADA",
            "referencia_externa": str(uuid4()),
            "ocurrido_en": "2026-11-13T13:15:30+00:00",
        }

    def test_cola_nueva_esta_vacia(self):
        self.assertEqual(self.cola.listar_pendientes(), [])

    def test_guardar_evento_nuevo(self):
        guardado = self.cola.guardar(self.evento)

        self.assertTrue(guardado)
        self.assertEqual(
            self.cola.listar_pendientes(),
            [self.evento],
        )

    def test_evento_sobrevive_reapertura(self):
        self.cola.guardar(self.evento)

        # Se crea otra instancia que abre el mismo archivo.
        nueva_cola = EventOutbox(self.ruta)

        self.assertEqual(
            nueva_cola.listar_pendientes(),
            [self.evento],
        )

    def test_mismo_uuid_no_se_duplica(self):
        primer_guardado = self.cola.guardar(self.evento)
        segundo_guardado = self.cola.guardar(self.evento)

        self.assertTrue(primer_guardado)
        self.assertFalse(segundo_guardado)
        self.assertEqual(
            len(self.cola.listar_pendientes()),
            1,
        )

    def test_mismo_uuid_con_datos_distintos_se_rechaza(self):
        self.cola.guardar(self.evento)

        evento_diferente = dict(self.evento)
        evento_diferente["tipo"] = "SALIDA"

        with self.assertRaises(ValueError):
            self.cola.guardar(evento_diferente)

        # El evento original debe permanecer intacto.
        self.assertEqual(
            self.cola.listar_pendientes(),
            [self.evento],
        )

    def test_rechazar_uuid_invalido(self):
        evento_invalido = dict(self.evento)
        evento_invalido["referencia_externa"] = "no-es-un-uuid"

        with self.assertRaises(ValueError):
            self.cola.guardar(evento_invalido)

        self.assertEqual(self.cola.listar_pendientes(), [])

    def test_rechazar_fecha_sin_zona_horaria(self):
        evento_invalido = dict(self.evento)
        evento_invalido["ocurrido_en"] = "2026-11-13T13:15:30"

        with self.assertRaises(ValueError):
            self.cola.guardar(evento_invalido)

        self.assertEqual(self.cola.listar_pendientes(), [])

    def test_guardar_entrada_y_salida(self):
        salida = dict(self.evento)
        salida["tipo"] = "SALIDA"
        salida["referencia_externa"] = str(uuid4())
        salida["ocurrido_en"] = "2026-11-13T13:16:00+00:00"

        self.assertTrue(self.cola.guardar(self.evento))
        self.assertTrue(self.cola.guardar(salida))

        pendientes = self.cola.listar_pendientes()

        self.assertEqual(len(pendientes), 2)
        self.assertEqual(
            [evento["tipo"] for evento in pendientes],
            ["ENTRADA", "SALIDA"],
        )


    def test_marcar_entregado(self):
        self.cola.guardar(self.evento)
        referencia = self.evento["referencia_externa"]

        self.assertTrue(
            self.cola.marcar_entregado(referencia)
        )
        self.assertEqual(self.cola.listar_pendientes(), [])

        # Confirmar dos veces no produce errores.
        self.assertFalse(
            self.cola.marcar_entregado(referencia)
        )

        # El registro sigue existiendo y no se duplica.
        self.assertFalse(self.cola.guardar(self.evento))

    def test_marcar_conflicto(self):
        self.cola.guardar(self.evento)
        referencia = self.evento["referencia_externa"]

        self.assertTrue(
            self.cola.marcar_conflicto(referencia)
        )
        self.assertEqual(self.cola.listar_pendientes(), [])

        self.assertFalse(
            self.cola.marcar_conflicto(referencia)
        )

    def test_no_cambiar_estado_final(self):
        self.cola.guardar(self.evento)
        referencia = self.evento["referencia_externa"]

        self.cola.marcar_conflicto(referencia)

        # Un conflicto no se convierte silenciosamente
        # en entregado.
        with self.assertRaises(ValueError):
            self.cola.marcar_entregado(referencia)

        # Tampoco se puede marcar un UUID inexistente.
        with self.assertRaises(ValueError):
            self.cola.marcar_entregado(str(uuid4()))


    def test_identidad_sobrevive_reapertura(self):
        sesion = str(uuid4())

        self.assertTrue(
            self.cola.guardar(
                self.evento,
                sesion_id=sesion,
                numero_evento=1,
            )
        )

        nueva_cola = EventOutbox(self.ruta)

        self.assertEqual(
            nueva_cola.buscar_por_movimiento(sesion, 1),
            self.evento,
        )

    def test_misma_sesion_numero_otro_uuid_se_rechaza(self):
        sesion = str(uuid4())

        self.cola.guardar(
            self.evento,
            sesion_id=sesion,
            numero_evento=1,
        )

        duplicado = dict(self.evento)
        duplicado["referencia_externa"] = str(uuid4())

        with self.assertRaises(ValueError):
            self.cola.guardar(
                duplicado,
                sesion_id=sesion,
                numero_evento=1,
            )

        self.assertEqual(
            len(self.cola.listar_pendientes()),
            1,
        )

    def test_sesiones_distintas_reutilizan_numero(self):
        sesion_1 = str(uuid4())
        sesion_2 = str(uuid4())

        segundo = dict(self.evento)
        segundo["referencia_externa"] = str(uuid4())

        self.assertTrue(
            self.cola.guardar(
                self.evento,
                sesion_id=sesion_1,
                numero_evento=1,
            )
        )

        self.assertTrue(
            self.cola.guardar(
                segundo,
                sesion_id=sesion_2,
                numero_evento=1,
            )
        )

        self.assertEqual(
            len(self.cola.listar_pendientes()),
            2,
        )

    def test_identidad_permanece_tras_entrega(self):
        sesion = str(uuid4())

        self.cola.guardar(
            self.evento,
            sesion_id=sesion,
            numero_evento=1,
        )

        self.cola.marcar_entregado(
            self.evento["referencia_externa"]
        )

        self.assertEqual(
            self.cola.listar_pendientes(),
            [],
        )

        # El evento entregado conserva su identidad.
        self.assertEqual(
            self.cola.buscar_por_movimiento(sesion, 1),
            self.evento,
        )


    def test_huella_persistente_detecta_movimiento_distinto(self):
        sesion = str(uuid4())
        huella_original = "a" * 64
        huella_distinta = "b" * 64

        self.assertTrue(
            self.cola.guardar(
                self.evento,
                sesion_id=sesion,
                numero_evento=1,
                huella_evento=huella_original,
            )
        )

        # Simular cierre y reapertura de SQLite.
        nueva_cola = EventOutbox(self.ruta)

        self.assertEqual(
            nueva_cola.buscar_por_movimiento(
                sesion,
                1,
                huella_evento=huella_original,
            ),
            self.evento,
        )

        # Misma sesion y numero, pero otra huella:
        # no debe aceptarse como el mismo movimiento.
        with self.assertRaises(ValueError):
            nueva_cola.buscar_por_movimiento(
                sesion,
                1,
                huella_evento=huella_distinta,
            )


if __name__ == "__main__":
    unittest.main()
