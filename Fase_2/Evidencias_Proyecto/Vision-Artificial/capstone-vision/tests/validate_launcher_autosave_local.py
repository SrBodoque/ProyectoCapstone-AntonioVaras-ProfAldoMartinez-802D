"""Real OpenCV/Tk/CUDA integration; input events automated, not manual acceptance."""
import argparse,json,os,sys,uuid,gc
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import cv2
from tkinter import ttk
from src.launcher import Launcher,parser
from src.launcher_ui import TkDialogs
from src.presentation_sources import load_profile
from src.view_presentation import PresentationWindow
from src.video_source import file_sha256


def main():
    p=argparse.ArgumentParser();p.add_argument('--resources',type=Path,required=True);o=p.parse_args()
    token=uuid.uuid4().hex
    os.environ['LOCALAPPDATA']=str(Path('logs')/('autosave-ui-'+token))
    video=o.resources/'videos_testing/nuevo_angulo/video_03.mp4'
    baseline=Path('config/baselines/sala_v4.json')
    before=file_sha256(baseline)
    geometry=load_profile(baseline,'video',video)
    ui=TkDialogs();errors=[];drawn=[];callbacks=[]
    ui.root.report_callback_exception=lambda *e:errors.append(str(e[1]))
    sys.unraisablehook=lambda e:errors.append(str(e.exc_value))
    def choose_new():
        for dialog in ui.root.winfo_children():
            for widget in dialog.winfo_children():
                if isinstance(widget,ttk.Button) and widget.cget('text')=='Dibujar zonas nuevas':widget.invoke();ui.root.after(20,click_settings);return
        ui.root.after(20,choose_new)
    def click_settings():
        for dialog in ui.root.winfo_children():
            if dialog.title()=='LimpIA - Preparar sesion':
                for widget in dialog.winfo_children():
                    if isinstance(widget,ttk.Button) and widget.cget('text')=='Iniciar visualizador':widget.invoke();return
        ui.root.after(20,click_settings)
    real_mouse=cv2.setMouseCallback;real_wait=cv2.waitKey
    def mouse(window,callback,*a):callbacks.append(callback);return real_mouse(window,callback,*a)
    def wait(ms):
        key=real_wait(ms)
        if not drawn and callbacks:
            from src.zone_calibrator import preview_size
            frame=__import__('src.calibrate_mp4_zones',fromlist=['reference_frame']).reference_frame(video,0)
            w,h=preview_size(frame)
            # Input injection through the real editor's registered callback. No seed.
            callback=callbacks[-1]
            for x,y in geometry.a:callback(cv2.EVENT_LBUTTONDOWN,round(x*w),round(y*h),0,None);callback(cv2.EVENT_LBUTTONUP,round(x*w),round(y*h),0,None)
            callback(cv2.EVENT_RBUTTONDOWN,0,0,0,None)
            drawn.append(True)
            return ord('b')
        if len(drawn)==1:
            frame=__import__('src.calibrate_mp4_zones',fromlist=['reference_frame']).reference_frame(video,0)
            from src.zone_calibrator import preview_size
            w,h=preview_size(frame);callback=callbacks[-1]
            for x,y in geometry.b:callback(cv2.EVENT_LBUTTONDOWN,round(x*w),round(y*h),0,None);callback(cv2.EVENT_LBUTTONUP,round(x*w),round(y*h),0,None)
            callback(cv2.EVENT_RBUTTONDOWN,0,0,0,None);drawn.append(True)
            return ord('s')
        return key
    try:
        args=parser().parse_args(['--mp4','--calibrar','--video',str(video),'--reviewer','Automated integration; not human calibration acceptance','--tracker','bytetrack','--device','cuda:0','--weights-dir',str(o.resources)])
        ui.root.after(20,choose_new)
        # Confirmation supplies the same answer as the real prompt, while editor
        # windows/rendering and CUDA processing remain real.
        with patch.object(ui,'save_json',side_effect=AssertionError('Unexpected save dialog')),patch.object(ui,'confirm',return_value=True),patch.object(cv2,'setMouseCallback',side_effect=mouse),patch.object(cv2,'waitKey',side_effect=wait):
            options=Launcher(ui).prepare(args)
        import tkinter as tk
        top=tk.Toplevel(ui.root);window=PresentationWindow(top,options)
        def stop():
            if window.display_state.frames_processed>=60 or window.session.snapshot().error:window.close()
            else:top.after(20,stop)
        top.after(50,window.start);top.after(100,stop);ui.root.wait_window(top)
        state=window.session.snapshot()
        report=dict(profile=str(options.zones),frames=state.frames_processed,device=options.device,error=state.error,tk_errors=errors,baseline_unchanged=file_sha256(baseline)==before,automated_input=True)
        path=Path('logs')/('autosave-real-'+token+'.json');path.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
        return 0 if state.frames_processed>=60 and not errors and not state.error and report['baseline_unchanged'] else 1
    finally:ui.close();gc.collect()
if __name__=='__main__':raise SystemExit(main())
