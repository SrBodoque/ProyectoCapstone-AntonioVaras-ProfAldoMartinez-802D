
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from usuarios.models import Usuario
from sistema.models import (
    Alerta,
    Bano,
    EventoConteo,
    FuenteConteo,
    ReferenciaOcupacion,
)
from sistema.services.ocupacion import calcular_ocupacion

import hashlib
import json
from uuid import uuid4

from django.urls import reverse

from datetime import datetime

from sistema.services.conteos_diarios import obtener_conteos_diarios

from unittest.mock import patch

from sistema.services.resumen_conteo import obtener_resumen_bano
from django.test import override_settings
from django.core.exceptions import PermissionDenied
from sistema.services.referencias_ocupacion import (registrar_verificacion_bano_vacio,)
from django.test import Client


# ==========================================
# PRUEBA DE BASE DE DATOS AISLADA
# ==========================================

class PruebaBaseDatosAislada(TestCase):

    def test_modelo_referencia_ocupacion(self):
        bano = Bano.objects.create(
            nombre="Baño de prueba",
            ubicacion="Entorno de pruebas",
        )

        self.assertIsNotNone(bano.id)

        self.assertEqual(
            ReferenciaOcupacion.objects.count(),
            0,
        )


# ==========================================
# PRUEBAS DEL CÁLCULO DE OCUPACIÓN
# ==========================================

class PruebasOcupacion(TestCase):

    def setUp(self):
        self.bano = Bano.objects.create(
            nombre="Baño de ocupación",
            ubicacion="Laboratorio de pruebas",
        )

        self.supervisor = Usuario.objects.create_user(
            username="supervisor_prueba",
            email="supervisor.prueba@example.com",
            password="clave_solo_para_pruebas",
            rol=Usuario.Rol.SUPERVISOR,
        )

        self.fecha_base = timezone.now() - timedelta(hours=1)

    def crear_referencia(self, ocupacion=0, vigente=True):
        return ReferenciaOcupacion.objects.create(
            bano=self.bano,
            ocupacion_inicial=ocupacion,
            fecha_referencia=self.fecha_base,
            verificada_por=self.supervisor,
            vigente=vigente,
        )

    def crear_evento(self, tipo, segundos):
        return EventoConteo.objects.create(
            bano=self.bano,
            tipo=tipo,
            origen=EventoConteo.Origen.SIMULADO,
            fecha_evento=(
                self.fecha_base + timedelta(seconds=segundos)
            ),
        )

    # PRUEBA 1: SIN OCUPACIÓN INICIAL
    def test_sin_referencia_es_desconocida(self):
        resultado = calcular_ocupacion(self.bano.id)

        self.assertEqual(
            resultado["estado"],
            "DESCONOCIDA",
        )
        self.assertIsNone(resultado["ocupacion"])

    # PRUEBA 2: CINCO ENTRADAS Y DOS SALIDAS
    def test_calculo_ocupacion_conocida(self):
        self.crear_referencia(ocupacion=0)

        for segundo in [10, 20, 30, 40, 50]:
            self.crear_evento(
                EventoConteo.Tipo.ENTRADA,
                segundo,
            )

        for segundo in [60, 70]:
            self.crear_evento(
                EventoConteo.Tipo.SALIDA,
                segundo,
            )

        resultado = calcular_ocupacion(self.bano.id)

        self.assertEqual(resultado["estado"], "CONOCIDA")
        self.assertEqual(resultado["ocupacion"], 3)
        self.assertEqual(resultado["entradas"], 5)
        self.assertEqual(resultado["salidas"], 2)

    # PRUEBA 3: REFERENCIA INVALIDADA
    def test_referencia_invalidada(self):
        self.crear_referencia(
            ocupacion=0,
            vigente=False,
        )

        resultado = calcular_ocupacion(self.bano.id)

        self.assertEqual(
            resultado["estado"],
            "DESCONOCIDA",
        )
        self.assertIsNone(resultado["ocupacion"])

    # PRUEBA 4: MÁS SALIDAS QUE PERSONAS
    def test_ocupacion_inconsistente(self):
        self.crear_referencia(ocupacion=0)

        self.crear_evento(
            EventoConteo.Tipo.SALIDA,
            10,
        )

        resultado = calcular_ocupacion(self.bano.id)

        self.assertEqual(
            resultado["estado"],
            "INCONSISTENTE",
        )
        self.assertIsNone(resultado["ocupacion"])

    # PRUEBA 5: EVENTOS QUE LLEGAN DESORDENADOS
    def test_eventos_atrasados_ordenados_por_fecha(self):
        self.crear_referencia(ocupacion=0)

        # Primero se guarda una salida.
        self.crear_evento(
            EventoConteo.Tipo.SALIDA,
            20,
        )

        # Después llega una entrada más antigua.
        self.crear_evento(
            EventoConteo.Tipo.ENTRADA,
            10,
        )

        # Cronológicamente hubo entrada y luego salida.
        resultado = calcular_ocupacion(self.bano.id)

        self.assertEqual(
            resultado["estado"],
            "CONOCIDA",
        )
        self.assertEqual(resultado["ocupacion"], 0)



# ==========================================
# PRUEBAS DE LA API ENTRADA / SALIDA
# ==========================================

