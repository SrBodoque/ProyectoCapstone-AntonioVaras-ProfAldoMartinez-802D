"""Small Tk dialogs; native file pickers and cancellable background readiness checks."""
import logging
from pathlib import Path
from queue import Queue,Empty
import threading
import tkinter as tk
from tkinter import filedialog,messagebox,simpledialog,ttk
from .launcher_calibration import Cancelled

BG='#101b29';FG='#eef4fa'


class TkDialogs:
    def __init__(self):
        self.root=tk.Tk();self.root.withdraw()
        self.root.title('LimpIA - Seleccionar fuente');self.root.geometry('620x460');self.root.resizable(False,False)
        self.root.configure(bg=BG)
        self.status=tk.StringVar(value='')

    def choose(self,title,message,choices,cancel_text='Cancelar'):
        top=tk.Toplevel(self.root);top.title('LimpIA - '+title);top.geometry('620x460');top.resizable(False,False);top.configure(bg=BG)
        result=[]
        tk.Label(top,text=title,bg=BG,fg=FG,font=('Segoe UI',22,'bold')).pack(anchor='w',padx=28,pady=(24,10))
        tk.Label(top,text=message,bg=BG,fg='#a9bbc9',wraplength=550,justify='left',font=('Segoe UI',11)).pack(anchor='w',padx=28,pady=(0,16))
        def select(value):result.append(value);top.destroy()
        if len(choices)>6:
            box=tk.Listbox(top,height=8,font=('Segoe UI',11),exportselection=False)
            for value,label in choices:box.insert('end',label)
            box.selection_set(0);box.pack(fill='x',padx=28)
            ttk.Button(top,text='Seleccionar',command=lambda:select(choices[int(box.curselection()[0])][0]) if box.curselection() else None).pack(fill='x',padx=28,pady=8)
        else:
            for index,(value,label) in enumerate(choices):
                button=ttk.Button(top,text=label,command=lambda v=value:select(v))
                button.pack(fill='x',padx=28,pady=5)
                if index==0:
                    button.configure(default='active');button.focus_set()
        tk.Label(top,textvariable=self.status,bg=BG,fg='#a9bbc9',wraplength=550).pack(side='bottom',padx=28)
        ttk.Button(top,text=cancel_text,command=top.destroy).pack(side='bottom',fill='x',padx=28,pady=20)
        top.protocol('WM_DELETE_WINDOW',top.destroy);top.grab_set();self.root.wait_window(top)
        if not result:raise Cancelled()
        return result[0]

    def menu(self):
        return self.choose('LimpIA','Seleccione una fuente o prepare sus zonas.',[('video','Abrir video MP4'),('camera','Abrir camara'),('calibrate','Calibrar zonas')],cancel_text='Salir')

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
    def confirm(self,title,message):return messagebox.askyesno(title,message,parent=self.root)
    def notice(self,message):self.status.set(message)  # Nonblocking; repeated questions are avoided.
    def error(self,message):messagebox.showerror('LimpIA',message,parent=self.root)

    def busy(self,function,title):
        result=Queue(maxsize=1);cancel=threading.Event()
        top=tk.Toplevel(self.root);top.title('LimpIA');top.geometry('500x170');top.resizable(False,False);top.configure(bg=BG)
        label=tk.Label(top,text=title+'...',bg=BG,fg=FG,font=('Segoe UI',13));label.pack(pady=(20,10))
        tk.Label(top,textvariable=self.status,bg=BG,fg='#a9bbc9',wraplength=460).pack(padx=16,pady=(0,8))
        def stop():cancel.set();label.configure(text='Cancelando y liberando recursos...')
        ttk.Button(top,text='Cancelar',command=stop).pack();top.protocol('WM_DELETE_WINDOW',stop)
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
        top=tk.Toplevel(self.root);top.title('LimpIA - Preparar sesion');top.geometry('660x390');top.resizable(False,False);top.configure(bg=BG)
        tk.Label(top,text='Preparar sesion',bg=BG,fg=FG,font=('Segoe UI',22,'bold')).pack(anchor='w',padx=24,pady=18)
        selected_source=('Video: '+args.video.name) if args.mp4 and args.video else f'Camara {args.camera_index}'
        tk.Label(top,text=selected_source,bg=BG,fg=FG,wraplength=600).pack(anchor='w',padx=24,pady=4)
        tk.Label(top,text=('Perfil: '+profile.name if profile else 'Sin calibrar: solo tracking, conteo deshabilitado'),bg=BG,fg=FG).pack(anchor='w',padx=24,pady=6)
        tracker=tk.StringVar(value=args.tracker or 'bytetrack');device=tk.StringVar(value=args.device or inventory.devices[0].device);weights=tk.StringVar(value=str(args.weights_dir))
        tk.Label(top,textvariable=self.status,bg=BG,fg='#a9bbc9',wraplength=600).pack(anchor='w',padx=24)
        form=tk.Frame(top,bg=BG);form.pack(fill='x',padx=24)
        for row,(name,var,values) in enumerate((('Tracker',tracker,('bytetrack','botsort')),('Dispositivo',device,tuple(d.device for d in inventory.devices)))):
            tk.Label(form,text=name,bg=BG,fg=FG).grid(row=row,column=0,sticky='w',pady=10)
            ttk.Combobox(form,textvariable=var,values=values,state='readonly',width=38).grid(row=row,column=1,sticky='ew')
        tk.Label(form,text='Pesos locales',bg=BG,fg=FG).grid(row=2,column=0,sticky='w',pady=10)
        ttk.Entry(form,textvariable=weights,width=42).grid(row=2,column=1)
        def browse():
            path=filedialog.askdirectory(parent=top,title='Directorio local con yolo26n.pt')
            if path:weights.set(path)
        ttk.Button(form,text='Elegir...',command=browse).grid(row=2,column=2,padx=6)
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
        ttk.Button(top,text='Iniciar visualizador',command=start).pack(side='right',padx=24,pady=22)
        ttk.Button(top,text='Cancelar',command=top.destroy).pack(side='left',padx=24,pady=22)
        top.grab_set();self.root.wait_window(top)
        if not result:raise Cancelled()
        return result[0]

    def run_view(self,options):
        from .view_presentation import PresentationWindow
        top=tk.Toplevel(self.root);window=PresentationWindow(top,options)
        top.after(50,window.start)
        self.root.wait_window(top)
        window.session.stop()
        if window.session.thread:window.session.thread.join()
        failed=bool(window.session.snapshot().error)
        if failed:self.error('La fuente o el procesamiento fallo. Puede elegir otra fuente desde el menu.')
        return failed

    def close(self):
        try:self.root.destroy()
        except tk.TclError:pass
