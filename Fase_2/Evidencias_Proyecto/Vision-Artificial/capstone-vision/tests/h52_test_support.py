"""Fixtures nuevos; nunca usan videos, pesos ni aprobaciones personales."""

from pathlib import Path
from src.video_zones import export_video_zones
from src.zones import ZoneProfile
from stage15_test_support import box, row, write_case


def profile():
    return ZoneProfile.create("synthetic", 0, 160, 160,
        ((.1,.2),(.4,.2),(.4,.8),(.1,.8)),
        ((.6,.2),(.9,.2),(.9,.8),(.6,.8)))


def fixture(root, *, real_video=False):
    root = Path(root)
    video = root / "synthetic.mp4"
    if real_video:
        import cv2
        import numpy as np
        writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 5, (160,160))
        if not writer.isOpened():
            writer.release()
            raise RuntimeError("Encoder MP4 no disponible; no se declara aprobado.")
        try:
            for value in (10,50,100,150):
                writer.write(np.full((160,160,3),value,dtype=np.uint8))
        finally:
            writer.release()
    else:
        video.write_bytes(b"fixture for hashes, not an actual MP4")
    rows = [row(i, [box(1,x1=20 if i<2 else 100,y1=30,x2=60 if i<2 else 140,y2=80)],
                timestamp_ms=i*200, timestamp_source="synthetic") for i in range(4)]
    case = write_case(root/"case",video,rows,device_effective="cpu",
                      video=dict(width=160,height=160,reported_frames=4,reported_fps=5),
                      configuration=dict(model="yolo26n.pt",model_sha256="a"*64,
                      tracker_parameters=dict(tracker_type="bytetrack"),device_name="SYNTHETIC"))
    zones = root/"zones.json"
    export_video_zones(zones,video,profile(),0,"AUTOMATED SYNTHETIC FIXTURE; not human acceptance")
    return video,case,zones
