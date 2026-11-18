# -*- coding: utf-8 -*-
"""Lanzador operativo LimpIA - v0.5 mejorada (servicios sin consolas visibles).

Se instala en capstone-vision/LimpIA_Operativo/.
No modifica scripts de otro lanzador ni necesita instalar paquetes nuevos.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
import webbrowser

import tkinter as tk
from tkinter import messagebox, ttk, simpledialog

from gestion_procesos import (
    carpeta_logs, iniciar_oculto, terminar_proceso, esperar_emisor
)

VISION = Path(__file__).resolve().parent.parent
DJANGO = VISION.parent.parent / "HigieneSmart"
BASE_URL = "http://127.0.0.1:8000"
CAMERA_CFG = VISION / "config" / "camera.json"
COUNT_CFG = VISION / "config" / "counting.json"
DETECT_CFG = VISION / "config" / "detection.json"
ACTIVE_ZONES = VISION / "config" / "zones" / "active.json"
ZONES_DIR = ACTIVE_ZONES.parent
BACKUP_DIR = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "HigieneSmart" / "lanzador_operativo" / "respaldos"
OPERACION_RAIZ = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "HigieneSmart" / "operacion_v2"
OPERACION_COLA = OPERACION_RAIZ / "limpIAvision" / "eventos.sqlite3"
EMISOR = Path(__file__).resolve().parent / "emisor_operativo.py"
MODO_PRUEBA = "Pruebas (sin enviar)"
MODO_REAL = "Operacion real (PostgreSQL)"

TRACKERS = {"ByteTrack": "bytetrack", "BoT-SORT sin ReID": "botsort_no_reid"}
PAGES = {
    "Panel supervisor": "/supervisor/",
    "Panel trabajador": "/trabajador/",
    "Inicio de sesion": "/",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def vision_python() -> Path:
    explicit = os.environ.get("LIMPIA_PYTHON_VISION", "").strip()
    if explicit:
        return Path(explicit)
    current = VISION / ".venv" / "Scripts" / "python.exe"
    if current.is_file():
        return current
    # Entorno de vision ya utilizado en este equipo (worktree de integracion).
    other = (Path.home() / "Documents" / "GitHub" /
             "LimpIAvision-integracion-vision-django" /
             "Fase_2" / "Evidencias_Proyecto" / "Vision-Artificial" /
             "capstone-vision" / ".venv" / "Scripts" / "python.exe")
    return other


def django_python() -> Path:
    configured = os.environ.get("LIMPIA_PYTHON_DJANGO", "").strip()
    if configured:
        return Path(configured)
    return DJANGO / ".venv" / "Scripts" / "python.exe"


def orientation_for_active(active: dict) -> Path:
    calib = active["calibration"]
    digest = hashlib.sha256(
        json.dumps(calib, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    matches = []
    for path in (VISION / "config").glob("counting*.local.json"):
        try:
            data = read_json(path)
            if (data.get("profile_name") == active["active_profile"]
                    and data.get("profile_sha256") == digest
                    and data.get("confirmed") is True
                    and data.get("h4_a_role") in ("exterior", "puerta")):
                matches.append(path)
        except (OSError, ValueError):
            continue
    if not matches:
        raise ValueError(
            "No existe confirmacion de orientacion valida para las zonas activas. "
            "Hay que confirmar exterior/puerta nuevamente antes de contar."
        )
    return max(matches, key=lambda p: p.stat().st_mtime)


def preflight() -> tuple[Path, dict, dict, dict]:
    if not (VISION / "src" / "track_count.py").is_file():
        raise FileNotFoundError("Instale el lanzador en capstone-vision, al lado de src/.")
    vp, dp = vision_python(), django_python()
    if not vp.is_file():
        raise FileNotFoundError(f"No se encontro Python de vision: {vp}")
    if not dp.is_file():
        raise FileNotFoundError(f"No se encontro Python de Django: {dp}")
    if not (DJANGO / "manage.py").is_file():
        raise FileNotFoundError("Falta manage.py de HigieneSmart.")

    camera = read_json(CAMERA_CFG)
    active = read_json(ACTIVE_ZONES)
    detection = read_json(DETECT_CFG)
    counting = read_json(COUNT_CFG)

    calib = active["calibration"]
    if camera["camera_index"] != calib["camera_index"]:
        raise ValueError(
            f"La camara configurada es {camera['camera_index']}, pero las zonas "
            f"son para la camara {calib['camera_index']}. Ajuste/active zonas para esta camara."
        )
    if calib["reference_size"] != [camera["width"], camera["height"]]:
        raise ValueError("La resolucion de las zonas no coincide con camera.json.")

    model = Path(detection["model"])
    if not model.is_absolute():
        model = VISION / model
    if not model.is_file():
        raise FileNotFoundError(f"Falta el modelo local: {model}")

    if not (VISION / "config" / "botsort_no_reid_capstone.yaml").is_file():
        raise FileNotFoundError("Falta la configuracion de BoT-SORT sin ReID.")
    yaml = (VISION / "config" / "botsort_no_reid_capstone.yaml").read_text(encoding="utf-8-sig")
    if not re.search(r"(?m)^\s*with_reid:\s*false\s*$", yaml):
        raise ValueError("No se comprobo que BoT-SORT tenga ReID desactivado.")
    orientation = orientation_for_active(active)
    if "tracker" not in counting or "thresholds" not in counting:
        raise ValueError("counting.json incompleto.")
    if "device" not in detection:
        raise ValueError("detection.json incompleto.")
    return orientation, camera, counting, detection


def set_json_field(path: Path, key: str, value: str) -> bool:
    data = read_json(path)
    if data[key] == value:
        return False
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    shutil.copy2(path, BACKUP_DIR / f"{stamp}_{path.name}")
    updated = dict(data)
    updated[key] = value
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if read_json(temporary)[key] != value:
            raise RuntimeError("Configuracion temporal no verificada.")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def django_listening() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=0.6):
            return True
    except OSError:
        return False


def django_is_ours() -> bool:
    """Comprueba que el servicio expone la API de conteo esperada."""
    try:
        # Vista POST-only: una petición GET debe producir 405 con Allow: POST.
        with urlopen(BASE_URL + "/api/v1/eventos-conteo/", timeout=2.0):
            return False
    except HTTPError as exc:
        return exc.code == 405 and "POST" in exc.headers.get("Allow", "").upper()
    except (URLError, OSError):
        return False


class Launcher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("LimpIAvision - Lanzador operativo v0.5 mejorada")
        self.root.geometry("740x585")
        self.root.minsize(710, 545)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.camera_proc: subprocess.Popen | None = None
        self.django_proc: subprocess.Popen | None = None
        self.sender_proc: subprocess.Popen | None = None
        self.running_mode: str | None = None
        self.sender_stop_file: Path | None = None
        self.registros: dict[str, Path] = {}
        self.tool_proc: subprocess.Popen | None = None
        self.tool_kind = ""
        self.busy = False

        frame = ttk.Frame(self.root, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="LimpIAvision | Lanzador operativo", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text="v0.5 mejorada - Sin terminales extra | Pruebas / Operacion real").pack(anchor="w", pady=(0, 12))

        fields = ttk.Frame(frame)
        fields.pack(fill="x")
        fields.columnconfigure(1, weight=1)
        self.camera_label = tk.StringVar(value="Leyendo configuracion...")
        self.zones_label = tk.StringVar(value="")
        self.active_zones_label = tk.StringVar(value="...")
        self.orientation_label = tk.StringVar(value="Orientacion: ...")
        self.tracker = tk.StringVar(value="ByteTrack")
        self.device = tk.StringVar(value="cpu")
        self.page = tk.StringVar(value="Panel supervisor")
        self.mode = tk.StringVar(value=MODO_PRUEBA)

        ttk.Label(fields, text="Camara:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Label(fields, textvariable=self.camera_label).grid(row=0, column=1, sticky="w")
        ttk.Button(fields, text="Cambiar camara", command=self.camera_selector).grid(row=0, column=2, padx=6)
        ttk.Label(fields, text="Perfil de zonas:").grid(row=1, column=0, sticky="w", pady=4)
        self.zone_combo = ttk.Combobox(fields, textvariable=self.zones_label, values=[], state="readonly", width=26)
        self.zone_combo.grid(row=1, column=1, sticky="w")
        self.zone_combo.bind("<<ComboboxSelected>>", self._on_zone_selected)
        ttk.Button(fields, text="Activar perfil", command=self.activate_selected).grid(row=1, column=2, padx=6)
        ttk.Label(fields, textvariable=self.active_zones_label).grid(row=2, column=1, sticky="w")
        ttk.Label(fields, textvariable=self.orientation_label).grid(row=3, column=1, sticky="w")

        zone_buttons = ttk.Frame(fields)
        zone_buttons.grid(row=4, column=1, columnspan=2, sticky="w", pady=(3, 8))
        ttk.Button(zone_buttons, text="Editar seleccionado", command=self.calibrator).pack(side="left", padx=(0, 6))
        ttk.Button(zone_buttons, text="Crear zonas", command=self.new_calibration).pack(side="left", padx=(0, 6))
        ttk.Button(zone_buttons, text="Confirmar A/B", command=self.confirm_orientation).pack(side="left")

        ttk.Label(fields, text="Tracker:").grid(row=5, column=0, sticky="w", pady=4)
        ttk.Combobox(fields, textvariable=self.tracker, values=list(TRACKERS), state="readonly", width=26).grid(row=5, column=1, sticky="w")
        ttk.Label(fields, text="Dispositivo:").grid(row=6, column=0, sticky="w", pady=4)
        ttk.Combobox(fields, textvariable=self.device, values=["cpu", "cuda:0"], state="readonly", width=26).grid(row=6, column=1, sticky="w")
        ttk.Label(fields, text="Abrir web:").grid(row=7, column=0, sticky="w", pady=4)
        ttk.Combobox(fields, textvariable=self.page, values=list(PAGES), state="readonly", width=26).grid(row=7, column=1, sticky="w")
        ttk.Label(fields, text="Modo:").grid(row=8, column=0, sticky="w", pady=4)
        ttk.Combobox(fields, textvariable=self.mode, values=[MODO_PRUEBA, MODO_REAL],
                     state="readonly", width=31).grid(row=8, column=1, sticky="w")

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(18, 5))
        self.start_btn = ttk.Button(buttons, text="INICIAR SISTEMA", command=self.start)
        self.start_btn.pack(side="left", padx=(0, 7))
        ttk.Button(buttons, text="Abrir web", command=self.open_web).pack(side="left", padx=5)
        ttk.Button(buttons, text="Detener", command=self.stop).pack(side="left", padx=5)
        ttk.Button(buttons, text="Actualizar", command=self.refresh).pack(side="left", padx=5)
        ttk.Button(buttons, text="Ver registros", command=self.open_logs).pack(side="left", padx=5)
        self.status = tk.StringVar(value="Listo. Modo de prueba: NO se envian eventos a Django.")
        ttk.Separator(frame).pack(fill="x", pady=(12, 9))
        ttk.Label(frame, textvariable=self.status, wraplength=670, justify="left").pack(anchor="w")
        ttk.Label(frame, text="La vista conserva zonas, IDs, IN/OUT y FPS del contador original.\nPara cerrar la camara normalmente, pulsa Q en su ventana.",
                  foreground="#555555", justify="left").pack(anchor="w", pady=(12, 0))
        self.refresh()
        self.root.after(1200, self.check_processes)

    def notify(self, text: str):
        self.status.set(text)

    def open_logs(self):
        try:
            destino = carpeta_logs()
            destino.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(destino))
            else:
                messagebox.showinfo("Registros", str(destino))
        except OSError as exc:
            messagebox.showerror("Registros", str(exc))

    def refresh(self):
        try:
            c = read_json(CAMERA_CFG)
            a = read_json(ACTIVE_ZONES)
            d = read_json(DETECT_CFG)
            t = read_json(COUNT_CFG)
            self.camera_label.set(f"{c['camera_index']} | {c['width']}x{c['height']}")
            self.refresh_profiles(sync_active=True)
            self.tracker.set(next((k for k, v in TRACKERS.items() if v == t["tracker"]), "ByteTrack"))
            self.device.set(d["device"] if d["device"] in ("cpu", "cuda:0") else "cpu")
            self.notify("Configuracion leida. Modo predeterminado: PRUEBAS (sin envio).")
        except Exception as exc:
            self.notify(f"Configuracion incompleta: {exc}")

    def _zone_store(self):
        # Reutiliza el almacén oficial: valida cada perfil, su geometría y su nombre.
        if str(VISION) not in sys.path:
            sys.path.insert(0, str(VISION))
        from src.zones import ZoneStore
        return ZoneStore()

    def _on_zone_selected(self, _event=None):
        self.show_zone_state()

    def refresh_profiles(self, *, sync_active=False):
        store = self._zone_store()
        names = store.names()
        active = store.load_active().name
        self.zone_combo.configure(values=names)
        if sync_active or self.zones_label.get() not in names:
            self.zones_label.set(active)
        self.active_zones_label.set(f"Activo para el conteo: {active}")
        self.show_zone_state()

    def show_zone_state(self):
        name = self.zones_label.get()
        try:
            store = self._zone_store()
            profile = store.load(name)
            camera = read_json(CAMERA_CFG)
            compatible = (profile.camera_index == camera["camera_index"]
                          and [profile.width, profile.height] == [camera["width"], camera["height"]])
            from src.count_orientation import load_orientation
            # Una orientación antigua nunca sirve si cambió algún polígono.
            has_orientation = False
            for file in (VISION / "config").glob("counting*.local.json"):
                try:
                    load_orientation(file, profile)
                    has_orientation = True
                    break
                except (OSError, ValueError):
                    continue
            self.orientation_label.set(
                ("Orientacion A/B: confirmada" if has_orientation else "Orientacion A/B: pendiente")
                + ("" if compatible else " | Perfil no compatible con camara/resolucion")
            )
        except (OSError, ValueError, KeyError) as exc:
            self.orientation_label.set("No se pudo validar el perfil: " + str(exc))

    def _can_change_zones(self):
        if self.busy or any(proc is not None and proc.poll() is None
                            for proc in (self.camera_proc, self.sender_proc)):
            messagebox.showwarning(
                "Sesion activa",
                "Deten el sistema (incluido el emisor) antes de cambiar los perfiles.")
            return False
        if self.tool_proc and self.tool_proc.poll() is None:
            messagebox.showwarning("Herramienta abierta", "Termina el editor/selector antes de cambiar los perfiles.")
            return False
        return True

    def _activate(self, name, *, ask=True):
        store = self._zone_store()
        profile = store.load(name)
        camera = read_json(CAMERA_CFG)
        profile.check_camera(camera["camera_index"], camera["width"], camera["height"])
        if (profile.width, profile.height) != (camera["width"], camera["height"]):
            raise ValueError("El perfil no corresponde a la resolucion configurada. Recalibra antes de activarlo.")
        active = store.load_active().name
        if name == active:
            return True
        if ask and not messagebox.askyesno(
            "Activar perfil de zonas",
            f"Se activara el perfil '{name}' para la camara {camera['camera_index']}.\n\n"
            "Verifica fisicamente que las zonas correspondan a este encuadre. "
            "Tener la misma resolucion NO demuestra que la camara siga apuntando al mismo lugar.\n\n"
            "¿Activar este perfil?"
        ):
            return False
        store.activate(name, expected=profile)
        self.refresh_profiles(sync_active=True)
        self.notify(f"Perfil '{name}' activado. Comprueba su orientacion antes de contar.")
        return True

    def activate_selected(self):
        if not self._can_change_zones():
            return
        try:
            self._activate(self.zones_label.get())
        except Exception as exc:
            messagebox.showerror("No se pudo activar el perfil", str(exc))

    def confirm_orientation(self):
        if not self._can_change_zones():
            return
        try:
            profile_name = self.zones_label.get()
            if not self._activate(profile_name):
                return
            profile = self._zone_store().load_active()
            role = tk.StringVar(value="")
            confirmed = tk.BooleanVar(value=False)
            modal = tk.Toplevel(self.root)
            modal.title("Confirmacion fisica de orientacion")
            modal.transient(self.root)
            modal.resizable(False, False)
            content = ttk.Frame(modal, padding=15)
            content.pack(fill="both", expand=True)
            ttk.Label(content, text=f"Perfil: {profile.name}", font=("Segoe UI", 11, "bold")).pack(anchor="w")
            ttk.Label(content, text="¿Qué representa la zona A en la imagen ACTUAL de la camara?").pack(anchor="w", pady=(10, 4))
            ttk.Radiobutton(content, text="A = exterior, B = puerta", variable=role, value="exterior").pack(anchor="w")
            ttk.Radiobutton(content, text="A = puerta, B = exterior", variable=role, value="puerta").pack(anchor="w")
            ttk.Checkbutton(content, text="Comprobe fisicamente la orientacion A/B de este encuadre.", variable=confirmed).pack(anchor="w", pady=(9, 5))
            ttk.Label(content, text="Nombre del responsable:").pack(anchor="w")
            reviewer = ttk.Entry(content, width=48)
            reviewer.pack(anchor="w", pady=5)
            result = {"saved": False}

            def save():
                if not role.get() or not confirmed.get() or not reviewer.get().strip():
                    messagebox.showwarning("Confirmacion incompleta", "Selecciona el rol de A, marca la verificacion fisica e indica un responsable.", parent=modal)
                    return
                try:
                    if self._zone_store().load_active() != profile:
                        raise RuntimeError("El perfil activo cambio durante la confirmacion. Vuelve a revisarlo.")
                    if str(VISION) not in sys.path:
                        sys.path.insert(0, str(VISION))
                    from src.count_orientation import confirm_orientation, load_orientation
                    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    output = VISION / "config" / f"counting.{profile.name}.{stamp}.local.json"
                    path = confirm_orientation(profile, role.get(), reviewer.get().strip(), output, confirmed=True)
                    load_orientation(path, profile)
                    result["saved"] = True
                    modal.destroy()
                except Exception as exc:
                    messagebox.showerror("No se pudo confirmar", str(exc), parent=modal)

            ttk.Button(content, text="Guardar confirmacion A/B", command=save).pack(anchor="e", pady=(10, 0))
            modal.protocol("WM_DELETE_WINDOW", modal.destroy)
            modal.grab_set()
            self.root.wait_window(modal)
            self.refresh_profiles(sync_active=True)
            if result["saved"]:
                self.notify(f"Orientacion confirmada para '{profile.name}'. Perfil listo para iniciar (si coincide el encuadre).")
        except Exception as exc:
            messagebox.showerror("Orientacion no confirmada", str(exc))

    def new_calibration(self):
        if not self._can_change_zones():
            return
        messagebox.showinfo("Crear otro perfil", "Se abrira el calibrador. Pulsa N para crear un perfil nuevo, dibuja A y B, cierra los poligonos y guarda con S y un NOMBRE NUEVO.\n\nNo sobrescribas el perfil anterior. Cuando cierres el editor, el nuevo aparecerá en la lista. Después confirma su orientacion A/B.")
        self.run_util("src.zone_calibrator", kind="calibrador")

    def run_util(self, module: str, *, kind="herramienta"):
        if not self._can_change_zones():
            return
        python = vision_python()
        if not python.is_file():
            messagebox.showerror("Python no encontrado", f"No existe: {python}")
            return
        try:
            self.tool_proc = subprocess.Popen([str(python), "-m", module], cwd=str(VISION),
                             creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
            self.tool_kind = kind
            self.notify("Abri el editor/selector. Al cerrarlo se actualizara la lista de perfiles.")
        except OSError as exc:
            messagebox.showerror("No se pudo abrir", str(exc))

    def camera_selector(self):
        self.run_util("src.camera_selector", kind="camara")

    def calibrator(self):
        if not self._can_change_zones():
            return
        selected = self.zones_label.get()
        try:
            if not self._activate(selected):
                return
            messagebox.showinfo("Editar perfil seleccionado",
                f"Se abrira '{selected}'. Ajusta vertices y pulsa S para guardar.\n\n"
                "Si quieres conservar el original y crear otro perfil, escribe un NOMBRE NUEVO al guardar.\n"
                "Si cambias los poligonos, debes CONFIRMAR A/B nuevamente.")
            self.run_util("src.zone_calibrator", kind="calibrador")
        except Exception as exc:
            messagebox.showerror("No se pudo editar", str(exc))

    def open_web(self):
        webbrowser.open(BASE_URL + PAGES[self.page.get()])

    def start(self):
        if self.busy or any(p is not None and p.poll() is None for p in
                            (self.camera_proc, self.sender_proc, self.django_proc)):
            self.notify("Hay procesos iniciados por este lanzador. Detenlos antes de iniciar otra sesion.")
            return
        token = None
        try:
            # Nunca activar zonas que solo fueron seleccionadas en el desplegable.
            if self.zones_label.get() != self._zone_store().load_active().name:
                raise ValueError("Elegiste otro perfil. Pulsa 'Activar perfil' antes de iniciar.")
            orientation, camera, counting, detection = preflight()
            selected_tracker = TRACKERS[self.tracker.get()]
            selected_device = self.device.get()
            mode = self.mode.get()
            if mode not in (MODO_PRUEBA, MODO_REAL):
                raise ValueError("Modo no reconocido.")
            if selected_device not in ("cpu", "cuda:0"):
                raise ValueError("Dispositivo invalido.")

            if mode == MODO_REAL:
                if not OPERACION_COLA.is_file():
                    raise FileNotFoundError(
                        "No existe operacion_v2; no se crea una cola nueva automaticamente.\n"
                        + str(OPERACION_COLA))
                if not EMISOR.is_file():
                    raise FileNotFoundError("Falta emisor_operativo.py")
                # El sistema no puede reconocer en la imagen si la camara
                # apunta al bano verdadero o a una habitacion de prueba.
                if not messagebox.askyesno(
                    "Operacion REAL - verificar ubicacion",
                    "Comprueba fisicamente que la camara apunta a la entrada REAL "
                    "del Bano hombres 1 y que el perfil '" +
                    self.zones_label.get() + "' corresponde a ese encuadre.\n\n"
                    "ATENCION: cada movimiento se enviara a capstone_db y "
                    "podra generar una alerta real.\n\n"
                    "Deten cualquier emisor antiguo conectado a operacion_v2.\n\n"
                    "¿Autorizar esta sesion REAL?"
                ):
                    return
                token = simpledialog.askstring(
                    "Token privado", "Token Bearer de droidcam-demo:",
                    show="*", parent=self.root)
                if token is None:
                    return
                if not token or token != token.strip():
                    raise ValueError("Token vacio o con espacios. Operacion cancelada.")
            elif selected_tracker == "botsort_no_reid":
                if not messagebox.askyesno(
                    "BoT-SORT sin ReID",
                    "Se probó con DroidCam. ¿Continuar con BoT-SORT sin ReID en modo pruebas?"):
                    return

            # El perfil ya debe estar activo y su confirmacion corresponder
            # exactamente a esta geometria. No se modifica esa orientacion.
            set_json_field(COUNT_CFG, "tracker", selected_tracker)
            set_json_field(DETECT_CFG, "device", selected_device)
        except Exception as exc:
            messagebox.showerror("Configuracion no lista", str(exc))
            return

        self.busy = True
        self.start_btn.configure(state="disabled")
        self.notify("Iniciando procesos: " + mode)
        threading.Thread(target=self._start_worker,
                         args=(orientation, mode, token), daemon=True).start()

    def _start_worker(self, orientation: Path, mode: str, token: str | None):
        """Django/emisor sin consola visible; OpenCV mantiene su ventana grafica."""
        try:
            env_sender = None
            if mode == MODO_REAL:
                # La comprobacion no envia nada y no modifica SQLite o PostgreSQL.
                # La credencial se entrega por stdin, nunca como parametro/env/log.
                env_sender = os.environ.copy()
                env_sender["DB_NAME"] = "capstone_db"
                env_sender["PYTHONPATH"] = str(DJANGO)
                check = subprocess.run(
                    [str(django_python()), "-B", str(EMISOR), "--comprobar",
                     "--cola", str(OPERACION_COLA), "--vision", str(VISION)],
                    input=token + "\n", capture_output=True, text=True,
                    cwd=str(DJANGO), env=env_sender, timeout=25,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if check.returncode != 0:
                    raise RuntimeError(
                        "Revision operativa fallida: " +
                        (check.stderr or check.stdout).strip()[-800:])

            if django_listening():
                if not django_is_ours():
                    raise RuntimeError(
                        "Puerto 8000 ocupado por un servicio que no presenta la API de conteo.")
                server_msg = "HigieneSmart ya estaba activo; no se cerrara al detener."
            else:
                env = os.environ.copy()
                env.update(DB_NAME="capstone_db", CONTEO_IN_OUT_HABILITADO="1",
                           CONTEO_DASHBOARD_FUENTE="droidcam-demo")
                self.django_proc, self.registros["django"] = iniciar_oculto(
                    [str(django_python()), "manage.py", "runserver",
                     "127.0.0.1:8000", "--noreload"],
                    cwd=DJANGO, env=env, etiqueta="django")
                ready = False
                for _ in range(30):
                    if self.django_proc.poll() is not None:
                        break
                    if django_listening() and django_is_ours():
                        ready = True
                        break
                    time.sleep(0.5)
                if not ready:
                    raise RuntimeError(
                        "Django no se inicio. Revisa 'Ver registros' en el lanzador.")
                server_msg = "Django iniciado sin terminal visible."

            if mode == MODO_REAL:
                self.sender_stop_file = (carpeta_logs() / "control" /
                                         f"emisor_{uuid.uuid4().hex}.stop")
                self.sender_proc, self.registros["emisor"] = iniciar_oculto(
                    [str(django_python()), "-B", str(EMISOR),
                     "--cola", str(OPERACION_COLA), "--vision", str(VISION),
                     "--stop-file", str(self.sender_stop_file)],
                    cwd=DJANGO, env=env_sender, etiqueta="emisor", con_stdin=True)
                if self.sender_proc.stdin is None:
                    raise RuntimeError("No se pudo entregar la credencial al emisor.")
                try:
                    self.sender_proc.stdin.write((token + "\n").encode("utf-8"))
                    self.sender_proc.stdin.close()
                finally:
                    token = None
                time.sleep(1.0)
                if self.sender_proc.poll() is not None:
                    raise RuntimeError(
                        "El emisor termino durante el arranque. Revisa 'Ver registros'.")

            env_cam = os.environ.copy()
            env_cam["LIMPIA_FUENTE_CONTEO"] = "droidcam-demo"
            if mode == MODO_REAL:
                env_cam["LIMPIA_GUARDAR_CONTEOS"] = "1"
                env_cam["LOCALAPPDATA"] = str(OPERACION_RAIZ)
            else:
                env_cam["LIMPIA_GUARDAR_CONTEOS"] = "0"

            self.camera_proc, self.registros["camara"] = iniciar_oculto(
                [str(vision_python()), "-m", "src.track_count",
                 "--orientation", str(orientation)],
                cwd=VISION, env=env_cam, etiqueta="camara")
            time.sleep(0.7)
            if self.camera_proc.poll() is not None:
                raise RuntimeError(
                    "La camara termino al iniciar. Revisa 'Ver registros'.")
            self.running_mode = mode
            self.ui(self.open_web)
            notice = (" MODO REAL: SQLite + envio a Django ACTIVADOS."
                      if mode == MODO_REAL else
                      " PRUEBAS: SIN guardar ni enviar eventos.")
            self.ui(lambda: self.notify(server_msg + " Camara abierta." + notice))
        except Exception as exc:
            # En caso de fallo no dejar servicios sin vigilancia.
            self._parar_procesos()
            msg = str(exc)
            self.ui(lambda: messagebox.showerror("No se pudo iniciar", msg))
            self.ui(lambda: self.notify("Error de inicio: " + msg))
        finally:
            token = None
            self.ui(self._startup_done)

    def ui(self, fn):
        try:
            self.root.after(0, fn)
        except (RuntimeError, tk.TclError):
            pass

    def _startup_done(self):
        self.busy = False
        self.start_btn.configure(state="normal")

    def _hay_procesos(self) -> bool:
        return any(proc is not None and proc.poll() is None for proc in
                   (self.camera_proc, self.sender_proc, self.django_proc))

    def _parar_procesos(self):
        """Primero vision, luego vaciar cola/emisor y al final Django propio."""
        terminar_proceso(self.camera_proc, espera=3)
        esperar_emisor(self.sender_proc, self.sender_stop_file, espera=15)
        terminar_proceso(self.django_proc, espera=3)
        if self.sender_stop_file is not None:
            try:
                self.sender_stop_file.unlink(missing_ok=True)
            except OSError:
                pass
        self.sender_stop_file = None
        self.camera_proc = None
        self.sender_proc = None
        self.django_proc = None
        self.running_mode = None

    def _parar_async(self, mensaje: str, *, salir: bool = False):
        if self.busy:
            return
        self.busy = True
        self.start_btn.configure(state="disabled")
        self.notify("Deteniendo procesos propios y conservando la cola SQLite...")
        def worker():
            self._parar_procesos()
            def finalizar():
                self.busy = False
                self.start_btn.configure(state="normal")
                self.notify(mensaje)
                if salir:
                    self.root.destroy()
            self.ui(finalizar)
        threading.Thread(target=worker, daemon=True).start()

    def stop(self):
        if self.busy:
            messagebox.showwarning("Ocupado", "Espera a terminar el inicio o detencion.")
            return
        if not self._hay_procesos():
            self.notify("No hay procesos en ejecucion iniciados por este lanzador.")
            return
        if not messagebox.askyesno(
            "Detener sistema",
            "Se detendran la camara, el emisor y Django SOLO si los inicio este lanzador.\n"
            "Un Django que ya estuviera abierto seguira funcionando.\n\n"
            "Los eventos pendientes permanecen en SQLite. ¿Continuar?"):
            return
        self._parar_async("Sistema detenido. Registros locales conservados.")

    def check_processes(self):
        if self.tool_proc is not None and self.tool_proc.poll() is not None:
            kind = self.tool_kind
            self.tool_proc, self.tool_kind = None, ""
            try:
                self.refresh()
                if kind == "calibrador":
                    if "pendiente" in self.orientation_label.get():
                        self.notify("Perfil guardado. Confirma A/B antes de contar.")
                    else:
                        self.notify("Perfiles actualizados. Revisa la seleccion antes de iniciar.")
            except Exception as exc:
                self.notify("No se pudieron actualizar los perfiles: " + str(exc))

        if not self.busy and self.running_mode is not None:
            # No dejar emisor Django abierto al cerrar la ventana de camara con Q.
            if self.camera_proc is None or self.camera_proc.poll() is not None:
                code = self.camera_proc.returncode if self.camera_proc else "?"
                self._parar_async(
                    f"Camara finalizada (codigo {code}). Emisor y Django propios detenidos.")
            elif self.sender_proc is not None and self.sender_proc.poll() is not None:
                code = self.sender_proc.returncode
                self._parar_async(
                    f"ATENCION: emisor termino (codigo {code}); se detuvo la camara. "
                    "Revisa SQLite y 'Ver registros'.")
            elif self.django_proc is not None and self.django_proc.poll() is not None:
                self._parar_async(
                    "ATENCION: Django se detuvo; tambien se cerro la camara y el emisor.")
        try:
            self.root.after(1200, self.check_processes)
        except tk.TclError:
            pass

    def close(self):
        if self.busy:
            messagebox.showwarning("Ocupado", "Espera a que terminen los procesos.")
            return
        if self.tool_proc is not None and self.tool_proc.poll() is None:
            messagebox.showwarning("Editor abierto", "Cierra primero el editor o selector de camara.")
            return
        if self._hay_procesos():
            if not messagebox.askyesno(
                "Salir de limpIAvision",
                "Hay procesos activos. ¿Detenerlos y cerrar el lanzador?\n"
                "No se cerraran programas que estaban abiertos previamente."):
                return
            self._parar_async("Todos los procesos propios detenidos.", salir=True)
            return
        self.root.destroy()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--listar-perfiles":
        if str(VISION) not in sys.path:
            sys.path.insert(0, str(VISION))
        from src.zones import ZoneStore
        store = ZoneStore()
        active = store.load_active().name
        names = store.names()
        print("=== PERFILES GUARDADOS (SOLO LECTURA) ===")
        for name in names:
            profile = store.load(name)
            print(f"- {name} | camara {profile.camera_index} | {profile.width}x{profile.height}" +
                  (" | ACTIVO" if name == active else ""))
        print("Total:", len(names))
        print("Sin cambios en PostgreSQL ni en los perfiles.")
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == "--verificar":
        ori, camera, counting, detection = preflight()
        print("LANZADOR OPERATIVO V0.5 MEJORADA - REVISION SEGURA")
        print("Camara:", camera["camera_index"])
        print("Tracker actual:", counting["tracker"])
        print("Dispositivo:", detection["device"])
        print("Orientacion:", ori.name)
        print("Modo por defecto: PRUEBAS (sin envio)")
        print("Cola operativa (solo se utiliza con autorizacion):", OPERACION_COLA)
        print("Envios HTTP: DESACTIVADOS EN ESTA VERIFICACION")
        print("Django y emisor: sin terminales extra en el inicio grafico")
        print("REVISION OK")
        return 0
    Launcher().root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
