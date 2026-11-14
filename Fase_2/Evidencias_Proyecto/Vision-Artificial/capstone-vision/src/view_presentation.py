"""LimpIA: one presentation window for MP4, saved tracking and live cameras."""
import argparse
import logging
from pathlib import Path
import platform
import time
from collections import deque
from dataclasses import replace
import tkinter as tk
from tkinter import filedialog, ttk

from .config import PROJECT_ROOT
from .presentation_session import Session
from .presentation_playback import WindowsTimer

BG = '#0c1420'
PANEL = '#142130'
TEXT = '#eef4fa'
MUTED = '#9eafbf'
IN = '#70d5b0'
OUT = '#ecba83'


def fit_size(width, height, available_width, available_height):
    scale = min(max(1, available_width) / width, max(1, available_height) / height)
    return max(1, round(width * scale)), max(1, round(height * scale))


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', choices=('video', 'camera'), default='video')
    p.add_argument('--video', type=Path, help='MP4 local; se puede elegir en la ventana.')
    p.add_argument('--zones', type=Path, default=PROJECT_ROOT / 'config/baselines/sala_v4.json')
    p.add_argument('--tracker', choices=('bytetrack', 'botsort'), default='bytetrack')
    p.add_argument('--device', help='cpu o cuda:N; si se omite, selector existente sin guardar preferencias.')
    p.add_argument('--weights-dir', type=Path, default=PROJECT_ROOT)
    p.add_argument('--camera-index', type=int)
    p.add_argument('--tracking-only', action='store_true', help='Camera sin calibrar: deteccion y tracking reales, conteo deshabilitado.')
    p.add_argument('--camera-backend', choices=('auto', 'msmf', 'dshow', 'v4l2', 'avfoundation'),
                   default='msmf' if platform.system() == 'Windows' else 'auto')
    p.add_argument('--confirm-camera-zones', action='store_true',
                   help='Confirma mismo encuadre y orientación A exterior / B puerta del perfil.')
    p.add_argument('--predictions', type=Path, help='Tracking completo ya procesado y vinculado al MP4.')
    p.set_defaults(realtime=True)
    p.add_argument('--log-file', type=Path, help='Archivo técnico NUEVO; no contiene imágenes.')
    return p


def resolve_choices(options):
    if options.tracking_only and options.source != 'camera':
        raise ValueError('--tracking-only requiere --source camera.')
    if options.predictions and options.source != 'video':
        raise ValueError('--predictions solo se permite con --source video.')
    if options.camera_index is not None and options.camera_index < 0:
        raise ValueError('El índice de cámara debe ser no negativo.')
    if options.source == 'camera':
        if options.video:
            raise ValueError('--video no corresponde a una fuente cámara.')
        if options.camera_index is None:
            from .camera_selector import scan_cameras, choose_camera
            from .config import load_config
            available = scan_cameras({**load_config(), 'backend': options.camera_backend})
            for camera in available:
                print(f'[{camera.index}] {camera.width}×{camera.height} | {camera.backend}')
            options.camera_index = choose_camera(available)
            if options.camera_index is None:
                raise ValueError('Selección de cámara cancelada.')
    if not options.predictions and options.device is None:
        from .device_selector import choose_device
        from .devices import discover_devices, load_torch
        inventory = discover_devices(load_torch())
        for i, device in enumerate(inventory.devices):
            print(f'[{i}] {device.device} | {device.name}')
        options.device = choose_device(inventory.devices)
        if options.device is None:
            raise ValueError('Selección de dispositivo cancelada.')
    return options


