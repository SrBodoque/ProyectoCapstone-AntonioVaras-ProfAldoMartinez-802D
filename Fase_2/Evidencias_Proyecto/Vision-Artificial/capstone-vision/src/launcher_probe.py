"""Bounded native-camera probes; imports no models and writes no preferences."""
import multiprocessing as mp
import time
from queue import Empty
from .camera_selector import AvailableCamera


def _probe_worker(index, backend, output):
    try:
        from .config import load_config
        from .camera import camera_info
        from .presentation_sources import native_camera_session, validate_frame
        with native_camera_session({**load_config(), 'camera_index':index, 'backend':backend}) as (capture,frame):
            validate_frame(frame,None)
            info=camera_info(capture)
            height,width=frame.shape[:2]
            camera=AvailableCamera(index,width,height,info['backend'],info['fps'])
        output.put(('ok',camera))  # Release happens BEFORE returning success.
    except Exception as exc:
        output.put(('error',str(exc)))


def probe_camera(index, backend='msmf', timeout=4., cancel=None):
    if type(index) is not int or not 0<=index<2**31 or not .1<=timeout<=30:
        raise ValueError('Indice o timeout de camara invalido.')
    context=mp.get_context('spawn');output=context.Queue(maxsize=1)
    process=context.Process(target=_probe_worker,args=(index,backend,output),daemon=True)
    try:
        process.start();deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if cancel is not None and cancel.is_set():raise InterruptedError('Sondeo cancelado.')
            try:
                status,value=output.get(timeout=min(.1,max(.001,deadline-time.monotonic())))
                if status!='ok':raise RuntimeError(value)
                return value
            except Empty:
                if not process.is_alive():break
        raise RuntimeError(f'Camara {index}: no entrego un frame valido dentro del timeout.')
    finally:
        if process.pid is not None:
            process.join(.2)
            if process.is_alive():process.terminate();process.join(2)
            process.close()
        output.close();output.join_thread()


def scan_cameras(limit=5,backend='msmf',timeout=4.,cancel=None,probe=probe_camera):
    if type(limit) is not int or not 1<=limit<=16:raise ValueError('El rango de busqueda debe estar entre 1 y 16.')
    available=[]
    for index in range(limit):
        if cancel is not None and cancel.is_set():raise InterruptedError('Busqueda cancelada.')
        try:available.append(probe(index,backend,timeout,cancel))
        except RuntimeError:pass
    return available
