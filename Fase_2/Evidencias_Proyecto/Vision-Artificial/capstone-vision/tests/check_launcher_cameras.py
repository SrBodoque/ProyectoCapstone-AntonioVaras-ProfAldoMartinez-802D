"""Bounded physical discovery, metadata only; no images are saved."""
from dataclasses import asdict
import json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from src.launcher_probe import scan_cameras

def main():
    started=time.monotonic()
    cameras=scan_cameras(limit=3,backend='msmf',timeout=4.)
    report=dict(limit=3,backend='msmf',timeout_per_device_seconds=4.,elapsed_seconds=time.monotonic()-started,
                cameras=[asdict(c) for c in cameras],frames_saved=False,probes_released_before_results=True)
    with Path('logs/launcher-real-camera-scan.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
    print(json.dumps(report),flush=True)
    return 0 if cameras else 1
if __name__=='__main__':
    from multiprocessing import freeze_support
    freeze_support()
    raise SystemExit(main())
