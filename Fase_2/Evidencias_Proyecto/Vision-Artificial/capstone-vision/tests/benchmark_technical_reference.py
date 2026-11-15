"""Read-only comparison with the protected technical viewer's actual play loop."""
import argparse,json,statistics,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from src.view_count_results import load_view,play_count

def main():
    p=argparse.ArgumentParser();p.add_argument('--video',required=True);p.add_argument('--count-results',required=True);p.add_argument('--zones',required=True);p.add_argument('--predictions',required=True);p.add_argument('--report',type=Path,required=True)
    o=p.parse_args();view=load_view(o.video,o.count_results,zones_path=o.zones,predictions=o.predictions)
    import cv2
    shown=[]
    class Display:
        def __getattr__(self,name):return getattr(cv2,name)
        def namedWindow(self,name,flags):
            cv2.namedWindow(name,flags);cv2.resizeWindow(name,1880,1000)
        def imshow(self,name,frame):
            cv2.imshow(name,frame);shown.append(time.monotonic())
        def waitKey(self,delay):
            return ord('q') if len(shown)>=600 else cv2.waitKey(delay)
    n=play_count(Display(),view)
    gaps=[(b-a)*1000 for a,b in zip(shown,shown[1:])]
    result=dict(frames=n,interval_ms_p50=statistics.median(gaps),interval_ms_p95=sorted(gaps)[int(.95*(len(gaps)-1))],interval_ms_max=max(gaps),elapsed_seconds=shown[-1]-shown[0],inference=False)
    with o.report.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))
if __name__=='__main__':main()
