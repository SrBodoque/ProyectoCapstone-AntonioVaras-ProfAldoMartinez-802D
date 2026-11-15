"""Real Tk/OpenCV navigation and two CUDA sessions; UI inputs automated."""
import argparse,gc,json,os,sys,threading,uuid
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import cv2,tkinter as tk
from tkinter import ttk
from src import launcher
from src.launcher_ui import TkDialogs
from src.launcher_calibration import Cancelled
from src.camera_selector import AvailableCamera
from src.view_presentation import PresentationWindow


def main():
    p=argparse.ArgumentParser();p.add_argument('--resources',type=Path,required=True);o=p.parse_args()
    token=uuid.uuid4().hex;os.environ['LOCALAPPDATA']=str(Path('logs')/('navigation-ui-'+token))
    video=str((o.resources/'videos_testing/nuevo_angulo/video_03.mp4').resolve())
    baseline=str(Path('config/baselines/sala_v4.json').resolve())
    steps=[('LimpIA','calibrate'),('Calibrar zonas','video'),('Videos disponibles',video),
        ('Base de calibracion','new'),('Base de calibracion','edit'),('Perfiles compatibles',None),
        ('Base de calibracion',None),('Videos disponibles',None),('Calibrar zonas','camera'),
        ('Seleccionar camara',None),('Calibrar zonas',None),('LimpIA','video'),
        ('Videos disponibles',video),('Zonas de transicion',baseline),
        ('Zonas de transicion',baseline),('LimpIA','video'),('Videos disponibles',video),
        ('Zonas de transicion',baseline),('LimpIA',None)]
    completed=[];errors=[];sessions=[];settings=[];windows=[]
    class Dialogs(TkDialogs):
        def __init__(self):
            super().__init__();self.root.report_callback_exception=lambda *e:errors.append(str(e[1]))
        def choose(self,title,message,choices,**kw):
            expected,value=steps.pop(0)
            if title!=expected:raise AssertionError(f'Expected {expected}, got {title}')
            def act():
                tops=[t for t in self.root.winfo_children() if t.title()=='LimpIA - '+title]
                if not tops:self.root.after(10,act);return
                top=tops[0];top.update_idletasks()
                if value is None:
                    if title=='LimpIA':self.root.tk.call(top.protocol('WM_DELETE_WINDOW'))
                    else:top.focus_force();top.event_generate('<Escape>',when='tail')
                    return
                index=next(i for i,c in enumerate(choices) if c[0]==value)
                if len(choices)>6:
                    box=next(w for w in top.winfo_children() if isinstance(w,tk.Listbox));box.selection_clear(0,'end');box.selection_set(index)
                    text='Seleccionar'
                else:text=choices[index][1]
                next(w for w in top.winfo_children() if isinstance(w,ttk.Button) and w.cget('text')==text).invoke()
            self.root.after(10,act)
            try:return super().choose(title,message,choices,**kw)
            finally:completed.append([title,value])
        def settings(self,args,profile):
            cancel=not settings;settings.append('cancel' if cancel else 'start')
            def act():
                tops=[t for t in self.root.winfo_children() if t.title()=='LimpIA - Preparar sesion']
                if not tops:self.root.after(10,act);return
                top=tops[0];top.update_idletasks()
                if cancel:top.focus_force();top.event_generate('<Escape>',when='tail')
                else:next(w for w in top.winfo_children() if isinstance(w,ttk.Button) and w.cget('text')=='Iniciar visualizador').invoke()
            self.root.after(10,act)
            return super().settings(args,profile)
        def error(self,message):errors.append(message);raise RuntimeError(message)
    class Window(PresentationWindow):
        def __init__(self,top,options):
            super().__init__(top,options);windows.append(self)
            def monitor():
                if self.display_state.frames_processed>=60 or self.session.snapshot().error:self.close()
                else:top.after(20,monitor)
            top.after(100,monitor)
    ui=Dialogs();sys.unraisablehook=lambda e:errors.append(str(e.exc_value))
    real_wait=cv2.waitKey;editor_keys=[]
    def escape(ms):
        real_wait(ms);editor_keys.append(27);return 27
    try:
        with patch('src.launcher_ui.TkDialogs',return_value=ui),patch('src.view_presentation.PresentationWindow',Window),patch.object(cv2,'waitKey',side_effect=escape),patch.object(launcher,'scan_cameras',return_value=[AvailableCamera(0,1920,1080,'MSMF',30.)]):
            result=launcher.main(['--tracker','bytetrack','--device','cuda:0','--weights-dir',str(o.resources)])
        for w in windows:
            state=w.session.snapshot();sessions.append(dict(frames=state.frames_processed,error=state.error))
        windows.clear();gc.collect()
        report=dict(result=result,remaining_steps=steps,completed=completed,settings=settings,editor_escape=editor_keys,sessions=sessions,
            errors=errors,workers_remaining=[t.name for t in threading.enumerate() if t.name.startswith('LimpIA')],camera_probe_simulated=True,gui_input_automated=True)
        accepted=not steps and not errors and len(sessions)==2 and all(s['frames']>=60 and not s['error'] for s in sessions) and not report['workers_remaining']
        report['accepted']=accepted
        Path('logs',f'navigation-real-{token}.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
        return 0 if accepted else 1
    finally:ui.close();gc.collect()
if __name__=='__main__':raise SystemExit(main())
