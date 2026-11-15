"""Opt-in: actual launcher planning + unchanged professional window and new inference."""
import argparse,json,sys,time,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from src.launcher import Launcher,parser
from src.launcher_ui import TkDialogs
from src.view_presentation import PresentationWindow


def main():
    p=argparse.ArgumentParser();p.add_argument('--resources',type=Path,required=True);p.add_argument('--camera',action='store_true');p.add_argument('--max-frames',type=int,default=0);p.add_argument('--auto-resources',action='store_true');p.add_argument('--report',type=Path,required=True)
    o=p.parse_args()
    if o.report.exists():p.error('Report must be new')
    args=['--camara','--camera-index','0','--tracking-only'] if o.camera else ['--mp4','--video',str(o.resources/'videos_testing/nuevo_angulo/video_03.mp4'),'--zones','config/baselines/sala_v4.json']
    args+=['--tracker','bytetrack']
    if not o.auto_resources:args+=['--device','cuda:0','--weights-dir',str(o.resources)]
    ui=TkDialogs()
    try:
        prepared=Launcher(ui).prepare(parser().parse_args(args))
        import tkinter as tk
        top=tk.Toplevel(ui.root);window=PresentationWindow(top,prepared);top.state('zoomed')
        shown=[];original=window.draw
        def draw(state,*rest):
            original(state,*rest);shown.append((time.monotonic(),state.index,state.timestamp))
        window.draw=draw
        started=time.monotonic()
        def monitor():
            if not top.winfo_exists():return
            state=window.session.snapshot()
            if (o.max_frames>0 and window.display_state.frames_processed>=o.max_frames) or (o.camera and window.display_state.frames_processed>=300) or (window.session.thread and not window.session.running):
                window.close();return
            top.after(20,monitor)
        top.after(50,window.start);top.after(100,monitor)
        ui.root.wait_window(top)
        state=window.session.snapshot();window.draw=original;window.photo=None
        report=dict(source=prepared.source,prepared_video=str(prepared.video),prepared_zones=str(prepared.zones),
                    device=prepared.device,tracker=prepared.tracker,tracking_only=prepared.tracking_only,
                    frames_processed=state.frames_processed,frames_shown=len(shown),entries=state.entries,exits=state.exits,
                    status=state.status,error=state.error,elapsed_seconds=time.monotonic()-started,
                    sequential=all(b[1]==a[1]+1 for a,b in zip(shown,shown[1:])),
                    inference='new local inference; no saved predictions',
                    accepted=not state.error and ((state.frames_processed>=o.max_frames) if o.max_frames>0 else ((state.frames_processed==5732 and len(shown)==5732 and (state.entries,state.exits)==(21,20)) if not o.camera else (state.frames_processed>=300 and state.entries is None and state.exits is None))))
        with o.report.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
        print(json.dumps(report),flush=True)
        return 0 if report['accepted'] else 1
    finally:ui.close()

if __name__=='__main__':
    from multiprocessing import freeze_support
    freeze_support()
    raise SystemExit(main())
