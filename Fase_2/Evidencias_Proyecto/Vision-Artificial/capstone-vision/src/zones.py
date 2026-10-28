"""Hito 4: geometría normalizada y perfiles locales. Sin IA, cámara ni conteo."""

import json
import math
import os
import re
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .config import PROJECT_ROOT

ZONES_DIR = PROJECT_ROOT / "config" / "zones"
MAX_POINTS = 16
EPS = 1e-9
MIN_AREA = 1e-6
COLORS = {"A": (230, 150, 30), "B": (0, 180, 255)}  # BGR


class ZoneError(ValueError):
    """Configuración ausente, inválida o incompatible; mensaje apto para consola."""


def _number(value):
    return type(value) in (int, float) and -1e100 < value < 1e100 and math.isfinite(value)


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(p, a, b):
    return (abs(_cross(a, b, p)) <= EPS
            and min(a[0], b[0]) - EPS <= p[0] <= max(a[0], b[0]) + EPS
            and min(a[1], b[1]) - EPS <= p[1] <= max(a[1], b[1]) + EPS)


def _intersects(a, b, c, d):
    ab_c, ab_d, cd_a, cd_b = _cross(a, b, c), _cross(a, b, d), _cross(c, d, a), _cross(c, d, b)
    if ((ab_c > EPS and ab_d < -EPS or ab_c < -EPS and ab_d > EPS)
            and (cd_a > EPS and cd_b < -EPS or cd_a < -EPS and cd_b > EPS)):
        return True
    return any((_on_segment(c, a, b), _on_segment(d, a, b),
                _on_segment(a, c, d), _on_segment(b, c, d)))


def signed_area(points):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1])) / 2


def validate_polygon(points):
    if not isinstance(points, (list, tuple)) or not 3 <= len(points) <= MAX_POINTS:
        raise ZoneError(f"Cada zona requiere entre 3 y {MAX_POINTS} vértices.")
    normalized = []
    for p in points:
        if (not isinstance(p, (list, tuple)) or len(p) != 2
                or any(not _number(v) or not 0 <= v <= 1 for v in p)):
            raise ZoneError("Coordenadas de zona: dos números finitos entre 0 y 1.")
        point = (float(p[0]), float(p[1]))
        if any(math.dist(point, q) <= EPS for q in normalized):
            raise ZoneError("Hay vértices repetidos; no repita el primero al cerrar.")
        normalized.append(point)
    points = tuple(normalized)
    n = len(points)
    for i, b in enumerate(points):
        a, c = points[i - 1], points[(i + 1) % n]
        if (abs(_cross(a, b, c)) <= EPS
                and (a[0] - b[0]) * (c[0] - b[0]) + (a[1] - b[1]) * (c[1] - b[1]) > EPS):
            raise ZoneError("El polígono tiene segmentos superpuestos o retrocesos.")
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            if _intersects(points[i], points[(i + 1) % n], points[j], points[(j + 1) % n]):
                raise ZoneError("El polígono se autointersecta o toca a sí mismo.")
    if abs(signed_area(points)) <= MIN_AREA:
        raise ZoneError("El polígono es degenerado o tiene un área demasiado pequeña.")
    return points


def point_location(point, polygon):
    """1 interior, 0 borde, -1 exterior. Sin rasterizar el frame."""
    inside = False
    x, y = point
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if _on_segment(point, a, b):
            return 0
        if (a[1] > y) != (b[1] > y):
            if x < a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
                inside = not inside
    return 1 if inside else -1


