"""Local UI benchmark; no image/video output. Reports use exclusive creation."""
import sys, time, json, statistics
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import tkinter as tk
from src.view_presentation import parser, resolve_choices, PresentationWindow

def run():
    p=parser(); p.add_argument('--report',type=Path,required=True); p.add_argument('--max-frames',type=int,default=600); p.add_argument('--maximized',action='store_true')
    o=resolve_choices(p.parse_args())
    if o.report.exists(): p.error('Report exists')
    root=tk.Tk(); window=PresentationWindow(root,o)
    if o.maximized:root.state('zoomed')
    destroy=root.destroy; root.destroy=lambda:None
    shown=[]; display_ages=[]; draws=[]; ages=[]; captures=[]; ticks=[]; original=window.draw
    def draw(*args):
        t=time.perf_counter(); original(*args); now=time.perf_counter(); draws.append((now-t)*1000)
        state=args[0]
        if state.captured_at is not None and state.index>30:display_ages.append((time.monotonic()-state.captured_at)*1000)
        if not shown or shown[-1][1]!=state.index:shown.append((now,state.index,state.timestamp))
    window.draw=draw
    first=None; last_index=-1; samples=[]; start=time.perf_counter()
    def monitor():
        nonlocal first,last_index
        state=getattr(window,'display_state',window.session.snapshot()); now=time.perf_counter()
        if state.index!=last_index and state.frame is not None:
            if first is None: first=now
            samples.append((now,state.index,state.timestamp,state.processing_fps))
            if state.index>30:
                ages.append(state.frame_age_ms); captures.append(state.capture_fps)
            last_index=state.index
        if (state.frames_processed>=o.max_frames>0) or (not window.session.running and window.session.thread):
            window.close()
        if window.closing and not window.session.running:
            s=window.session.snapshot()
            if o.source=='video' and shown:samples[:]=shown
            gaps=[(b[0]-a[0])*1000 for a,b in zip(shown,shown[1:])]
            steady=samples[30:] if o.source=='camera' and len(samples)>31 else samples
            elapsed=steady[-1][0]-steady[0][0] if len(steady)>1 else 0
            media=steady[-1][2]-steady[0][2] if len(steady)>1 else 0
            report=dict(source=o.source,device=o.device,frames=s.frames_processed,entries=s.entries,exits=s.exits,status=s.status,error=s.error,
                        wall_seconds=elapsed,media_seconds=media,speed=media/elapsed if elapsed else 0,
                        capture_frames_skipped=s.capture_frames_skipped,
                        display_unique_frames=len(shown),
                        display_index_gaps=sum(max(0,b[1]-a[1]-1) for a,b in zip(shown,shown[1:])),
                        display_interval_ms_p50=statistics.median(gaps) if gaps else 0,
                        display_interval_ms_p95=sorted(gaps)[int(.95*(len(gaps)-1))] if gaps else 0,
                        display_interval_ms_max=max(gaps,default=0),
                        display_gap_outliers=[{'frame':b[1],'interval_ms':(b[0]-a[0])*1000} for a,b in zip(shown,shown[1:]) if b[0]-a[0]>.05],
                        display_stalls_over_66ms=sum(g>66.7 for g in gaps),
                        processing_fps_mean=s.processing_fps,
                        render_frames=len(draws),render_ms_mean=statistics.mean(draws) if draws else 0,
                        render_ms_p95=sorted(draws)[int(.95*(len(draws)-1))] if draws else 0,
                        elapsed_total=time.perf_counter()-start,
                        capture_fps_mean=(samples[-1][1]-samples[30][1])/(samples[-1][2]-samples[30][2]) if o.source=='camera' and len(samples)>31 and samples[-1][2]>samples[30][2] else 0,
                        capture_to_display_ms_p95=sorted(display_ages)[int(.95*(len(display_ages)-1))] if display_ages else 0,
                        capture_to_processing_ms_p95=sorted(ages)[int(.95*(len(ages)-1))] if ages else 0)
            with o.report.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
            print(json.dumps(report),flush=True)
            destroy()
            window.draw=original
            window.photo=None
            return
        root.after(10,monitor)
    root.after(100,window.start);root.after(110,monitor)
    root.mainloop()

if __name__=='__main__':run()