class PresentationWindow:
    def __init__(self, root, options):
        self.root, self.options = root, options
        self.session = Session(options, display_buffer=True)
        self.display_state = self.session.snapshot()
        self.shown_times = deque(maxlen=60)
        self.visual_fps = 0.
        self.timer = WindowsTimer()
        root.bind('<Destroy>', lambda event: self.timer.close() if event.widget is root else None, add='+')
        self.closing = False
        self.photo = None
        self.draw_key = None
        self._ui_signature = None
        self.render_count = 0
        root.title('LimpIA · Monitoreo de personas')
        root.geometry('1280x780')
        root.minsize(1000, 700)
        root.configure(bg=BG)
        root.rowconfigure(1, weight=1)
        root.columnconfigure(0, weight=1)
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('TButton', font=('Segoe UI', 11), padding=(12, 9),
                        background='#24384b', foreground=TEXT, borderwidth=0)
        style.map('TButton', background=[('active', '#355269')])
        video_area = tk.Frame(root, bg=BG)
        video_area.grid(row=1, column=0, sticky='nsew', padx=12, pady=(12, 8))
        self.canvas = tk.Canvas(video_area, bg='#080e16', highlightthickness=0, width=960, height=540)
        self.canvas.pack(fill='both', expand=True)
        self.image_item = self.canvas.create_image(0, 0, anchor='center')
        self.placeholder = self.canvas.create_text(320, 180, text='Seleccione una fuente e inicie la sesion',
                                                  fill=MUTED, font=('Segoe UI', 14))
        # The card floats over the viewport; it never participates in video geometry.
        self.card = tk.Frame(self.canvas, bg=PANEL, highlightthickness=1, highlightbackground='#344857')
        self.card.place(relx=1, x=-20, y=20, anchor='ne', width=308, height=390)
        self.values = {}
        def label(key, text, x, y, size=11, color=MUTED, width=268, bold=False):
            widget = tk.Label(self.card, text=text, bg=PANEL, fg=color, anchor='w',
                              font=('Segoe UI', size, 'bold' if bold else 'normal'))
            widget.place(x=x, y=y, width=width)
            self.values[key] = widget
            return widget
        label('brand', 'LimpIA', 20, 14, 23, TEXT, bold=True)
        label('subtitle', 'MONITOREO DE PERSONAS', 20, 55, 9, IN)
        label('in_title', 'Entradas', 20, 92, 11, IN, 118)
        label('out_title', 'Salidas', 154, 92, 11, OUT, 118)
        label('entries', '0', 16, 112, 42, TEXT, 126, True)
        label('exits', '0', 150, 112, 42, TEXT, 126, True)
        tk.Frame(self.card, bg='#344857').place(x=20,y=184,width=250,height=1)
        label('status', 'Listo para iniciar', 20, 199, 11, IN)
        label('event_title', 'ULTIMO EVENTO CONFIRMADO', 20, 230, 9)
        label('event', 'Sin eventos confirmados', 20, 250, 12, TEXT)
        label('details', '', 20, 283, 10).configure(justify='left', wraplength=268, anchor='nw')
        label('error', '', 20, 389, 9, OUT).configure(justify='left', wraplength=268, anchor='nw')
        controls = tk.Frame(root, bg=BG, height=64)
        controls.grid(row=2, column=0, columnspan=2, sticky='ew', padx=24, pady=(0, 12))
        self.start_button = ttk.Button(controls, text='Iniciar', command=self.start)
        self.start_button.pack(side='left', padx=(0, 10))
        self.pause_button = ttk.Button(controls, text='Pausar / Reanudar', command=self.session.toggle_pause)
        self.pause_button.pack(side='left', padx=(0, 10))
        if options.source == 'camera':
            self.pause_button.configure(state='disabled')
        ttk.Button(controls, text='Detener', command=self.session.stop).pack(side='left')
        tk.Label(controls, text='Conteo por transiciones A / B confirmadas', bg=BG,
                 fg=MUTED, font=('Segoe UI', 10)).pack(side='right')
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(33, self.tick)

    def start(self):
        if self.session.running or self.closing:
            return
        if self.options.source == 'video' and self.options.video is None:
            path = filedialog.askopenfilename(title='Seleccionar video MP4', filetypes=[('Video MP4', '*.mp4')])
            if not path:
                return
            self.options.video = Path(path)
        self.draw_key = None
        self._ui_signature = None
        self.session.start()
        self.display_state = self.session.snapshot()
        self.shown_times.clear()

    def close(self):
        self.closing = True
        self.session.stop()
        self.values['status'].configure(text='Cerrando · liberando recursos')

    def tick(self):
        tick_started = time.perf_counter()
        if self.closing and not self.session.running:
            self.root.destroy()
            return
        latest = self.session.snapshot()
        queued = self.session.display_queue
        state = latest
        acquired = False
        if queued is not None:
            state = self.display_state
            if not self.session.paused:
                next_state = queued.take()
                if next_state is not None:
                    state, acquired = next_state, True
            if self.session.paused and state.status != 'Pausado':
                state = replace(state, status='Pausado')
            elif (latest.status in ('Inicializando', 'Finalizado', 'Detenido') or latest.error) and (state.status!=latest.status or state.error!=latest.error):
                state = replace(state, status=latest.status, error=latest.error)
        self.display_state = state
        signature = (id(state), self.canvas.winfo_width(), self.canvas.winfo_height(), self.closing)
        if signature == self._ui_signature and not acquired:
            self.root.after(1, self.tick)
            return
        self._ui_signature = signature
        self.start_button.configure(state='disabled' if self.session.running or self.closing else 'normal')
        self.values['entries'].configure(text=str(state.entries) if state.entries is not None else '—')
        self.values['exits'].configure(text=str(state.exits) if state.exits is not None else '—')
        if not self.closing:
            self.values['status'].configure(text=state.status)
        event = state.last_event
        self.values['event'].configure(text=('Entrada detectada' if event.direction == 'IN' else 'Salida detectada')
                                       if event else 'Sin eventos confirmados')
        source = (self.options.video.name if self.options.video else 'MP4 local') if self.options.source == 'video' else f'Cámara {self.options.camera_index}'
        tracker = 'ByteTrack' if self.options.tracker == 'bytetrack' else 'BoT-SORT sin ReID'
        mode = 'Predicciones guardadas' if self.options.predictions else self.options.device
        total = str(state.source_frames) if state.source_frames else '?'
        self.values['details'].configure(text=f'{source}\n{tracker} | {mode}\nFrame {max(0,state.index+1)}/{total} | {state.timestamp:.2f} s | {len(state.tracks)} tracks\nFuente {state.source_fps:.1f} FPS | Visual {self.visual_fps:.1f} FPS')
        notice = state.error[:280] or ('Conteo deshabilitado: camara sin calibrar' if self.options.tracking_only else '')
        self.values['error'].configure(text=notice)
        bottom = 283 + self.values['details'].winfo_reqheight()
        if notice:
            self.values['error'].place_configure(y=bottom+10)
            bottom += 10 + self.values['error'].winfo_reqheight()
        else:
            self.values['error'].place_forget()
        self.card.place_configure(height=bottom+20)
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        key = (state.index, id(state.frame), width, height)
        if key != self.draw_key:
            self.draw_key = key
            self.canvas.coords(self.placeholder, width / 2, height / 2)
            self.canvas.itemconfigure(self.placeholder, state='hidden' if state.frame is not None else 'normal')
            if state.frame is not None:
                try:
                    self.draw(state, width, height)
                finally:
                    if acquired:
                        queued.acknowledge()
                now = time.monotonic()
                self.shown_times.append(now)
                if len(self.shown_times)>1:
                    self.visual_fps = (len(self.shown_times)-1)/(self.shown_times[-1]-self.shown_times[0])
            else:
                self.canvas.itemconfigure(self.image_item, image='')
        self.root.after(1, self.tick)

    def draw(self, state, width, height):
        import cv2
        import numpy as np
        from PIL import Image, ImageTk
        source_height, source_width = state.frame.shape[:2]
        fw, fh = fit_size(source_width, source_height, width, height)
        frame = cv2.resize(state.frame, (fw, fh), interpolation=cv2.INTER_LINEAR)
        profile = self.session.profile
        for polygon, color in (((profile.a, (176, 213, 112)), (profile.b, (131, 186, 236))) if profile is not None else ()):
            points = np.array([(round(x*(fw-1)), round(y*(fh-1))) for x, y in polygon], np.int32)
            cv2.polylines(frame, [points], True, color, 1, cv2.LINE_AA)
        sx, sy = fw / source_width, fh / source_height
        for boxes, color in ((state.tracks, (176, 213, 112)), (state.detections, (150, 160, 170))):
            for box in boxes:
                cv2.rectangle(frame, (round(box.x1*sx), round(box.y1*sy)),
                              (round(box.x2*sx), round(box.y2*sy)), color, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        if self.photo is not None and (self.photo.width(), self.photo.height()) == (fw, fh):
            self.photo.paste(image)
        else:
            self.photo = ImageTk.PhotoImage(image=image)
        self.canvas.coords(self.image_item, width / 2, height / 2)
        self.canvas.itemconfigure(self.image_item, image=self.photo)
        self.render_count += 1


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.log_file:
            handler = logging.FileHandler(args.log_file, mode='x', encoding='utf-8')
            logging.basicConfig(level=logging.INFO, handlers=[handler])
        else:
            logging.basicConfig(level=logging.WARNING)
        options = resolve_choices(args)
        root = tk.Tk()
        window = PresentationWindow(root, options)
        try:
            root.mainloop()
        finally:
            window.session.stop()
            if window.session.thread:
                window.session.thread.join()
        return 1 if window.session.snapshot().error else 0
    except (OSError, ValueError, RuntimeError, tk.TclError) as exc:
        logging.getLogger(__name__).error('%s', exc)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
