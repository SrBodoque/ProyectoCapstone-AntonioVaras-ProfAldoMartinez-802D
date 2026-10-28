"""Editor visual de zonas: python -m src.zone_calibrator. Sin cargar IA."""

import logging
import math
import os
import sys
import textwrap
import unicodedata

from .config import load_config
from .zones import (COLORS, MAX_POINTS, ZoneError, ZoneProfile, ZoneStore,
                    draw_regions, normalized_point, validate_name, validate_polygon)

LOGGER = logging.getLogger(__name__)
WINDOW = "CAPSTONE - Calibrador de zonas A/B"


class CalibrationEditor:
    """Estado de edición de geometría, separado de cámara/frames y eventos OpenCV."""

    def __init__(self, store, camera_index, width, height):
        self.store, self.camera_index = store, camera_index
        self.width, self.height = width, height
        self.selected = "A"
        self.name = ""
        self.active_name = "ninguno"
        self.polygons = {"A": [], "B": []}
        self.closed = {"A": False, "B": False}
        self.loaded = None
        self.incompatible = ""
        self.frozen = False
        self.drag = None
        self.mode = "edit"
        self.pending = None
        self.name_input = ""
        self.profiles = []
        self.profile_index = 0
        self.exit_requested = False
        self.status = "Dibuje A y B; no hay zonas predeterminadas."
        self._baseline = self._fingerprint()
        try:
            profile = store.load_active()
            self.active_name = profile.name
            self._load(profile)
        except ZoneError as exc:
            self.status = str(exc)

    def _fingerprint(self):
        return (self.name, tuple(self.polygons["A"]), tuple(self.polygons["B"]),
                self.closed["A"], self.closed["B"])

    @property
    def dirty(self):
        return self._fingerprint() != self._baseline

    def _load(self, profile):
        self.name, self.loaded = profile.name, profile
        self.polygons = {"A": list(profile.a), "B": list(profile.b)}
        self.closed = {"A": True, "B": True}
        self.incompatible = ""
        try:
            profile.check_camera(self.camera_index, self.width, self.height)
        except ZoneError as exc:
            self.incompatible = str(exc)
        self._baseline = self._fingerprint()
        self.drag = None
        self.mode = "edit"
        self.status = (f"PERFIL INCOMPATIBLE: {self.incompatible} R borra ambas zonas para recalibrar."
                       if self.incompatible else f"Perfil {profile.name} cargado para revisar. G activa; S guarda cambios.")

    def _new(self):
        self.polygons = {"A": [], "B": []}
        self.closed = {"A": False, "B": False}
        self.name, self.loaded, self.incompatible = "", None, ""
        self.drag = None
        self.mode = "edit"
        self._baseline = self._fingerprint()
        self.status = "Nuevo perfil sin guardar. Dibuje ambas zonas."

    def _confirm(self, action, payload, message):
        self.mode, self.pending = "confirm", (action, payload)
        self.status = message + " Y: confirmar / N o ESC: volver."

    def request_exit(self):
        if self.dirty:
            self._confirm("exit", None, "Hay cambios sin guardar. ¿Descartarlos y salir?")
        else:
            self.exit_requested = True

    def profile(self, name):
        if self.incompatible:
            raise ZoneError("Perfil incompatible. R inicia la recalibración; no se puede activar ni guardar sin redibujar.")
        if not all(self.closed.values()):
            raise ZoneError("Cierre cada polígono con Enter o clic derecho antes de guardar.")
        return ZoneProfile.create(name, self.camera_index, self.width, self.height,
                                  self.polygons["A"], self.polygons["B"])

    def _save(self, profile, overwrite=False):
        self.store.save_and_activate(profile, overwrite=overwrite)
        self._load(profile)
        self.active_name = profile.name
        self.status = f"GUARDADO Y ACTIVO: {profile.name}. Puede cerrar o seguir editando."

    def _perform(self, action, payload):
        self.mode, self.pending = "edit", None
        if action == "exit": self.exit_requested = True
        elif action == "new": self._new()
        elif action == "load": self._load(payload)
        elif action == "save": self._save(payload, overwrite=True)

    def key(self, key):
        try:
            self._key(key)
        except (ZoneError, OSError) as exc:
            self.status = str(exc)
            if self.mode == "confirm": self.mode, self.pending = "edit", None

    def _key(self, key):
        if self.mode == "confirm":
            if key in (ord("y"), ord("Y")):
                self._perform(*self.pending)
            elif key in (27, ord("n"), ord("N")):
                self.mode, self.pending, self.status = "edit", None, "Operación cancelada; cambios de edición conservados."
            return
        if self.mode == "name":
            if key == 27:
                self.mode, self.status = "edit", "Guardado cancelado; archivos intactos."
            elif key in (8, 127): self.name_input = self.name_input[:-1]
            elif key in (10, 13):
                name = validate_name(self.name_input)
                profile = self.profile(name)
                if name in self.store.names():
                    self._confirm("save", profile, f"Sobrescribir y activar el perfil {name}?")
                else:
                    self._save(profile)
            elif 32 <= key <= 126 and len(self.name_input) < 48:
                self.name_input += chr(key)
            return
        if self.mode == "profiles":
            if key == 27: self.mode = "edit"
            elif key in (ord("j"), ord("]")): self.profile_index = (self.profile_index + 1) % len(self.profiles)
            elif key in (ord("k"), ord("[")): self.profile_index = (self.profile_index - 1) % len(self.profiles)
            elif key in (10, 13):
                profile = self.store.load(self.profiles[self.profile_index])
                if self.dirty:
                    self._confirm("load", profile, "Descartar cambios y cargar el perfil seleccionado?")
                else: self._load(profile)
            return
        if key in (27, ord("q"), ord("Q")):
            self.request_exit()
        elif key in (ord("a"), ord("A"), ord("b"), ord("B")):
            self.selected = chr(key).upper(); self.drag = None
        elif key == 32:
            self.frozen = not self.frozen
        elif key in (ord("u"), ord("U"), 8, 127):
            if self.polygons[self.selected]:
                self.polygons[self.selected].pop(); self.closed[self.selected] = False
        elif key in (ord("r"), ord("R")):
            if self.incompatible:
                self.polygons = {"A": [], "B": []}; self.closed = {"A": False, "B": False}
                self.incompatible = ""
                self.status = "Recalibrando para la cámara actual. Dibuje A y B antes de guardar."
            else:
                self.polygons[self.selected] = []; self.closed[self.selected] = False
                self.status = f"Zona {self.selected} borrada solo en el editor."
            self.drag = None
        elif key in (10, 13):
            validate_polygon(self.polygons[self.selected])
            self.closed[self.selected] = True
            self.status = f"Zona {self.selected} cerrada. Al guardar se valida también la separación A/B."
        elif key in (ord("s"), ord("S")):
            self.profile(self.name or "validacion")  # Valida sin crear ningún perfil.
            self.name_input, self.mode = self.name, "name"
            self.status = "Escriba el nombre; Enter guarda y activa. ESC cancela."
        elif key in (ord("p"), ord("P")):
            self.profiles = self.store.names()
            if not self.profiles: raise ZoneError("No hay perfiles guardados. Dibuje A/B y use S.")
            self.profile_index, self.mode = 0, "profiles"
            self.status = "J/K o [/] seleccionan; Enter carga para revisar; G activa desde la vista."
        elif key in (ord("g"), ord("G")):
            if self.dirty or self.loaded is None:
                raise ZoneError("Guarde los cambios con S antes de activar este perfil.")
            if self.incompatible: raise ZoneError(self.incompatible)
            current = self.store.load(self.name)
            if current != self.loaded: raise ZoneError("El perfil cambió en disco; vuelva a cargarlo con P.")
            current.check_camera(self.camera_index, self.width, self.height)
            self.store.activate(self.name, expected=self.loaded)
            self.active_name = self.name
            self.status = f"PERFIL ACTIVO: {self.name}."
        elif key in (ord("n"), ord("N")):
            if self.dirty: self._confirm("new", None, "Descartar cambios y comenzar un perfil nuevo?")
            else: self._new()

    def mouse(self, action, x, y, width, height):
        if self.mode != "edit" or self.incompatible:
            return
        if action == "up":
            self.drag = None; return
        point = normalized_point(x, y, width, height)
        if point is None: return
        points = self.polygons[self.selected]
        if action == "right":
            self.key(13)
        elif action == "down":
            nearest = min(range(len(points)), key=lambda i: math.hypot(points[i][0] * width - x, points[i][1] * height - y), default=None)
            if nearest is not None and math.hypot(points[nearest][0] * width - x, points[nearest][1] * height - y) <= 10:
                self.drag = nearest
            elif not self.closed[self.selected] and len(points) < MAX_POINTS:
                points.append(point)
            else:
                self.status = "Arrastre un vértice para editar; R borra la zona; U quita el último punto."
        elif action == "move" and self.drag is not None:
            points[self.drag] = point
            self.status = "Vértice movido. Enter valida el polígono; S valida y guarda ambas zonas."