def _triangles(polygon):
    """Ear clipping para polígonos simples; solo se usa al validar/guardar."""
    points = list(polygon if signed_area(polygon) > 0 else tuple(reversed(polygon)))
    # Elimina vértices colineales redundantes de la copia de trabajo.
    changed = True
    while changed and len(points) > 3:
        changed = False
        for i in range(len(points)):
            if abs(_cross(points[i - 1], points[i], points[(i + 1) % len(points)])) <= EPS:
                del points[i]; changed = True; break
    triangles = []
    while len(points) > 3:
        for i, b in enumerate(points):
            a, c = points[i - 1], points[(i + 1) % len(points)]
            if _cross(a, b, c) <= EPS:
                continue
            if any(point_location(p, (a, b, c)) >= 0 for j, p in enumerate(points)
                   if j not in ((i - 1) % len(points), i, (i + 1) % len(points))):
                continue
            triangles.append((a, b, c)); del points[i]; break
        else:
            raise ZoneError("No se pudo validar el interior del polígono.")
    triangles.append(tuple(points))
    return triangles


def _triangle_overlap(a, b):
    # SAT: compartir solo borde/punto no es superposición de interiores.
    for triangle in (a, b):
        for p, q in zip(triangle, triangle[1:] + triangle[:1]):
            length = math.dist(p, q)
            nx, ny = -(q[1] - p[1]) / length, (q[0] - p[0]) / length
            aa = [x * nx + y * ny for x, y in a]
            bb = [x * nx + y * ny for x, y in b]
            if min(max(aa), max(bb)) - max(min(aa), min(bb)) <= EPS:
                return False
    return True


def validate_zones(a, b):
    a, b = validate_polygon(a), validate_polygon(b)
    ta, tb = _triangles(a), _triangles(b)
    if any(_triangle_overlap(x, y) for x in ta for y in tb):
        raise ZoneError("Zona A y Zona B superponen sus interiores; separe o ajuste los polígonos.")
    return a, b


def validate_name(name):
    reserved = {"active", "con", "prn", "aux", "nul", *[f"com{i}" for i in range(10)],
                *[f"lpt{i}" for i in range(10)]}
    if (not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", name)
            or name in reserved):
        raise ZoneError("Nombre: 1–48 caracteres, empezar con letra minúscula; usar a-z, 0-9, _ o -. Sin rutas ni nombres reservados.")
    return name


def _size(width, height):
    if any(type(v) is not int or not 2 <= v <= 16384 for v in (width, height)):
        raise ZoneError("Resolución de referencia inválida (2–16384 píxeles por dimensión).")


@dataclass(frozen=True)
class ZoneProfile:
    name: str
    camera_index: int
    width: int
    height: int
    a: tuple
    b: tuple

    @classmethod
    def create(cls, name, camera_index, width, height, a, b):
        validate_name(name); _size(width, height)
        if type(camera_index) is not int or not 0 <= camera_index <= 2**31 - 1:
            raise ZoneError("Índice de cámara inválido.")
        a, b = validate_zones(a, b)
        return cls(name, camera_index, width, height, a, b)

    def to_dict(self):
        return {"schema_version": 1, "profile_name": self.name, "camera_index": self.camera_index,
                "reference_size": [self.width, self.height], "aspect_ratio": self.width / self.height,
                "zones": {"A": [list(p) for p in self.a], "B": [list(p) for p in self.b]}}

    @classmethod
    def from_dict(cls, data):
        if (not isinstance(data, dict) or set(data) != {"schema_version", "profile_name", "camera_index",
                "reference_size", "aspect_ratio", "zones"}
                or type(data["schema_version"]) is not int or data["schema_version"] != 1):
            raise ZoneError("Formato de perfil de zonas inválido o versión no soportada.")
        size, regions = data["reference_size"], data["zones"]
        if not isinstance(size, list) or len(size) != 2 or not isinstance(regions, dict) or set(regions) != {"A", "B"}:
            raise ZoneError("El perfil necesita resolución y exactamente Zona A y Zona B.")
        profile = cls.create(data["profile_name"], data["camera_index"], *size, regions["A"], regions["B"])
        if not _number(data["aspect_ratio"]) or not math.isclose(data["aspect_ratio"], profile.width / profile.height, rel_tol=1e-9):
            raise ZoneError("La relación de aspecto del perfil no coincide con su resolución.")
        return profile

    def check_camera(self, camera_index, width, height):
        _size(width, height)
        if camera_index != self.camera_index:
            raise ZoneError("Cambió el índice de cámara. Recalibre con python -m src.zone_calibrator; no se aplicarán estas zonas.")
        if not math.isclose(width / height, self.width / self.height, rel_tol=.005):
            raise ZoneError("Cambió la relación de aspecto. Recalibre con python -m src.zone_calibrator; no se aplicarán estas zonas.")

    def classify(self, point, width, height):
        _size(width, height)
        if len(point) != 2 or any(not _number(v) for v in point):
            raise ZoneError("Posición de persona no finita.")
        x, y = point[0] / width, point[1] / height
        if not 0 <= x <= 1 or not 0 <= y <= 1:
            return "FUERA"
        # Borde exterior incluido. En un borde compartido, A tiene prioridad.
        if point_location((x, y), self.a) >= 0:
            return "A"
        if point_location((x, y), self.b) >= 0:
            return "B"
        return "FUERA"


