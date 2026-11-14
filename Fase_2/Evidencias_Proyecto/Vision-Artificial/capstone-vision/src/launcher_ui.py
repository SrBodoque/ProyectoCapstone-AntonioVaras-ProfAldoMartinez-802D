"""Small Tk dialogs; native file pickers and cancellable background readiness checks."""
from pathlib import Path
from queue import Queue
import threading
import tkinter as tk
from tkinter import filedialog,messagebox,simpledialog,ttk
from tkinter import font as tkfont
from .launcher_calibration import Cancelled

BG = '#101b29'
PANEL = '#192838'
FG = '#eef4fa'
MUTED = '#a9bbc9'
ACCENT = '#79c9bd'


def ellipsize(text, measure, width):
    """Fit a single line to pixels, retaining both its beginning and suffix."""
    text = ' '.join(str(text).split())
    if measure(text) <= width:
        return text
    if measure('…') > width:
        return ''
    low, high = 0, len(text)
    while low < high:
        keep = (low + high + 1) // 2
        head = (keep + 1) // 2
        tail = keep // 2
        candidate = text[:head] + '…' + (text[-tail:] if tail else '')
        if measure(candidate) <= width:
            low = keep
        else:
            high = keep - 1
    head, tail = (low + 1) // 2, low // 2
    return text[:head] + '…' + (text[-tail:] if tail else '')


def choice_text(value, label):
    """Keep catalog paths as data and use a readable name in the list."""
    path = Path(str(value))
    if path.suffix.lower() not in ('.mp4', '.json'):
        return label
    name = label.rsplit(' | ', 1)[0]
    if path.suffix.lower() == '.mp4' or name == path.name:
        return path.name
    return f'{name} · {path.name}'


def display_message(message):
    """Shorten path-bearing notices and confirmation lines at the UI boundary."""
    lines = []
    for line in str(message).splitlines():
        if line.startswith('Perfil creado: '):
            line = 'Perfil creado: ' + Path(line[len('Perfil creado: '):]).name
        elif Path(line).is_absolute():
            line = Path(line).name
        lines.append(line)
    return '\n'.join(lines)


class CompactLabel(tk.Label):
    """A width-neutral label with pixel ellipsis and a full-text hover detail."""

    def __init__(self, parent, text='', variable=None, detail=None, **kwargs):
        super().__init__(parent, width=1, anchor='w', font=('Segoe UI', 11), **kwargs)
        self.full_text = str(text)
        self.detail = detail
        self.variable = variable
        self.tooltip = None
        self.trace = variable.trace_add('write', self._refresh) if variable is not None else None
        self.bind('<Configure>', self._refresh)
        self.bind('<Enter>', self._show_detail)
        self.bind('<Leave>', self._hide_detail)
        self.bind('<Destroy>', self._dispose)
        self._refresh()

    def _refresh(self, *args):
        text = self.variable.get() if self.variable is not None else self.full_text
        font = tkfont.Font(font=self.cget('font'))
        self.configure(text=ellipsize(display_message(text), font.measure, max(0, self.winfo_width() - 12)))

    def _show_detail(self, event):
        text = self.detail or (self.variable.get() if self.variable is not None else self.full_text)
        if not text or self.tooltip is not None:
            return
        self.tooltip = tk.Toplevel(self)
        self.tooltip.overrideredirect(True)
        width = min(520, self.winfo_screenwidth() - 40)
        tk.Label(self.tooltip, text=text, wraplength=width, justify='left',
                 bg=PANEL, fg=FG, padx=12, pady=10, font=('Segoe UI', 10)).pack()
        self.tooltip.update_idletasks()
        x = min(self.winfo_rootx(), self.winfo_screenwidth() - self.tooltip.winfo_reqwidth() - 12)
        y = min(self.winfo_rooty() + self.winfo_height(),
                self.winfo_screenheight() - self.tooltip.winfo_reqheight() - 12)
        self.tooltip.geometry(f'+{max(0, x)}+{max(0, y)}')

    def _hide_detail(self, event=None):
        if self.tooltip is not None:
            self.tooltip.destroy()
            self.tooltip = None

    def _dispose(self, event):
        if event.widget is self:
            self._hide_detail()
            if self.trace is not None:
                self.variable.trace_remove('write', self.trace)


