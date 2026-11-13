
"""
Emisor de eventos IN/OUT hacia la API Django.

Lee eventos previamente guardados en SQLite.
Conserva su UUID y fecha originales.

No envia nada automaticamente al importar este modulo.
"""

import json

from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .event_outbox import EventOutbox


class DjangoEventSender:

    def __init__(
        self,
        cola: EventOutbox,
        *,
        url: str,
        token: str,
        transporte=None,
        timeout=5,
    ):
        if not isinstance(cola, EventOutbox):
            raise TypeError("Se requiere una EventOutbox.")

        partes = urlsplit(url)

        if (
            partes.scheme not in ("http", "https")
            or not partes.hostname
            or partes.username is not None
            or partes.password is not None
            or partes.fragment
        ):
            raise ValueError("URL de Django invalida.")

        # HTTP sin cifrado solo para Django local.
        if (
            partes.scheme == "http"
            and partes.hostname not in (
                "localhost",
                "127.0.0.1",
                "::1",
            )
        ):
            raise ValueError(
                "HTTP solo se permite para Django local."
            )

        if (
            not isinstance(token, str)
            or not token
            or any(caracter.isspace() for caracter in token)
        ):
            raise ValueError("Token Bearer invalido.")

        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not 0 < timeout <= 60
        ):
            raise ValueError("Timeout invalido.")

        self.cola = cola
        self.url = url
        self.token = token
        self.timeout = timeout

        # En las pruebas se reemplazara por una funcion falsa.
        self.transporte = (
            transporte
            if transporte is not None
            else self._enviar_http
        )

    @staticmethod
    def _enviar_http(url, token, datos, timeout):
        contenido = json.dumps(
            datos,
            ensure_ascii=False,
        ).encode("utf-8")

        solicitud = Request(
            url,
            data=contenido,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )

        try:
            with urlopen(
                solicitud,
                timeout=timeout,
            ) as respuesta:
                return respuesta.status

        except HTTPError as error:
            return error.code

    def procesar_pendientes(self, max_eventos=50):
        """
        Procesa eventos pendientes una sola vez.

        No reintenta automaticamente.
        Un proceso futuro podra volver a llamar al metodo.
        """

        if (
            type(max_eventos) is not int
            or not 1 <= max_eventos <= 100
        ):
            raise ValueError(
                "max_eventos debe estar entre 1 y 100."
            )

        resumen = {
            "entregados": 0,
            "conflictos": 0,
            "detenidos": 0,
        }

        pendientes = self.cola.listar_pendientes()

        for datos in pendientes[:max_eventos]:
            referencia = datos["referencia_externa"]

            try:
                codigo = self.transporte(
                    self.url,
                    self.token,
                    datos,
                    self.timeout,
                )

            except (URLError, OSError, TimeoutError):
                # Problema de conexion: conservar pendiente.
                resumen["detenidos"] += 1
                break

            if codigo in (200, 201):
                self.cola.marcar_entregado(referencia)
                resumen["entregados"] += 1

            elif codigo == 409:
                self.cola.marcar_conflicto(referencia)
                resumen["conflictos"] += 1

            else:
                # No confirmar algo que Django no acepto.
                resumen["detenidos"] += 1
                break

        return resumen