def bottom_center(box):
    values = (box.x1, box.y1, box.x2, box.y2)
    if any(not _number(v) for v in values) or box.x2 < box.x1 or box.y2 < box.y1:
        raise ZoneError("Bounding box inválido para bottom-center.")
    return (box.x1 + box.x2) / 2, box.y2


def pixel_point(point, width, height):
    return point[0] * width, point[1] * height


def normalized_point(x, y, width, height):
    _size(width, height)
    if not 0 <= x < width or not 0 <= y < height:
        return None  # Mouse fuera de la imagen, por ejemplo en la ayuda.
    return x / width, y / height


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ZoneError("JSON con claves repetidas.")
        result[key] = value
    return result


class ZoneStore:
    """Perfiles por nombre y una instantánea activa; lectura nunca escribe."""

    def __init__(self, directory=ZONES_DIR):
        self.directory = Path(directory)
        if self.directory.is_symlink():
            raise ZoneError("El directorio de zonas no puede ser un enlace simbólico.")
        self.directory = self.directory.resolve()

    def _path(self, name):
        path = self.directory / (validate_name(name) + ".json")
        if path.is_symlink():
            raise ZoneError("No se admiten perfiles enlazados a otros archivos.")
        return path

    def names(self):
        result = []
        if self.directory.exists():
            for p in self.directory.glob("*.json"):
                if p.name == "active.json":
                    continue
                try:
                    validate_name(p.stem)
                    if p.is_file() and not p.is_symlink(): result.append(p.stem)
                except ZoneError:
                    continue
        return sorted(result)

    def _read(self, path):
        try:
            if path.is_symlink() or path.stat().st_size > 65536:
                raise ZoneError("Archivo de zonas enlazado o demasiado grande.")
            return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_unique_pairs)
        except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ZoneError(f"No se pudo leer la configuración de zonas {path.name}: {exc}") from exc

    def load(self, name):
        profile = ZoneProfile.from_dict(self._read(self._path(name)))
        if profile.name != name:
            raise ZoneError("El nombre interno del perfil no coincide con el archivo.")
        return profile

    def load_active(self):
        path = self.directory / "active.json"
        if not path.exists() and not path.is_symlink():
            raise ZoneError("No existe una configuración activa de zonas. Ejecute primero: python -m src.zone_calibrator")
        data = self._read(path)
        if not isinstance(data, dict) or set(data) != {"active_profile", "calibration"}:
            raise ZoneError("El selector activo de zonas es inválido. Revíselo en zone_calibrator.")
        profile = ZoneProfile.from_dict(data["calibration"])
        if profile.name != data["active_profile"]:
            raise ZoneError("El perfil activo no coincide con su calibración.")
        return profile

    @contextmanager
    def _writer(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        lock = self.directory / ".write-lock"
        try:
            lock.mkdir()
        except FileExistsError as exc:
            raise ZoneError("Otro guardado está en curso (.write-lock). Consulte la guía si quedó tras una interrupción.") from exc
        try:
            yield
        finally:
            lock.rmdir()

    def _atomic(self, path, data):
        if path.is_symlink():
            raise ZoneError("No se sobrescriben enlaces simbólicos de configuración.")
        temporary = self.directory / (".pending-" + uuid.uuid4().hex)
        try:
            with temporary.open("xb") as stream:
                stream.write((json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8"))
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def _activate(self, profile):
        self._atomic(self.directory / "active.json", {"active_profile": profile.name, "calibration": profile.to_dict()})

    def save_and_activate(self, profile, *, overwrite=False):
        profile = ZoneProfile.from_dict(profile.to_dict())
        try:
            with self._writer():
                path = self._path(profile.name)
                if path.exists() and not overwrite:
                    raise ZoneError("El perfil ya existe; confirme explícitamente la sobrescritura.")
                self._atomic(path, profile.to_dict())
                try:
                    self._activate(profile)
                except OSError as exc:
                    raise ZoneError("El perfil se guardó, pero no pudo activarse. La calibración activa anterior sigue intacta.") from exc
        except OSError as exc:
            raise ZoneError(f"No se pudieron guardar las zonas: {exc}") from exc

    def activate(self, name, *, expected=None):
        try:
            with self._writer():
                profile = self.load(name)
                if expected is not None and profile != expected:
                    raise ZoneError("El perfil cambió; vuelva a cargarlo antes de activarlo.")
                self._activate(profile)
                return profile
        except OSError as exc:
            raise ZoneError(f"No se pudo activar el perfil: {exc}") from exc


class ZoneObservations:
    """Última observación por ID continuo; debounce visual, sin eventos ni conteos."""

    def __init__(self, stable_frames=3, recent_frames=30):
        self.stable_frames = stable_frames
        self.recent_frames = recent_frames
        self._states = {}
        self._frame = 0

    def update(self, observations):
        self._frame += 1
        current = dict(observations)
        self._states = {key: value for key, value in self._states.items() if key in current}
        transitions = {}
        for identifier, zone in current.items():
            state = self._states.setdefault(identifier, {"candidate": zone, "count": 0, "stable": None,
                                                        "transition": None, "expires": 0})
            if state["candidate"] != zone:
                state["candidate"], state["count"] = zone, 0
            state["count"] = min(state["count"] + 1, self.stable_frames)
            if state["count"] >= self.stable_frames and state["stable"] != zone:
                if state["stable"] is not None:
                    state["transition"] = f"{state['stable']} -> {zone}"
                    state["expires"] = self._frame + self.recent_frames
                state["stable"] = zone
            transitions[identifier] = state["transition"] if self._frame < state["expires"] else None
        return transitions


def draw_regions(cv2, frame, polygons, closed=None):
    """Superposición únicamente para presentación; no calcular pertenencia por imagen."""
    import numpy as np
    height, width = frame.shape[:2]
    overlay = frame.copy()
    converted = {}
    for name, points in polygons.items():
        if not points: continue
        pts = np.array([(min(width - 1, max(0, round(x * width))),
                         min(height - 1, max(0, round(y * height)))) for x, y in points], dtype=np.int32)
        converted[name] = pts
        if len(pts) >= 3 and (closed is None or closed[name]):
            cv2.fillPoly(overlay, [pts], COLORS[name])
    cv2.addWeighted(overlay, .20, frame, .80, 0, dst=frame)
    for name, pts in converted.items():
        cv2.polylines(frame, [pts], closed is None or closed[name], COLORS[name], 2)
        position = tuple(int(v) for v in pts[0])
        cv2.putText(frame, f"ZONA {name}", (max(4, position[0]), max(18, position[1] - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, .65, COLORS[name], 2, cv2.LINE_AA)
