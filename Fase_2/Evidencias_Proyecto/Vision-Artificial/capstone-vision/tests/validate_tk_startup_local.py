"""Actual CUDA settings-button validation and two real viewer sessions in one Tk root."""
import sys,json,threading,gc
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import tkinter as tk
from tkinter import ttk
from src.launcher import parser,Launcher
from src.launcher_ui import TkDialogs
from src.view_presentation import PresentationWindow

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--resources',type=Path,required=True);o=p.parse_args()
    ui=TkDialogs();errors=[];sessions=[]
    sys.unraisablehook=lambda exc:errors.append(str(exc.exc_value))
    ui.root.report_callback_exception=lambda *exc:errors.append(str(exc[1]))
    def click():
        for top in ui.root.winfo_children():
            if top.title()=='LimpIA - Preparar sesion':
                for child in top.winfo_children():
                    if isinstance(child,ttk.Button) and child.cget('text')=='Iniciar visualizador':child.invoke();return
        ui.root.after(20,click)
    try:
        for n in range(2):
            def choose_video():
                for dialog in ui.root.winfo_children():
                    for child in dialog.winfo_children():
                        if isinstance(child,ttk.Button) and child.cget('text')=='Abrir video MP4':child.invoke();return
                ui.root.after(20,choose_video)
            ui.root.after(20,choose_video)
            assert ui.menu()=='video'

            args=parser().parse_args(['--mp4','--video',str(o.resources/'videos_testing/nuevo_angulo/video_03.mp4'),'--zones','config/baselines/sala_v4.json','--device','cuda:0','--weights-dir',str(o.resources)])
            ui.root.after(20,click)
            prepared=Launcher(ui).prepare(args)  # tracker omitted: actual settings GUI is mandatory.
            top=tk.Toplevel(ui.root);window=PresentationWindow(top,prepared)
            def monitor():
                if window.display_state.frames_processed>=60 or window.session.snapshot().error:window.close()
                elif top.winfo_exists():top.after(20,monitor)
            top.after(50,window.start);top.after(100,monitor)
            ui.root.wait_window(top)
            state=window.session.snapshot()
            sessions.append(dict(device=prepared.device,frames=state.frames_processed,error=state.error,status=state.status))
            del window,top;gc.collect()
        report=dict(sessions=sessions,tk_callback_errors=errors,workers_remaining=[t.name for t in threading.enumerate() if t.name.startswith('LimpIA')],accepted=not errors and all(s['frames']>=60 and not s['error'] for s in sessions))
        with Path('logs/tk-startup-real-cuda-final.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
        print(json.dumps(report),flush=True)
        return 0 if report['accepted'] else 1
    finally:ui.close();gc.collect()
if __name__=='__main__':main()
