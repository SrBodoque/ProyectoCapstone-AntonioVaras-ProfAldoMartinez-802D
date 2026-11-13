
"""
Registra movimientos confirmados por el contador.

Convierte CountEvent a JSON y lo guarda en SQLite.

Utiliza:
- ID de sesion.
- Numero de evento.
- Huella SHA-256 del movimiento.

Evita duplicados y permite recuperar el UUID
y la fecha originales desde SQLite.

No utiliza la camara ni realiza solicitudes HTTP.
"""

import hashlib
import json

from dataclasses import asdict
from datetime import datetime
from uuid import UUID, uuid4

from .count_engine import CountEvent
from .count_event_adapter import adaptar_evento_conteo
from .event_outbox import EventOutbox


TIPOS_DJANGO = {
    "IN": "ENTRADA",
    "OUT": "SALIDA",
}


def calcular_huella_evento(evento: CountEvent) -> str:
    """
    Calcula una huella reproducible de los datos
    originales de un CountEvent.

    No genera UUID ni modifica el evento.
    """
    if not isinstance(evento, CountEvent):
        raise TypeError("Se requiere un CountEvent.")

    contenido = json.dumps(
        asdict(evento),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )

    return hashlib.sha256(
        contenido.encode("utf-8")
    ).hexdigest()


class CountEventRecorder:

    def __init__(
        self,
        cola: EventOutbox,
        *,
        fuente: str,
        sesion_id: str | None = None,
    ):
        if not isinstance(cola, EventOutbox):
            raise TypeError("Se requiere una EventOutbox.")

        if (
            not isinstance(fuente, str)
            or not fuente
            or fuente != fuente.strip()
            or len(fuente) > 80
        ):
            raise ValueError(
                "Identificador de fuente invalido."
            )

        # Una sesion nueva recibe un UUID4 nuevo.
        # Una sesion recuperada debe indicar su UUID anterior.
        if sesion_id is None:
            sesion_id = str(uuid4())

        try:
            identificador = UUID(sesion_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError(
                "ID de sesion invalido."
            ) from exc

        if (
            identificador.version != 4
            or str(identificador) != sesion_id
        ):
            raise ValueError(
                "Se requiere un ID de sesion UUID4 canonico."
            )

        self.cola = cola
        self.fuente = fuente
        self.sesion_id = sesion_id

        # Proteccion adicional dentro de esta instancia.
        self._registrados = {}

    def registrar(
        self,
        evento: CountEvent,
        *,
        ocurrido_en: datetime | None = None,
    ) -> dict:
        """
        Convierte y guarda un movimiento confirmado.

        Si el movimiento ya existe con la misma
        identidad y huella, devuelve su JSON original.

        Si la identidad corresponde a otro movimiento,
        se rechaza.

        No envia solicitudes HTTP.
        """

        # 1. Validar el evento recibido.
        if not isinstance(evento, CountEvent):
            raise TypeError("Se requiere un CountEvent.")

        if (
            type(evento.number) is not int
            or evento.number < 1
        ):
            raise ValueError(
                "Numero de evento invalido."
            )

        tipo_esperado = TIPOS_DJANGO.get(
            evento.direction
        )

        if tipo_esperado is None:
            raise ValueError(
                "La direccion debe ser IN u OUT."
            )

        # 2. Calcular la huella antes de recuperar
        # o guardar informacion.
        huella = calcular_huella_evento(evento)

        # 3. Revisar duplicados en memoria.
        anterior = self._registrados.get(
            evento.number
        )

        if anterior is not None:
            evento_original, datos_originales = anterior

            if evento != evento_original:
                raise ValueError(
                    "El numero de evento ya corresponde "
                    "a otro movimiento."
                )

            return dict(datos_originales)

        # 4. Buscar un movimiento anterior en SQLite,
        # exigiendo coincidencia de la huella.
        existente = self.cola.buscar_por_movimiento(
            self.sesion_id,
            evento.number,
            huella_evento=huella,
        )

        if existente is not None:
            if (
                existente["fuente"] != self.fuente
                or existente["tipo"] != tipo_esperado
            ):
                raise ValueError(
                    "El movimiento persistido no coincide "
                    "con la fuente o direccion."
                )

            # Recuperar UUID y fecha originales.
            self._registrados[evento.number] = (
                evento,
                dict(existente),
            )

            return dict(existente)

        # 5. Adaptar el movimiento nuevo.
        datos = adaptar_evento_conteo(
            evento,
            fuente=self.fuente,
            ocurrido_en=ocurrido_en,
        )

        # 6. Guardar el JSON, la identidad
        # y la huella en una misma operacion.
        guardado = self.cola.guardar(
            datos,
            sesion_id=self.sesion_id,
            numero_evento=evento.number,
            huella_evento=huella,
        )

        if not guardado:
            raise RuntimeError(
                "El movimiento no pudo guardarse "
                "como nuevo."
            )

        # 7. Recordar el movimiento solamente
        # despues de confirmar SQLite.
        self._registrados[evento.number] = (
            evento,
            dict(datos),
        )

        return dict(datos)
