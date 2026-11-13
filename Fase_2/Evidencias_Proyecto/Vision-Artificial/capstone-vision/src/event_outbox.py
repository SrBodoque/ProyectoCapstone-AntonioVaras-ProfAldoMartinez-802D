
"""
Cola SQLite persistente para eventos IN/OUT.

Conserva UUID, fecha, identidad de sesion y huella
del movimiento antes del envio a Django.

No realiza solicitudes HTTP.
"""

import json
import sqlite3

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID


class EventOutbox:

    def __init__(self, ruta_db):
        self.ruta_db = Path(ruta_db)

        with closing(
            sqlite3.connect(self.ruta_db, timeout=10)
        ) as conexion:
            with conexion:
                conexion.execute("""
                    CREATE TABLE IF NOT EXISTS eventos (
                        referencia_externa TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL,
                        estado TEXT NOT NULL DEFAULT 'PENDIENTE'
                            CHECK (
                                estado IN (
                                    'PENDIENTE',
                                    'ENTREGADO',
                                    'CONFLICTO'
                                )
                            ),
                        creado_en TEXT NOT NULL
                    )
                """)

                columnas = {
                    fila[1]
                    for fila in conexion.execute(
                        "PRAGMA table_info(eventos)"
                    )
                }

                # Migraciones compatibles con versiones anteriores.
                if "sesion_id" not in columnas:
                    conexion.execute(
                        "ALTER TABLE eventos "
                        "ADD COLUMN sesion_id TEXT"
                    )

                if "numero_evento" not in columnas:
                    conexion.execute(
                        "ALTER TABLE eventos "
                        "ADD COLUMN numero_evento INTEGER"
                    )

                if "huella_evento" not in columnas:
                    conexion.execute(
                        "ALTER TABLE eventos "
                        "ADD COLUMN huella_evento TEXT"
                    )

                conexion.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS
                        idx_evento_sesion_numero
                    ON eventos (sesion_id, numero_evento)
                """)

    @staticmethod
    def _validar_identidad(sesion_id, numero_evento):
        if sesion_id is None and numero_evento is None:
            return

        if (
            not isinstance(sesion_id, str)
            or type(numero_evento) is not int
            or numero_evento < 1
        ):
            raise ValueError(
                "Se requiere ID de sesion y numero positivo."
            )

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
                "Se requiere ID de sesion UUID4 canonico."
            )

    @staticmethod
    def _validar_huella(huella_evento):
        if huella_evento is None:
            return

        if (
            not isinstance(huella_evento, str)
            or len(huella_evento) != 64
            or any(
                caracter not in "0123456789abcdef"
                for caracter in huella_evento
            )
        ):
            raise ValueError(
                "La huella debe ser SHA-256 hexadecimal."
            )

    def buscar_por_movimiento(
        self,
        sesion_id,
        numero_evento,
        *,
        huella_evento=None,
    ):
        """
        Recupera el JSON original del movimiento.

        Cuando se proporciona una huella, exige
        que coincida con la guardada en SQLite.
        """
        self._validar_identidad(
            sesion_id,
            numero_evento,
        )
        self._validar_huella(huella_evento)

        if sesion_id is None:
            raise ValueError(
                "Se requiere una identidad de movimiento."
            )

        with closing(
            sqlite3.connect(self.ruta_db, timeout=10)
        ) as conexion:
            fila = conexion.execute(
                """
                SELECT payload_json, huella_evento
                FROM eventos
                WHERE sesion_id = ?
                  AND numero_evento = ?
                """,
                (sesion_id, numero_evento),
            ).fetchone()

        if fila is None:
            return None

        if huella_evento is not None:
            if fila[1] is None:
                raise ValueError(
                    "Movimiento antiguo sin huella; "
                    "requiere revision antes de recuperarlo."
                )

            if fila[1] != huella_evento:
                raise ValueError(
                    "La sesion y el numero corresponden "
                    "a un movimiento diferente."
                )

        return json.loads(fila[0])

    def guardar(
        self,
        datos,
        *,
        sesion_id=None,
        numero_evento=None,
        huella_evento=None,
    ):
        """
        Guarda un evento nuevo.

        True: evento nuevo guardado.
        False: mismo UUID, datos e identidad.

        Rechaza reutilizar una identidad con
        informacion diferente.
        """
        self._validar_identidad(
            sesion_id,
            numero_evento,
        )
        self._validar_huella(huella_evento)

        if huella_evento is not None and sesion_id is None:
            raise ValueError(
                "La huella requiere identidad de sesion."
            )

        campos = {
            "fuente",
            "tipo",
            "referencia_externa",
            "ocurrido_en",
        }

        if (
            not isinstance(datos, dict)
            or set(datos) != campos
        ):
            raise ValueError(
                "El evento no tiene los cuatro "
                "campos requeridos."
            )

        if (
            not isinstance(datos["fuente"], str)
            or not datos["fuente"]
            or datos["tipo"] not in ("ENTRADA", "SALIDA")
        ):
            raise ValueError(
                "Fuente o tipo de evento invalido."
            )

        try:
            identificador = UUID(
                datos["referencia_externa"]
            )
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError(
                "Referencia externa invalida."
            ) from exc

        if (
            identificador.version != 4
            or str(identificador)
            != datos["referencia_externa"]
        ):
            raise ValueError(
                "Se requiere un UUID4 canonico."
            )

        try:
            fecha = datetime.fromisoformat(
                datos["ocurrido_en"]
            )
        except (ValueError, TypeError) as exc:
            raise ValueError(
                "La fecha del evento no es valida."
            ) from exc

        if (
            fecha.tzinfo is None
            or fecha.utcoffset() is None
        ):
            raise ValueError(
                "La fecha debe incluir zona horaria."
            )

        contenido = json.dumps(
            datos,
            ensure_ascii=False,
            sort_keys=True,
        )

        with closing(
            sqlite3.connect(self.ruta_db, timeout=10)
        ) as conexion:
            with conexion:
                conexion.execute("BEGIN IMMEDIATE")

                existente = conexion.execute(
                    """
                    SELECT
                        payload_json,
                        sesion_id,
                        numero_evento,
                        huella_evento
                    FROM eventos
                    WHERE referencia_externa = ?
                    """,
                    (datos["referencia_externa"],),
                ).fetchone()

                if existente is not None:
                    if json.loads(existente[0]) != datos:
                        raise ValueError(
                            "UUID existente con datos diferentes."
                        )

                    if (
                        existente[1],
                        existente[2],
                        existente[3],
                    ) != (
                        sesion_id,
                        numero_evento,
                        huella_evento,
                    ):
                        raise ValueError(
                            "UUID existente con otra identidad "
                            "o huella de movimiento."
                        )

                    return False

                if sesion_id is not None:
                    repetido = conexion.execute(
                        """
                        SELECT referencia_externa
                        FROM eventos
                        WHERE sesion_id = ?
                          AND numero_evento = ?
                        """,
                        (sesion_id, numero_evento),
                    ).fetchone()

                    if repetido is not None:
                        raise ValueError(
                            "Movimiento existente con otro UUID."
                        )

                conexion.execute(
                    """
                    INSERT INTO eventos (
                        referencia_externa,
                        payload_json,
                        estado,
                        creado_en,
                        sesion_id,
                        numero_evento,
                        huella_evento
                    )
                    VALUES (
                        ?, ?, 'PENDIENTE', ?, ?, ?, ?
                    )
                    """,
                    (
                        datos["referencia_externa"],
                        contenido,
                        datetime.now(
                            timezone.utc
                        ).isoformat(),
                        sesion_id,
                        numero_evento,
                        huella_evento,
                    ),
                )

                return True

    def listar_pendientes(self):
        """Devuelve el JSON de los eventos pendientes."""
        with closing(
            sqlite3.connect(self.ruta_db, timeout=10)
        ) as conexion:
            filas = conexion.execute(
                """
                SELECT payload_json
                FROM eventos
                WHERE estado = 'PENDIENTE'
                ORDER BY creado_en, rowid
                """
            ).fetchall()

        return [
            json.loads(fila[0])
            for fila in filas
        ]

    def _cambiar_estado(
        self,
        referencia_externa,
        nuevo_estado,
    ):
        if nuevo_estado not in (
            "ENTREGADO",
            "CONFLICTO",
        ):
            raise ValueError("Estado final invalido.")

        with closing(
            sqlite3.connect(self.ruta_db, timeout=10)
        ) as conexion:
            with conexion:
                resultado = conexion.execute(
                    """
                    UPDATE eventos
                    SET estado = ?
                    WHERE referencia_externa = ?
                      AND estado = 'PENDIENTE'
                    """,
                    (nuevo_estado, referencia_externa),
                )

                if resultado.rowcount == 1:
                    return True

                fila = conexion.execute(
                    """
                    SELECT estado
                    FROM eventos
                    WHERE referencia_externa = ?
                    """,
                    (referencia_externa,),
                ).fetchone()

                if fila is None:
                    raise ValueError("Evento desconocido.")

                if fila[0] != nuevo_estado:
                    raise ValueError(
                        "El evento ya tiene otro estado final."
                    )

                return False

    def marcar_entregado(self, referencia_externa):
        return self._cambiar_estado(
            referencia_externa,
            "ENTREGADO",
        )

    def marcar_conflicto(self, referencia_externa):
        return self._cambiar_estado(
            referencia_externa,
            "CONFLICTO",
        )