class PruebasApiConteo(TestCase):

    def setUp(self):
        self.bano = Bano.objects.create(
            nombre="Baño API de pruebas",
            ubicacion="Laboratorio",
            umbral_entradas=2,
            inicio_ciclo_conteo=(
                timezone.now() - timedelta(minutes=5)
            ),
        )

        # Credencial ficticia, exclusiva para las pruebas.
        self.token = "credencial_ficticia_pruebas_api"

        self.fuente = FuenteConteo.objects.create(
            nombre="Fuente de pruebas",
            identificador="fuente-api-pruebas",
            bano=self.bano,
            activa=True,
            credencial_hash=hashlib.sha256(
                self.token.encode("utf-8")
            ).hexdigest(),
        )

        self.url = reverse("api_eventos_conteo")
        self.fecha = timezone.now().isoformat()

    def enviar_evento(
        self,
        tipo,
        referencia=None,
        token=None,
    ):
        if referencia is None:
            referencia = str(uuid4())

        if token is None:
            token = self.token

        datos = {
            "fuente": self.fuente.identificador,
            "tipo": tipo,
            "referencia_externa": referencia,
            "ocurrido_en": self.fecha,
        }

        return self.client.post(
            self.url,
            data=json.dumps(datos),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    # PRUEBA 7: UNA SALIDA SE GUARDA
    def test_salida_se_guarda_sin_alerta(self):
        respuesta = self.enviar_evento(
            EventoConteo.Tipo.SALIDA,
        )

        self.assertEqual(respuesta.status_code, 201)

        self.assertEqual(
            EventoConteo.objects.filter(
                tipo=EventoConteo.Tipo.SALIDA,
            ).count(),
            1,
        )

        self.assertEqual(Alerta.objects.count(), 0)

    # PRUEBA 8: SOLO LAS ENTRADAS ACTIVAN ALERTAS
    def test_umbral_cuenta_solo_entradas(self):
        respuesta_1 = self.enviar_evento(
            EventoConteo.Tipo.ENTRADA,
        )
        self.assertEqual(respuesta_1.status_code, 201)

        respuesta_salida = self.enviar_evento(
            EventoConteo.Tipo.SALIDA,
        )
        self.assertEqual(respuesta_salida.status_code, 201)

        # Una entrada y una salida todavía
        # no alcanzan el umbral de dos entradas.
        self.assertEqual(Alerta.objects.count(), 0)

        respuesta_2 = self.enviar_evento(
            EventoConteo.Tipo.ENTRADA,
        )
        self.assertEqual(respuesta_2.status_code, 201)

        self.assertEqual(Alerta.objects.count(), 1)

        self.assertEqual(
            EventoConteo.objects.filter(
                tipo=EventoConteo.Tipo.ENTRADA,
            ).count(),
            2,
        )

    # PRUEBA 9: UNA SALIDA REPETIDA NO SE DUPLICA
    def test_salida_duplicada(self):
        referencia = str(uuid4())

        primera = self.enviar_evento(
            EventoConteo.Tipo.SALIDA,
            referencia=referencia,
        )

        segunda = self.enviar_evento(
            EventoConteo.Tipo.SALIDA,
            referencia=referencia,
        )

        self.assertEqual(primera.status_code, 201)
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(EventoConteo.objects.count(), 1)

    # PRUEBA 10: MISMO UUID CON OTRO TIPO
    def test_uuid_reutilizado_con_otro_tipo(self):
        referencia = str(uuid4())

        primera = self.enviar_evento(
            EventoConteo.Tipo.ENTRADA,
            referencia=referencia,
        )

        segunda = self.enviar_evento(
            EventoConteo.Tipo.SALIDA,
            referencia=referencia,
        )

        self.assertEqual(primera.status_code, 201)
        self.assertEqual(segunda.status_code, 409)
        self.assertEqual(EventoConteo.objects.count(), 1)

    # PRUEBA 11: CREDENCIAL INCORRECTA
    def test_token_incorrecto(self):
        respuesta = self.enviar_evento(
            EventoConteo.Tipo.ENTRADA,
            token="token_incorrecto",
        )

        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(EventoConteo.objects.count(), 0)



# ==========================================
# PRUEBAS DE CONTEOS DIARIOS
# ==========================================

class PruebasConteosDiarios(TestCase):

    def setUp(self):
        self.bano = Bano.objects.create(
            nombre="Baño de conteos diarios",
            ubicacion="Laboratorio de pruebas",
        )

    def fecha(self, dia, hora, minuto=0):
        """Crea una fecha con zona horaria de Chile."""
        return timezone.make_aware(
            datetime(2026, 11, dia, hora, minuto),
            timezone.get_default_timezone(),
        )

    def crear_evento(self, tipo, dia, hora, minuto=0):
        return EventoConteo.objects.create(
            bano=self.bano,
            tipo=tipo,
            origen=EventoConteo.Origen.SIMULADO,
            fecha_evento=self.fecha(dia, hora, minuto),
        )

    # PRUEBA 12: CONTAR SOLO LA JORNADA ACTUAL
    def test_entradas_y_salidas_de_la_jornada(self):
        # Pertenece a la jornada anterior.
        self.crear_evento(
            EventoConteo.Tipo.ENTRADA, 13, 5, 45
        )

        # Eventos de la jornada actual.
        self.crear_evento(
            EventoConteo.Tipo.ENTRADA, 13, 6, 5
        )
        self.crear_evento(
            EventoConteo.Tipo.SALIDA, 13, 6, 15
        )
        self.crear_evento(
            EventoConteo.Tipo.ENTRADA, 13, 6, 20
        )

        # Todavía no ha ocurrido a las 07:00.
        self.crear_evento(
            EventoConteo.Tipo.SALIDA, 13, 8, 0
        )

        resultado = obtener_conteos_diarios(
            self.bano.id,
            ahora=self.fecha(13, 7, 0),
        )

        self.assertEqual(resultado["entradas"], 2)
        self.assertEqual(resultado["salidas"], 1)

        # El historial conserva todos los eventos.
        self.assertEqual(
            EventoConteo.objects.filter(
                bano=self.bano
            ).count(),
            5,
        )

    # PRUEBA 13: ANTES DE LAS 06:00
    def test_madrugada_pertenece_a_jornada_anterior(self):
        self.crear_evento(
            EventoConteo.Tipo.ENTRADA, 13, 6, 10
        )
        self.crear_evento(
            EventoConteo.Tipo.SALIDA, 14, 5, 45
        )

        # Este evento pertenece a la próxima jornada.
        self.crear_evento(
            EventoConteo.Tipo.ENTRADA, 14, 6, 15
        )

        resultado = obtener_conteos_diarios(
            self.bano.id,
            ahora=self.fecha(14, 5, 59),
        )

        self.assertEqual(resultado["entradas"], 1)
        self.assertEqual(resultado["salidas"], 1)

        self.assertEqual(
            resultado["inicio_jornada"],
            self.fecha(13, 6, 0).isoformat(),
        )

    # PRUEBA 14: CAMBIO DE JORNADA SIN BORRAR DATOS
    def test_nueva_jornada_no_borra_historial(self):
        # Entrada de ayer.
        self.crear_evento(
            EventoConteo.Tipo.ENTRADA, 13, 10, 0
        )

        # Eventos de hoy.
        self.crear_evento(
            EventoConteo.Tipo.SALIDA, 14, 7, 0
        )
        self.crear_evento(
            EventoConteo.Tipo.ENTRADA, 14, 7, 30
        )

        resultado = obtener_conteos_diarios(
            self.bano.id,
            ahora=self.fecha(14, 8, 0),
        )

        self.assertEqual(resultado["entradas"], 1)
        self.assertEqual(resultado["salidas"], 1)

        # Los tres eventos permanecen registrados.
        self.assertEqual(
            EventoConteo.objects.filter(
                bano=self.bano
            ).count(),
            3,
        )


# ==========================================
# PRUEBAS DEL RESUMEN DE CONTEO
# ==========================================

class PruebasResumenConteo(TestCase):

    def setUp(self):
        self.zona = timezone.get_default_timezone()

        # Fecha fija para que las pruebas no dependan
        # de la hora real del computador.
        self.ahora = self.fecha(10, 0)

        self.bano = Bano.objects.create(
            nombre="Baño resumen",
            ubicacion="Laboratorio de pruebas",
            umbral_entradas=3,
            inicio_ciclo_conteo=self.fecha(9, 0),
        )

        self.supervisor = Usuario.objects.create_user(
            username="supervisor_resumen",
            email="supervisor.resumen@example.com",
            password="clave_solo_para_pruebas",
            rol=Usuario.Rol.SUPERVISOR,
        )

    def fecha(self, hora, minuto=0):
        return timezone.make_aware(
            datetime(2026, 11, 13, hora, minuto),
            self.zona,
        )

    def crear_evento(self, tipo, hora, minuto):
        return EventoConteo.objects.create(
            bano=self.bano,
            tipo=tipo,
            origen=EventoConteo.Origen.SIMULADO,
            fecha_evento=self.fecha(hora, minuto),
        )

    def crear_referencia(self, ocupacion_inicial=0):
        return ReferenciaOcupacion.objects.create(
            bano=self.bano,
            ocupacion_inicial=ocupacion_inicial,
            fecha_referencia=self.fecha(7, 0),
            verificada_por=self.supervisor,
            vigente=True,
        )

    def consultar_resumen(self):
        # Simular las 10:00 del 13 de noviembre.
        with patch(
            "django.utils.timezone.now",
            return_value=self.ahora,
        ):
            return obtener_resumen_bano(self.bano)

    # PRUEBA 15: LOS TRES CONTADORES SON INDEPENDIENTES
    def test_contadores_independientes(self):
        self.crear_referencia(ocupacion_inicial=0)

        # Entrada de la jornada, pero anterior
        # al ciclo de limpieza actual.
        self.crear_evento(
            EventoConteo.Tipo.ENTRADA, 8, 30
        )

        # Eventos posteriores al inicio del ciclo.
        self.crear_evento(
            EventoConteo.Tipo.ENTRADA, 9, 5
        )
        self.crear_evento(
            EventoConteo.Tipo.SALIDA, 9, 10
        )
        self.crear_evento(
            EventoConteo.Tipo.ENTRADA, 9, 20
        )
        self.crear_evento(
            EventoConteo.Tipo.SALIDA, 9, 30
        )

        resumen = self.consultar_resumen()

        # Limpieza: solo dos entradas desde las 09:00.
        self.assertEqual(resumen["entradas_ciclo"], 2)
        self.assertEqual(resumen["limite"], 3)

        # Jornada: tres entradas y dos salidas.
        self.assertEqual(resumen["entradas_jornada"], 3)
        self.assertEqual(resumen["salidas_jornada"], 2)

        # Ocupacion: 0 + 3 - 2 = 1.
        self.assertEqual(
            resumen["ocupacion_estado"],
            "CONOCIDA",
        )
        self.assertEqual(
            resumen["ocupacion_estimada"],
            1,
        )

        # Ningun evento fue eliminado.
        self.assertEqual(EventoConteo.objects.count(), 5)

    # PRUEBA 16: SIN REFERENCIA NO INVENTAR OCUPACION
    def test_sin_referencia_ocupacion_desconocida(self):
        self.crear_evento(
            EventoConteo.Tipo.ENTRADA, 9, 15
        )

        resumen = self.consultar_resumen()

        # Las entradas siguen contabilizandose.
        self.assertEqual(resumen["entradas_ciclo"], 1)
        self.assertEqual(resumen["entradas_jornada"], 1)

        # Pero la ocupacion inicial es desconocida.
        self.assertEqual(
            resumen["ocupacion_estado"],
            "DESCONOCIDA",
        )
        self.assertIsNone(
            resumen["ocupacion_estimada"]
        )

    # PRUEBA 17: UNA INCONSISTENCIA NO ALTERA LIMPIEZA
    def test_inconsistencia_no_altera_conteos(self):
        self.crear_referencia(ocupacion_inicial=0)

        # Se registra una salida con ocupacion cero.
        self.crear_evento(
            EventoConteo.Tipo.SALIDA, 9, 10
        )

        # Una entrada posterior no elimina
        # la inconsistencia anterior.
        self.crear_evento(
            EventoConteo.Tipo.ENTRADA, 9, 20
        )

        resumen = self.consultar_resumen()

        self.assertEqual(resumen["entradas_ciclo"], 1)
        self.assertEqual(resumen["entradas_jornada"], 1)
        self.assertEqual(resumen["salidas_jornada"], 1)

        self.assertEqual(
            resumen["ocupacion_estado"],
            "INCONSISTENTE",
        )
        self.assertIsNone(
            resumen["ocupacion_estimada"]
        )



# ==========================================
# PRUEBAS DEL DASHBOARD IN / OUT
# ==========================================

class PruebasDashboardInOut(TestCase):

    def setUp(self):
        self.zona = timezone.get_default_timezone()

        self.ahora = self.fecha(10, 0)

        self.bano = Bano.objects.create(
            nombre="Baño dashboard",
            ubicacion="Laboratorio de pruebas",
            umbral_entradas=3,
            inicio_ciclo_conteo=self.fecha(8, 0),
        )

        self.fuente = FuenteConteo.objects.create(
            nombre="DroidCam de pruebas",
            identificador="droidcam-demo",
            bano=self.bano,
            activa=True,
        )

        self.supervisor = Usuario.objects.create_user(
            username="supervisor_dashboard",
            email="supervisor.dashboard@example.com",
            password="clave_solo_para_pruebas",
            rol=Usuario.Rol.SUPERVISOR,
        )

        self.url = reverse("datos_dashboard_supervisor")

    def fecha(self, hora, minuto=0):
        return timezone.make_aware(
            datetime(2026, 11, 13, hora, minuto),
            self.zona,
        )

    def crear_evento(self, tipo, hora, minuto):
        return EventoConteo.objects.create(
            bano=self.bano,
            tipo=tipo,
            origen=EventoConteo.Origen.SIMULADO,
            fecha_evento=self.fecha(hora, minuto),
        )

    def consultar_dashboard(self):
        with patch(
            "django.utils.timezone.now",
            return_value=self.ahora,
        ):
            return self.client.get(self.url)

    # PRUEBA 18: EL DASHBOARD FUNCIONA DESACTIVADO
    @override_settings(CONTEO_IN_OUT_HABILITADO=False)
    def test_dashboard_con_funcion_desactivada(self):
        self.client.force_login(self.supervisor)

        # Si se intenta calcular ocupacion,
        # la prueba debe fallar.
        with patch(
            "sistema.views.obtener_resumen_bano",
            side_effect=AssertionError(
                "No debe consultar el resumen IN/OUT."
            ),
        ):
            respuesta = self.consultar_dashboard()

        self.assertEqual(respuesta.status_code, 200)

        conteo = respuesta.json()["conteo_demo"]

        self.assertIsNotNone(conteo)
        self.assertNotIn("resumen_in_out", conteo)

    # PRUEBA 19: EL DASHBOARD ENTREGA LOS TRES CONTEOS
    @override_settings(CONTEO_IN_OUT_HABILITADO=True)
    def test_dashboard_con_funcion_activada(self):
        self.client.force_login(self.supervisor)

        ReferenciaOcupacion.objects.create(
            bano=self.bano,
            ocupacion_inicial=0,
            fecha_referencia=self.fecha(8, 15),
            verificada_por=self.supervisor,
            vigente=True,
        )

        self.crear_evento(
            EventoConteo.Tipo.ENTRADA, 9, 0
        )
        self.crear_evento(
            EventoConteo.Tipo.SALIDA, 9, 10
        )
        self.crear_evento(
            EventoConteo.Tipo.ENTRADA, 9, 20
        )

        respuesta = self.consultar_dashboard()

        self.assertEqual(respuesta.status_code, 200)

        datos = respuesta.json()
        resumen = datos["conteo_demo"]["resumen_in_out"]

        # Limpieza: dos entradas.
        self.assertEqual(resumen["entradas_ciclo"], 2)
        self.assertEqual(resumen["limite"], 3)

        # Jornada: dos entradas y una salida.
        self.assertEqual(resumen["entradas_jornada"], 2)
        self.assertEqual(resumen["salidas_jornada"], 1)

        # Ocupacion: cero + dos - una = uno.
        self.assertEqual(
            resumen["ocupacion_estado"],
            "CONOCIDA",
        )
        self.assertEqual(
            resumen["ocupacion_estimada"],
            1,
        )

    # PRUEBA 20: UN TRABAJADOR NO PUEDE ACCEDER
    @override_settings(CONTEO_IN_OUT_HABILITADO=True)
    def test_trabajador_no_accede_al_dashboard(self):
        trabajador = Usuario.objects.create_user(
            username="trabajador_dashboard",
            email="trabajador.dashboard@example.com",
            password="clave_solo_para_pruebas",
            rol=Usuario.Rol.TRABAJADOR,
        )

        self.client.force_login(trabajador)

        respuesta = self.consultar_dashboard()

        self.assertEqual(respuesta.status_code, 403)



# ==========================================
# PRUEBAS VISUALES DEL HTML DEL DASHBOARD
# ==========================================

class PruebasHtmlDashboardInOut(TestCase):

    def setUp(self):
        self.bano = Bano.objects.create(
            nombre="Baño HTML de pruebas",
            ubicacion="Laboratorio",
        )

        FuenteConteo.objects.create(
            nombre="DroidCam HTML pruebas",
            identificador="droidcam-demo",
            bano=self.bano,
            activa=True,
        )

        self.supervisor = Usuario.objects.create_user(
            username="supervisor_html",
            email="supervisor.html@example.com",
            password="clave_solo_para_pruebas",
            rol=Usuario.Rol.SUPERVISOR,
        )

        self.client.force_login(self.supervisor)
        self.url = reverse("inicio_supervisor")

    # PRUEBA 21: TARJETAS OCULTAS POR DEFECTO
    @override_settings(CONTEO_IN_OUT_HABILITADO=False)
    def test_tarjetas_ocultas(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)

        # El contador original debe mantenerse.
        self.assertContains(
            respuesta,
            'id="conteo-demo-valor"',
        )

        # Las tarjetas nuevas no deben aparecer.
        self.assertNotContains(
            respuesta,
            'id="ocupacion-estimada-valor"',
        )

        self.assertNotContains(
            respuesta,
            'id="movimientos-jornada-valor"',
        )

    # PRUEBA 22: TARJETAS VISIBLES AL HABILITAR
    @override_settings(CONTEO_IN_OUT_HABILITADO=True)
    def test_tarjetas_visibles(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)

        # Se conserva el contador original.
        self.assertContains(
            respuesta,
            'id="conteo-demo-valor"',
        )

        # Aparecen las tarjetas nuevas.
        self.assertContains(
            respuesta,
            'id="ocupacion-estimada-valor"',
        )

        self.assertContains(
            respuesta,
            'id="ocupacion-estado-valor"',
        )

        self.assertContains(
            respuesta,
            'id="movimientos-jornada-valor"',
        )



# ==========================================
# PRUEBAS DE VERIFICACION DE BAÑO VACIO
# ==========================================

class PruebasVerificacionBanoVacio(TestCase):

    def setUp(self):
        self.bano = Bano.objects.create(
            nombre="Baño de verificacion",
            ubicacion="Laboratorio de pruebas",
            umbral_entradas=5,
            inicio_ciclo_conteo=(
                timezone.now() - timedelta(hours=2)
            ),
        )

        self.supervisor = Usuario.objects.create_user(
            username="supervisor_verificacion",
            email="supervisor.verificacion@example.com",
            password="clave_solo_para_pruebas",
            rol=Usuario.Rol.SUPERVISOR,
        )

        self.trabajador = Usuario.objects.create_user(
            username="trabajador_verificacion",
            email="trabajador.verificacion@example.com",
            password="clave_solo_para_pruebas",
            rol=Usuario.Rol.TRABAJADOR,
        )

    # PRUEBA 23: SUPERVISOR VERIFICA BAÑO VACIO
    def test_supervisor_registra_referencia_cero(self):
        referencia = registrar_verificacion_bano_vacio(
            bano_id=self.bano.id,
            supervisor=self.supervisor,
            observacion="Baño revisado y vacío.",
        )

        self.assertEqual(referencia.ocupacion_inicial, 0)
        self.assertTrue(referencia.vigente)
        self.assertEqual(
            referencia.verificada_por,
            self.supervisor,
        )
        self.assertEqual(
            referencia.observacion,
            "Baño revisado y vacío.",
        )

        resultado = calcular_ocupacion(self.bano.id)

        self.assertEqual(resultado["estado"], "CONOCIDA")
        self.assertEqual(resultado["ocupacion"], 0)

    # PRUEBA 24: TRABAJADOR NO PUEDE VERIFICAR
    def test_trabajador_no_puede_verificar(self):
        with self.assertRaises(PermissionDenied):
            registrar_verificacion_bano_vacio(
                bano_id=self.bano.id,
                supervisor=self.trabajador,
            )

        self.assertEqual(
            ReferenciaOcupacion.objects.count(),
            0,
        )

    # PRUEBA 25: SUPERVISOR INACTIVO NO PUEDE VERIFICAR
    def test_supervisor_inactivo_no_puede_verificar(self):
        self.supervisor.is_active = False
        self.supervisor.save(update_fields=["is_active"])

        with self.assertRaises(PermissionDenied):
            registrar_verificacion_bano_vacio(
                bano_id=self.bano.id,
                supervisor=self.supervisor,
            )

        self.assertEqual(
            ReferenciaOcupacion.objects.count(),
            0,
        )

    # PRUEBA 26: NUEVA VERIFICACION REEMPLAZA LA ANTERIOR
    def test_nueva_verificacion_invalida_anterior(self):
        anterior = registrar_verificacion_bano_vacio(
            bano_id=self.bano.id,
            supervisor=self.supervisor,
            observacion="Primera verificación.",
        )

        nueva = registrar_verificacion_bano_vacio(
            bano_id=self.bano.id,
            supervisor=self.supervisor,
            observacion="Segunda verificación.",
        )

        anterior.refresh_from_db()

        self.assertFalse(anterior.vigente)
        self.assertIsNotNone(
            anterior.fecha_invalidacion
        )

        self.assertTrue(nueva.vigente)

        self.assertEqual(
            ReferenciaOcupacion.objects.filter(
                bano=self.bano,
                vigente=True,
            ).count(),
            1,
        )

        # Se conserva el historial.
        self.assertEqual(
            ReferenciaOcupacion.objects.filter(
                bano=self.bano,
            ).count(),
            2,
        )

    # PRUEBA 27: NO BORRA EVENTOS NI REINICIA LIMPIEZA
    def test_verificacion_no_reinicia_conteo_limpieza(self):
        inicio_original = self.bano.inicio_ciclo_conteo

        # Entrada anterior a la verificacion fisica.
        EventoConteo.objects.create(
            bano=self.bano,
            tipo=EventoConteo.Tipo.ENTRADA,
            origen=EventoConteo.Origen.SIMULADO,
            fecha_evento=(
                timezone.now() - timedelta(minutes=1)
            ),
        )

        registrar_verificacion_bano_vacio(
            bano_id=self.bano.id,
            supervisor=self.supervisor,
        )

        resumen = obtener_resumen_bano(self.bano)

        # La entrada sigue contando para limpieza.
        self.assertEqual(
            resumen["entradas_ciclo"],
            1,
        )

        # La ocupacion comienza desde cero
        # porque el supervisor verifico el baño.
        self.assertEqual(
            resumen["ocupacion_estado"],
            "CONOCIDA",
        )
        self.assertEqual(
            resumen["ocupacion_estimada"],
            0,
        )

        # El evento historico sigue guardado.
        self.assertEqual(
            EventoConteo.objects.count(),
            1,
        )

        # No se modifico el inicio del ciclo.
        self.bano.refresh_from_db()

        self.assertEqual(
            self.bano.inicio_ciclo_conteo,
            inicio_original,
        )


# ==========================================
# PRUEBAS DE SEGURIDAD - VERIFICAR BAÑO VACIO
# ==========================================

class PruebasRutaVerificacionBano(TestCase):

    def setUp(self):
        self.bano = Bano.objects.create(
            nombre="Baño seguridad",
            ubicacion="Laboratorio de pruebas",
        )

        self.supervisor = Usuario.objects.create_user(
            username="supervisor_seguridad",
            email="supervisor.seguridad@example.com",
            password="clave_solo_para_pruebas",
            rol=Usuario.Rol.SUPERVISOR,
        )

        self.trabajador = Usuario.objects.create_user(
            username="trabajador_seguridad",
            email="trabajador.seguridad@example.com",
            password="clave_solo_para_pruebas",
            rol=Usuario.Rol.TRABAJADOR,
        )

        self.url = reverse(
            "verificar_bano_vacio",
            args=[self.bano.id],
        )

    # PRUEBA 28: FUNCIONALIDAD DESACTIVADA
    @override_settings(CONTEO_IN_OUT_HABILITADO=False)
    def test_verificacion_bloqueada_por_configuracion(self):
        self.client.force_login(self.supervisor)

        respuesta = self.client.post(
            self.url,
            {"confirmo_vacio": "si"},
        )

        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(
            ReferenciaOcupacion.objects.count(),
            0,
        )

    # PRUEBA 29: USUARIO SIN INICIAR SESION
    @override_settings(CONTEO_IN_OUT_HABILITADO=True)
    def test_usuario_anonimo_no_puede_verificar(self):
        respuesta = self.client.post(
            self.url,
            {"confirmo_vacio": "si"},
        )

        # Django redirige al inicio de sesion.
        self.assertEqual(respuesta.status_code, 302)

        self.assertEqual(
            ReferenciaOcupacion.objects.count(),
            0,
        )

    # PRUEBA 30: TRABAJADOR SIN PERMISOS
    @override_settings(CONTEO_IN_OUT_HABILITADO=True)
    def test_trabajador_no_puede_verificar(self):
        self.client.force_login(self.trabajador)

        respuesta = self.client.post(
            self.url,
            {"confirmo_vacio": "si"},
        )

        self.assertEqual(respuesta.status_code, 403)

        self.assertEqual(
            ReferenciaOcupacion.objects.count(),
            0,
        )

    # PRUEBA 31: FALTA CONFIRMACION EXPLICITA
    @override_settings(CONTEO_IN_OUT_HABILITADO=True)
    def test_supervisor_debe_confirmar(self):
        self.client.force_login(self.supervisor)

        respuesta = self.client.post(
            self.url,
            {"observacion": "Revisado"},
        )

        self.assertEqual(respuesta.status_code, 400)

        self.assertEqual(
            ReferenciaOcupacion.objects.count(),
            0,
        )

    # PRUEBA 32: SUPERVISOR REGISTRA VERIFICACION
    @override_settings(CONTEO_IN_OUT_HABILITADO=True)
    def test_supervisor_confirma_bano_vacio(self):
        self.client.force_login(self.supervisor)

        respuesta = self.client.post(
            self.url,
            {
                "confirmo_vacio": "si",
                "observacion": "Baño verificado vacío.",
            },
        )

        self.assertEqual(respuesta.status_code, 302)

        self.assertEqual(
            ReferenciaOcupacion.objects.count(),
            1,
        )

        referencia = ReferenciaOcupacion.objects.get()

        self.assertEqual(referencia.ocupacion_inicial, 0)
        self.assertTrue(referencia.vigente)
        self.assertEqual(
            referencia.verificada_por,
            self.supervisor,
        )

    # PRUEBA 33: PROTECCION CONTRA CSRF
    @override_settings(CONTEO_IN_OUT_HABILITADO=True)
    def test_solicitud_sin_csrf_es_rechazada(self):
        cliente_seguro = Client(
            enforce_csrf_checks=True,
        )

        cliente_seguro.force_login(self.supervisor)

        # Se intenta registrar sin enviar token CSRF.
        respuesta = cliente_seguro.post(
            self.url,
            {"confirmo_vacio": "si"},
        )

        self.assertEqual(respuesta.status_code, 403)

        self.assertEqual(
            ReferenciaOcupacion.objects.count(),
            0,
        )



# ==========================================
# PRUEBAS DEL FORMULARIO DE BAÑO VACÍO
# ==========================================

class PruebasFormularioBanoVacio(TestCase):

    def setUp(self):
        self.supervisor = Usuario.objects.create_user(
            username="supervisor_formulario",
            email="supervisor.formulario@example.com",
            password="clave_solo_para_pruebas",
            rol=Usuario.Rol.SUPERVISOR,
        )

        self.bano = Bano.objects.create(
            nombre="Baño conectado a cámara",
            ubicacion="Laboratorio de pruebas",
        )

        self.otro_bano = Bano.objects.create(
            nombre="Otro baño",
            ubicacion="Segundo laboratorio",
        )

        self.client.force_login(self.supervisor)

        self.url_dashboard = reverse("inicio_supervisor")

        self.url_verificacion = reverse(
            "verificar_bano_vacio",
            args=[self.bano.id],
        )

    def crear_fuente_demo(self):
        return FuenteConteo.objects.create(
            nombre="DroidCam de pruebas",
            identificador="droidcam-demo",
            bano=self.bano,
            activa=True,
        )

    # PRUEBA 34: FORMULARIO OCULTO
    @override_settings(CONTEO_IN_OUT_HABILITADO=False)
    def test_formulario_oculto_si_funcion_desactivada(self):
        self.crear_fuente_demo()

        respuesta = self.client.get(self.url_dashboard)

        self.assertEqual(respuesta.status_code, 200)

        self.assertNotContains(
            respuesta,
            'name="confirmo_vacio"',
        )

        # El contador antiguo sigue disponible.
        self.assertContains(
            respuesta,
            'id="conteo-demo-valor"',
        )

    # PRUEBA 35: FORMULARIO DEL BAÑO CORRECTO
    @override_settings(CONTEO_IN_OUT_HABILITADO=True)
    def test_formulario_apunta_al_bano_correcto(self):
        self.crear_fuente_demo()

        respuesta = self.client.get(self.url_dashboard)

        self.assertEqual(respuesta.status_code, 200)

        # El formulario apunta al baño de DroidCam.
        self.assertContains(
            respuesta,
            f'action="{self.url_verificacion}"',
        )

        # No debe apuntar al otro baño.
        url_incorrecta = reverse(
            "verificar_bano_vacio",
            args=[self.otro_bano.id],
        )

        self.assertNotContains(
            respuesta,
            f'action="{url_incorrecta}"',
        )

        # Debe existir la confirmación obligatoria.
        self.assertContains(
            respuesta,
            'name="confirmo_vacio"',
        )

        # Debe incluir protección CSRF.
        self.assertContains(
            respuesta,
            'name="csrfmiddlewaretoken"',
        )

    # PRUEBA 36: SIN CÁMARA NO APARECE EL FORMULARIO
    @override_settings(CONTEO_IN_OUT_HABILITADO=True)
    def test_sin_fuente_demo_no_muestra_formulario(self):
        respuesta = self.client.get(self.url_dashboard)

        self.assertEqual(respuesta.status_code, 200)

        self.assertNotContains(
            respuesta,
            'name="confirmo_vacio"',
        )


# ==========================================
# PRUEBAS DE EVENTOS ATRASADOS
# ==========================================

class PruebasEventosAtrasadosOcupacion(TestCase):

    def setUp(self):
        self.ahora = timezone.now()

        self.bano = Bano.objects.create(
            nombre="Baño eventos atrasados",
            ubicacion="Laboratorio de pruebas",
            inicio_ciclo_conteo=(
                self.ahora - timedelta(hours=2)
            ),
        )

        self.supervisor = Usuario.objects.create_user(
            username="supervisor_atrasados",
            email="supervisor.atrasados@example.com",
            password="clave_solo_para_pruebas",
            rol=Usuario.Rol.SUPERVISOR,
        )

        # Referencia verificada hace 10 minutos.
        self.referencia = ReferenciaOcupacion.objects.create(
            bano=self.bano,
            ocupacion_inicial=0,
            fecha_referencia=(
                self.ahora - timedelta(minutes=10)
            ),
            verificada_por=self.supervisor,
            vigente=True,
        )

    def registrar_evento(self, tipo, segundos):
        return EventoConteo.objects.create(
            bano=self.bano,
            tipo=tipo,
            origen=EventoConteo.Origen.SIMULADO,
            fecha_evento=(
                self.referencia.fecha_referencia
                + timedelta(seconds=segundos)
            ),
        )

    # PRUEBA 37
    # UNA ENTRADA ANTERIOR A LA VERIFICACION
    # LLEGA DESPUES AL SERVIDOR.
    def test_entrada_atrasada_anterior_a_referencia(self):

        # Primero llega una entrada posterior
        # a la verificacion.
        self.registrar_evento(
            EventoConteo.Tipo.ENTRADA,
            20,
        )

        # Despues llega una entrada que ocurrio
        # 30 segundos antes de la verificacion.
        self.registrar_evento(
            EventoConteo.Tipo.ENTRADA,
            -30,
        )

        resumen = obtener_resumen_bano(self.bano)

        # Ambas cuentan para el ciclo de limpieza.
        self.assertEqual(
            resumen["entradas_ciclo"],
            2,
        )

        # Solo la entrada posterior a la referencia
        # cuenta para la ocupacion estimada.
        self.assertEqual(
            resumen["ocupacion_estado"],
            "CONOCIDA",
        )

        self.assertEqual(
            resumen["ocupacion_estimada"],
            1,
        )

        self.assertEqual(
            EventoConteo.objects.count(),
            2,
        )

    # PRUEBA 38
    # LOS EVENTOS POSTERIORES A LA REFERENCIA
    # LLEGAN EN ORDEN INVERSO.
    def test_eventos_posteriores_llegan_desordenados(self):

        # Se registra primero la salida de +20 s.
        self.registrar_evento(
            EventoConteo.Tipo.SALIDA,
            20,
        )

        # Despues llega la entrada de +10 s.
        self.registrar_evento(
            EventoConteo.Tipo.ENTRADA,
            10,
        )

        # El orden real fue entrada y luego salida.
        resultado = calcular_ocupacion(self.bano.id)

        self.assertEqual(
            resultado["estado"],
            "CONOCIDA",
        )

        self.assertEqual(
            resultado["ocupacion"],
            0,
        )

    # PRUEBA 39
    # UNA SALIDA ATRASADA REVELA UNA INCONSISTENCIA.
    def test_salida_atrasada_revela_inconsistencia(self):

        # Llega primero una entrada que ocurrio
        # 20 segundos despues de la referencia.
        self.registrar_evento(
            EventoConteo.Tipo.ENTRADA,
            20,
        )

        # Luego llega una salida que realmente
        # ocurrio antes, a los +10 segundos.
        self.registrar_evento(
            EventoConteo.Tipo.SALIDA,
            10,
        )

        resultado = calcular_ocupacion(self.bano.id)

        # Cronologicamente hubo una salida
        # cuando la ocupacion inicial era cero.
        self.assertEqual(
            resultado["estado"],
            "INCONSISTENTE",
        )

        # No debemos mostrar un numero engañoso.
        self.assertIsNone(
            resultado["ocupacion"],
        )


# ==========================================
# PRUEBA DE EVENTOS CON FECHA FUTURA
# ==========================================

class PruebasEventosFuturosOcupacion(TestCase):

    def test_entrada_futura_no_aumenta_ocupacion(self):
        ahora = timezone.now()

        bano = Bano.objects.create(
            nombre="Baño evento futuro",
            ubicacion="Laboratorio de pruebas",
        )

        supervisor = Usuario.objects.create_user(
            username="supervisor_futuro",
            email="supervisor.futuro@example.com",
            password="clave_solo_para_pruebas",
            rol=Usuario.Rol.SUPERVISOR,
        )

        ReferenciaOcupacion.objects.create(
            bano=bano,
            ocupacion_inicial=0,
            fecha_referencia=ahora - timedelta(minutes=10),
            verificada_por=supervisor,
            vigente=True,
        )

        # Entrada registrada con fecha dos minutos futura.
        EventoConteo.objects.create(
            bano=bano,
            tipo=EventoConteo.Tipo.ENTRADA,
            origen=EventoConteo.Origen.SIMULADO,
            fecha_evento=ahora + timedelta(minutes=2),
        )

        resultado = calcular_ocupacion(bano.id)

        # Todavia no debe aumentar la ocupacion.
        self.assertEqual(resultado["estado"], "CONOCIDA")
        self.assertEqual(resultado["ocupacion"], 0)

        # El evento permanece guardado.
        self.assertEqual(EventoConteo.objects.count(), 1)
