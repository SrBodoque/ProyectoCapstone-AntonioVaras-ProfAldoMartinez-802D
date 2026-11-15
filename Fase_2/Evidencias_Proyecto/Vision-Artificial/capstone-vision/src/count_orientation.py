"""Confirmación explícita del significado físico de un perfil H4, sin editarlo."""

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import PROJECT_ROOT
from .zones import ZoneProfile, ZoneStore

ORIENTATION_PATH = PROJECT_ROOT / "config" / "counting.local.json"


def profile_hash(profile):
    data = json.dumps(profile.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class OrientedProfile:
    profile: ZoneProfile
    source_hash: str
    h4_a_role: str

    @property
    def description(self):
        a, b = ("A", "B") if self.h4_a_role == "exterior" else ("B", "A")
        return f"Conteo A=H4 {a} (exterior); Conteo B=H4 {b} (puerta)"


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Orientacion: clave duplicada {key}.")
        result[key] = value
    return result


def load_orientation(path, profile):
    path = Path(path)
    try:
        if path.is_symlink() or path.stat().st_size > 32768:
            raise ValueError("Confirmacion de orientacion enlazada o demasiado grande.")
        record = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_unique)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Falta una orientacion valida. Revise exterior/puerta y ejecute python -m src.count_orientation; no se reinterpretara el perfil H4.") from exc
    keys = {"schema_version", "profile_sha256", "profile_name", "h4_a_role",
            "reviewer", "confirmed", "confirmed_at"}
    if (not isinstance(record, dict) or set(record) != keys
            or type(record["schema_version"]) is not int or record["schema_version"] != 1
            or record["confirmed"] is not True or record["h4_a_role"] not in ("exterior", "puerta")
            or not isinstance(record["reviewer"], str) or not record["reviewer"].strip()
            or not isinstance(record["confirmed_at"], str) or not record["confirmed_at"].strip()):
        raise ValueError("Confirmacion de orientacion invalida; requiere revision humana explicita.")
    digest = profile_hash(profile)
    if record["profile_sha256"] != digest or record["profile_name"] != profile.name:
        raise ValueError("El perfil H4 cambio. Confirme nuevamente la orientacion en un archivo nuevo.")
    if record["h4_a_role"] == "exterior":
        logical = ZoneProfile.from_dict(profile.to_dict())
    else:
        logical = ZoneProfile.create(profile.name, profile.camera_index, profile.width, profile.height,
                                     profile.b, profile.a)
    return OrientedProfile(logical, digest, record["h4_a_role"])


def confirm_orientation(profile, role, reviewer, output, *, confirmed=False):
    if role not in ("exterior", "puerta") or not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("Indique el rol fisico de H4 A y un responsable no vacio.")
    if confirmed is not True:
        raise ValueError("Se requiere confirmar fisicamente exterior y puerta.")
    path = Path(output)
    if path.suffix.lower() != ".json" or path.is_symlink():
        raise ValueError("La salida debe ser un JSON nuevo y no enlazado.")
    record = dict(schema_version=1, profile_sha256=profile_hash(profile),
                  profile_name=profile.name, h4_a_role=role, reviewer=reviewer.strip(),
                  confirmed=True, confirmed_at=datetime.now(timezone.utc).isoformat())
    # No crea directorios ni reemplaza confirmaciones anteriores.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Confirma orientacion del perfil H4 activo sin modificarlo.")
    parser.add_argument("--h4-a-role", choices=("exterior", "puerta"), required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--confirm-exterior-door", action="store_true", required=True)
    parser.add_argument("--output", type=Path, default=ORIENTATION_PATH)
    args = parser.parse_args(argv)
    try:
        profile = ZoneStore().load_active()
        path = confirm_orientation(profile, args.h4_a_role, args.reviewer, args.output,
                                   confirmed=args.confirm_exterior_door)
        orientation = load_orientation(path, profile)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Orientacion no guardada: {exc}\n")
    print(f"Confirmacion nueva: {path}\n{orientation.description}\nPerfil H4 conservado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