class TkDialogs:
    def __init__(self):
        self.root=tk.Tk();self.root.withdraw()
        self.root.title('LimpIA - Seleccionar fuente')
        self.root.configure(bg=BG)
        self.status=tk.StringVar(value='')
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('Launcher.TButton', font=('Segoe UI', 11), padding=(16, 10),
                        background=PANEL, foreground=FG, borderwidth=0)
        style.map('Launcher.TButton', background=[('pressed', '#24394c'), ('active', '#294358')])
        style.configure('Primary.Launcher.TButton', background=ACCENT, foreground=BG)
        style.map('Primary.Launcher.TButton', background=[('pressed', '#65b4a8'), ('active', '#9addd2')])
        style.configure('Launcher.TCombobox', padding=8, fieldbackground=PANEL,
                        background=PANEL, foreground=FG, arrowcolor=FG)
        style.map('Launcher.TCombobox', fieldbackground=[('readonly', PANEL)],
                  foreground=[('readonly', FG)], selectbackground=[('readonly', PANEL)],
                  selectforeground=[('readonly', FG)])
        style.configure('Launcher.TEntry', padding=8, fieldbackground=PANEL, foreground=FG,
                        insertcolor=FG)
        self.root.option_add('*TCombobox*Listbox.background', PANEL)
        self.root.option_add('*TCombobox*Listbox.foreground', FG)
        self.root.option_add('*TCombobox*Listbox.selectBackground', '#294358')

    def _window(self, title, size='720x560', minimum=(580, 480)):
        top = tk.Toplevel(self.root)
        top.title('LimpIA - ' + title)
        top.geometry(size)
        top.minsize(*minimum)
        top.configure(bg=BG, padx=28, pady=24)
        top.columnconfigure(0, weight=1, uniform='actions')
        top.columnconfigure(1, weight=1, uniform='actions')
        top.rowconfigure(2, weight=1)
        return top

    def _heading(self, top, title, subtitle):
        tk.Label(top, text=title, bg=BG, fg=FG, anchor='w',
                 font=('Segoe UI', 24, 'bold')).grid(row=0, column=0, columnspan=2, sticky='ew')
        CompactLabel(top, text=subtitle, bg=BG, fg=MUTED).grid(
            row=1, column=0, columnspan=2, sticky='ew', pady=(8, 24))

    def _status(self, top):
        CompactLabel(top, variable=self.status, bg=BG, fg=ACCENT).grid(
            row=3, column=0, columnspan=2, sticky='ew', pady=(16, 12))

    def _button(self, parent, text, command, primary=False):
        return ttk.Button(parent, text=text, command=command,
                          style='Primary.Launcher.TButton' if primary else 'Launcher.TButton')

    def choose(self,title,message,choices,cancel_text='Volver',escape_back=True):
        top = self._window(title)
        result=[]
        self._heading(top, title, message)
        def select(value):result.append(value);top.destroy()
        content = tk.Frame(top, bg=BG)
        content.grid(row=2, column=0, columnspan=2, sticky='nsew')
        content.columnconfigure(0, weight=1)
        if len(choices)>6 or any(Path(str(value)).suffix.lower() in ('.mp4', '.json') for value, _ in choices):
            content.rowconfigure(0, weight=1)
            box = tk.Listbox(content, height=7, width=1, font=('Segoe UI', 12),
                             exportselection=False, bg=PANEL, fg=FG, selectbackground='#294358',
                             selectforeground=FG, activestyle='none', relief='flat', borderwidth=0,
                             highlightthickness=1, highlightbackground='#30475b', highlightcolor=ACCENT)
            box.grid(row=0, column=0, sticky='nsew')
            scroll = ttk.Scrollbar(content, orient='vertical', command=box.yview)
            scroll.grid(row=0, column=1, sticky='ns')
            box.configure(yscrollcommand=scroll.set)
            detail = tk.StringVar(master=top)
            CompactLabel(content, variable=detail, bg=BG, fg=MUTED).grid(
                row=1, column=0, columnspan=2, sticky='ew', pady=(12, 0))
            labels = [choice_text(value, label) for value, label in choices]
            def render(event=None):
                selection = box.curselection()
                position = box.yview()[0]
                measure = tkfont.Font(font=box.cget('font')).measure
                box.delete(0, 'end')
                for label in labels:
                    box.insert('end', '  ' + ellipsize(label, measure, max(0, box.winfo_width() - 28)))
                if selection:
                    box.selection_set(selection[0])
                box.yview_moveto(position)
            def show_selection(event=None):
                if box.curselection():
                    value, label = choices[box.curselection()[0]]
                    detail.set(str(value) if Path(str(value)).suffix.lower() in ('.mp4', '.json') else label)
            box.bind('<Configure>', render)
            box.bind('<<ListboxSelect>>', show_selection)
            render()
            if choices:
                box.selection_set(0)
                show_selection()
            def accept(event=None):
                if box.curselection():
                    select(choices[int(box.curselection()[0])][0])
            box.bind('<Return>', accept)
            box.bind('<Double-Button-1>', accept)
            self._button(top, 'Seleccionar', accept, primary=True).grid(
                row=4, column=1, sticky='ew', padx=(6, 0))
            box.focus_set()
        else:
            for index,(value,label) in enumerate(choices):
                button=self._button(content, choice_text(value, label), lambda v=value:select(v), primary=index==0)
                button.grid(row=index, column=0, sticky='ew', pady=(0, 12))
                if index==0:
                    button.configure(default='active');button.focus_set()
        self._status(top)
        self._button(top, cancel_text, top.destroy).grid(row=4, column=0, sticky='ew', padx=(0, 6))
        top.protocol('WM_DELETE_WINDOW',top.destroy)
        if escape_back:top.bind('<Escape>',lambda event:top.destroy())
        top.grab_set();self.root.wait_window(top)
        if not result:raise Cancelled()
        return result[0]

    def menu(self):
        return self.choose('LimpIA','Seleccione una fuente o prepare sus zonas.',[('video','Abrir video MP4'),('camera','Abrir camara'),('calibrate','Calibrar zonas')],cancel_text='Salir',escape_back=False)

    def _file(self,dialog,**kwargs):
        result=dialog(parent=self.root,**kwargs)
        if not result:raise Cancelled()
        return Path(result).resolve()

    def open_video(self):return self._file(filedialog.askopenfilename,title='Seleccionar MP4',filetypes=[('Video MP4','*.mp4')])
    def open_json(self):return self._file(filedialog.askopenfilename,title='Seleccionar perfil de zonas',filetypes=[('Perfil JSON','*.json')])
    def save_json(self):return self._file(filedialog.asksaveasfilename,title='Guardar perfil NUEVO de zonas',defaultextension='.json',filetypes=[('Perfil JSON','*.json')],confirmoverwrite=False)
    def text(self,title,prompt):
        value=simpledialog.askstring(title,prompt,parent=self.root)
        if value is None:raise Cancelled()
        return value
    def integer(self,title,prompt,initial):
        value=simpledialog.askinteger(title,prompt,parent=self.root,initialvalue=initial,minvalue=0,maxvalue=2**31-1)
        if value is None:raise Cancelled()
        return value
    def manual_camera(self,backend):
        index=self.integer('Camara manual','Indice del dispositivo',0)
        from .camera import backend_candidates
        choices=[(name,name.upper()) for name,_ in backend_candidates('auto')]
        return index,self.choose('Backend','Seleccione un backend compatible',choices)
    def confirm(self,title,message):
        message = display_message(message)
        message = '\n'.join(ellipsize(line, len, 100) for line in message.splitlines())
        return messagebox.askyesno(title,message,parent=self.root)
    def notice(self,message):self.status.set(message)  # Nonblocking; repeated questions are avoided.
    def error(self,message):messagebox.showerror('LimpIA',message,parent=self.root)

    def busy(self,function,title):
        result=Queue(maxsize=1);cancel=threading.Event()
        top = self._window('Comprobando recursos', '600x240', (480, 220))
        label = CompactLabel(top, text=title+'…', bg=BG, fg=FG)
        label.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 16))
        self._status(top)
        def stop():
            cancel.set()
            label.full_text = 'Cancelando y liberando recursos…'
            label._refresh()
        self._button(top, 'Cancelar', stop).grid(row=4, column=0, columnspan=2, sticky='ew')
        top.protocol('WM_DELETE_WINDOW',stop);top.bind('<Escape>',lambda event:stop())
        def run():
            try:result.put((True,function(cancel)))
            except BaseException as exc:result.put((False,exc))
        def poll():
            if result.empty():top.after(40,poll)
            else:top.destroy()
        thread=threading.Thread(target=run,name='LimpIA-launcher-check',daemon=True);thread.start()
        top.grab_set();top.after(40,poll);self.root.wait_window(top)
        ok,value=result.get();thread.join()
        if cancel.is_set() or isinstance(value,InterruptedError):raise Cancelled()
        if not ok:raise value
        return value

    def settings(self,args,profile):
        from .devices import discover_devices,load_torch
        inventory=self.busy(lambda cancel:discover_devices(load_torch()),'Buscando CPU/GPU disponibles')
        top = self._window('Preparar sesion', '720x560', (580, 540))
        self._heading(top, 'Preparar sesión', 'Revise la selección y los recursos locales antes de iniciar.')
        tracker=tk.StringVar(value=args.tracker or 'bytetrack');device=tk.StringVar(value=args.device or inventory.devices[0].device);weights=tk.StringVar(value=str(args.weights_dir))
        form = tk.Frame(top, bg=PANEL, padx=16, pady=12)
        form.grid(row=2, column=0, columnspan=2, sticky='new')
        form.columnconfigure(1, weight=1)
        def row_label(row, name):
            tk.Label(form, text=name, bg=PANEL, fg=MUTED, font=('Segoe UI', 10),
                     anchor='w').grid(row=row, column=0, sticky='w', padx=(0, 20), pady=12)
        selected_source=args.video.name if args.mp4 and args.video else f'Cámara {args.camera_index}'
        profile_path = getattr(args, 'zones', None)
        for row, (name, value, detail) in enumerate((
                ('Video' if args.mp4 else 'Cámara', selected_source, str(args.video) if args.video else None),
                ('Perfil', profile.name if profile else 'Sin calibrar · conteo deshabilitado',
                 str(profile_path) if profile_path else None))):
            row_label(row, name)
            CompactLabel(form, text=value, detail=detail, bg=PANEL, fg=FG).grid(
                row=row, column=1, columnspan=2, sticky='ew', pady=8)
        for row,(name,var,values) in enumerate((('Tracker',tracker,('bytetrack','botsort')),('Dispositivo',device,tuple(d.device for d in inventory.devices)))):
            row_label(row + 2, name)
            ttk.Combobox(form, textvariable=var, values=values, state='readonly', width=1,
                         font=('Segoe UI', 11), style='Launcher.TCombobox').grid(
                             row=row+2, column=1, columnspan=2, sticky='ew', pady=6)
        row_label(4, 'Pesos locales')
        ttk.Entry(form, textvariable=weights, width=1, font=('Segoe UI', 11),
                  style='Launcher.TEntry').grid(row=4, column=1, sticky='ew', pady=6)
        def browse():
            path=filedialog.askdirectory(parent=top,title='Directorio local con yolo26n.pt')
            if path:weights.set(path)
        self._button(form, 'Elegir…', browse).grid(row=4, column=2, padx=(8, 0), pady=6)
        self._status(top)
        result=[]
        def start():
            from .launcher_resources import valid_weights
            from .devices import validate_device
            path=Path(weights.get()).expanduser().resolve()
            if not valid_weights(path):
                self.status.set('La carpeta debe contener yolo26n.pt no vacio. Elija otra carpeta.');return
            selected_device=device.get()  # Read Tk variables ONLY on their owning UI thread.
            try:self.busy(lambda cancel:validate_device(selected_device),'Validando dispositivo')
            except Cancelled:
                self.status.set('Validacion cancelada. Puede volver a iniciar.');return
            except (ValueError,RuntimeError) as exc:self.status.set(str(exc));return
            result.append((tracker.get(),device.get(),path));top.destroy()
        self._button(top, 'Iniciar visualizador', start, primary=True).grid(
            row=4, column=1, sticky='ew', padx=(6, 0))
        def back():
            args.tracker=tracker.get();args.device=device.get();args.weights_dir=Path(weights.get()).expanduser()
            top.destroy()
        self._button(top, 'Volver', back).grid(row=4, column=0, sticky='ew', padx=(0, 6))
        top.protocol('WM_DELETE_WINDOW',back);top.bind('<Escape>',lambda event:back())
        top.grab_set();self.root.wait_window(top)
        if not result:raise Cancelled()
        return result[0]

    def run_view(self,options):
        from .view_presentation import PresentationWindow
        previous=set(self.root.tk.call('after','info'))
        top=tk.Toplevel(self.root);window=PresentationWindow(top,options)
        top.after(50,window.start)
        try:self.root.wait_window(top)
        finally:
            window.session.stop()
            if window.session.thread:window.session.thread.join()
            # Timers created by this modal host must not survive its Toplevel.
            for token in set(self.root.tk.call('after','info'))-previous:
                self.root.tk.call('after','cancel',token)
        failed=bool(window.session.snapshot().error)
        if failed:self.error('La fuente o el procesamiento fallo. Puede elegir otra fuente desde el menu.')
        return failed

    def close(self):
        try:self.root.destroy()
        except tk.TclError:pass