def _ascii(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def preview_size(frame):
    height, width = frame.shape[:2]
    factor = min(960 / width, 480 / height, 1.)
    return max(2, round(width * factor)), max(2, round(height * factor))


def render_editor(cv2, source, editor):
    import numpy as np
    width, height = preview_size(source)
    preview = cv2.resize(source, (width, height))
    draw_regions(cv2, preview, editor.polygons, editor.closed)
    for name, points in editor.polygons.items():
        for i, (x, y) in enumerate(points):
            p = (round(x * width), round(y * height))
            cv2.circle(preview, p, 5 if name == editor.selected else 3, COLORS[name], -1)
            cv2.putText(preview, str(i + 1), (p[0] + 6, p[1] + 3), cv2.FONT_HERSHEY_SIMPLEX, .4, COLORS[name], 1)
    canvas = np.zeros((height + 220, max(960, width), 3), dtype=np.uint8)
    canvas[:height, :width] = preview
    rows = [f"Editando ZONA {editor.selected} | Puntos {len(editor.polygons[editor.selected])}/{MAX_POINTS} | "
            f"Perfil: {editor.name or '(nuevo)'} | Activo: {editor.active_name}",
            f"{'CONGELADO' if editor.frozen else 'EN VIVO'} | {'CAMBIOS SIN GUARDAR' if editor.dirty else 'Sin cambios pendientes'}",
            "A/B: elegir zona | Clic izq: agregar / arrastrar vertice | Clic der o Enter: cerrar",
            "U/Retroceso: quitar ultimo punto | R: redibujar zona | Espacio: congelar/reanudar",
            "S: guardar y activar | P: perfiles | G: activar perfil revisado | N: nuevo | Q/ESC: salir"]
    if editor.mode == "name": rows.append("Nombre: " + editor.name_input + "_")
    elif editor.mode == "profiles":
        start = max(0, editor.profile_index - 1)
        rows.extend(("> " if i == editor.profile_index else "  ") + editor.profiles[i]
                    for i in range(start, min(start + 3, len(editor.profiles))))
    rows.extend(textwrap.wrap(_ascii(editor.status), 110)[:3])
    for i, text in enumerate(rows[:11]):
        cv2.putText(canvas, _ascii(text), (10, height + 18 + 19 * i), cv2.FONT_HERSHEY_SIMPLEX, .48,
                    (80, 160, 255) if editor.mode == "confirm" or editor.incompatible else (235, 235, 235), 1, cv2.LINE_AA)
    return canvas


def run_calibrator(cv2, camera_config, store=None):
    from .camera import camera_session
    store = ZoneStore() if store is None else store
    editor = None
    try:
        with camera_session(camera_config) as (capture, frame):
            height, width = frame.shape[:2]
            editor = CalibrationEditor(store, camera_config["camera_index"], width, height)
            frozen = None
            display = preview_size(frame)

            def mouse(event, x, y, flags, parameter):
                actions = {cv2.EVENT_LBUTTONDOWN: "down", cv2.EVENT_LBUTTONUP: "up",
                           cv2.EVENT_MOUSEMOVE: "move", cv2.EVENT_RBUTTONDOWN: "right"}
                if event in actions: editor.mouse(actions[event], x, y, *display)

            def open_window():
                cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
                cv2.setMouseCallback(WINDOW, mouse)

            open_window()
            while not editor.exit_requested:
                try:
                    if editor.frozen and frozen is None: frozen = frame.copy()
                    if not editor.frozen: frozen = None
                    shown = frozen if frozen is not None else frame
                    display = preview_size(shown)
                    cv2.imshow(WINDOW, render_editor(cv2, shown, editor))
                    editor.key(cv2.waitKey(20) & 0xFF)
                    if editor.frozen and frozen is None: frozen = frame.copy()
                    if not editor.frozen: frozen = None
                    if editor.exit_requested: break
                    try:
                        visible = cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE)
                    except cv2.error:
                        visible = -1  # Algunos backends ya destruyeron la ventana al pulsar X.
                    if visible < 1:
                        editor.request_exit()
                        if not editor.exit_requested: open_window()
                    if editor.exit_requested: break
                    ok, frame = capture.read()
                    if not ok or frame is None or frame.size == 0:
                        raise RuntimeError("La cámara dejó de entregar frames. No se guardaron cambios pendientes.")
                    h, w = frame.shape[:2]
                    if not math.isclose(w / h, width / height, rel_tol=.005):
                        raise RuntimeError("La relación de aspecto cambió durante la calibración; vuelva a abrir el calibrador.")
                except KeyboardInterrupt:
                    editor.request_exit()
            frozen = None
    finally:
        try: cv2.destroyAllWindows()
        except cv2.error as exc: LOGGER.warning("No se pudieron cerrar las ventanas: %s", exc)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        import cv2
    except ImportError as exc:
        LOGGER.error("No se pudo cargar OpenCV del entorno existente: %s", exc)
        return 1
    try:
        camera_config = load_config()
        if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            raise RuntimeError("Ejecute el calibrador en un escritorio con webcam y OpenCV gráfico.")
        run_calibrator(cv2, camera_config)
    except KeyboardInterrupt:
        LOGGER.info("Calibración cancelada; no se guardan cambios pendientes.")
    except (ValueError, RuntimeError, OSError, cv2.error) as exc:
        LOGGER.error("%s", exc); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
