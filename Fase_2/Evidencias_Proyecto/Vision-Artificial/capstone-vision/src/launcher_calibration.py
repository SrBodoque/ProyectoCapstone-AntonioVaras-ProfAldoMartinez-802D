"""Calibration adapters: existing editor and geometry, exclusive JSON exports."""
from contextlib import contextmanager
from datetime import datetime,timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .config import PROJECT_ROOT,load_config
from .calibrate_mp4_zones import reference_frame,edit_frame
from .presentation_sources import native_camera_session,validate_frame,load_profile
from .video_source import discover_cases,file_sha256
from .video_zones import export_video_zones
from .zones import ZoneProfile,ZoneStore


class Cancelled(Exception):pass


def new_output(path):
    path=Path(path).expanduser()
    if path.is_symlink():raise ValueError('No se guardan perfiles sobre enlaces.')
    path=path.resolve()
    if (path.exists() or path.is_symlink() or path.suffix.lower()!='.json' or not path.parent.is_dir()
            or any(part.lower() in ('baselines','.git') for part in path.parts)):
        raise ValueError('Elija un JSON NUEVO fuera de baselines; no se sobrescriben perfiles existentes.')
    return path


def validate_video(video):
    video=discover_cases(video=video)[0].path
    frame=reference_frame(video,0)
    validate_frame(frame,None)
    return video,frame.shape[1],frame.shape[0]


def edit_profile(frame,camera_index=0,seed=None,camera=False,on_save=None):
    """The MP4 editor uses index zero; only transport metadata is adapted here."""
    import cv2
    if seed is not None and (seed.width,seed.height)!=(frame.shape[1],frame.shape[0]):
        raise ValueError('El perfil inicial no coincide con la resolucion del frame.')
    root=PROJECT_ROOT/'logs'/'launcher_calibration'
    root.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory(prefix='edit-',dir=root) as directory:
        if not Path(directory).resolve().is_relative_to(root.resolve()):raise RuntimeError('Temporal fuera del espacio de calibracion.')
        store=ZoneStore(Path(directory)/'profiles')
        if seed is not None:
            editing=ZoneProfile.create(seed.name,camera_index if camera else 0,seed.width,seed.height,seed.a,seed.b)
            store.save_and_activate(editing)
        try:profile=edit_camera_frame(cv2,frame,store,camera_index,on_save) if camera or on_save else edit_frame(cv2,frame,store)
        except ValueError:
            if not (store.directory/'active.json').exists():raise Cancelled()
            raise
        return ZoneProfile.create(profile.name,camera_index,profile.width,profile.height,profile.a,profile.b)


def edit_camera_frame(cv2,frame,store,index,on_save=None):
    """Thin fixed-image host for the existing editor, with the actual camera ID."""
    from .zone_calibrator import CalibrationEditor,preview_size,render_editor
    height,width=frame.shape[:2]
    editor=CalibrationEditor(store,index,width,height)
    editor.status='A exterior / B puerta. S guarda version nueva; W Guardar como; Q cancela.'
    saved=[]
    display=preview_size(frame)
    window='LimpIA - Calibrar zonas A exterior / B puerta' if on_save else 'LimpIA - Calibrar frame de camara congelado'
    def mouse(event,x,y,flags,param):
        actions={cv2.EVENT_LBUTTONDOWN:'down',cv2.EVENT_LBUTTONUP:'up',cv2.EVENT_MOUSEMOVE:'move',cv2.EVENT_RBUTTONDOWN:'right'}
        if event in actions:editor.mouse(actions[event],x,y,*display)
    def open_window():
        cv2.namedWindow(window,cv2.WINDOW_AUTOSIZE);cv2.setMouseCallback(window,mouse)
    try:
        open_window()
        while not editor.exit_requested:
            editor.frozen=True
            cv2.imshow(window,render_editor(cv2,frame,editor))
            key=cv2.waitKey(20)&255
            if on_save and editor.mode=='edit' and key in (ord('s'),ord('S'),ord('w'),ord('W')):
                try:
                    profile=editor.profile(editor.name or 'calibracion')
                    on_save(profile,key in (ord('w'),ord('W')))
                    saved.append(profile);editor.exit_requested=True
                except Cancelled:editor.status='Guardado cancelado; zonas conservadas. S reintenta.'
                except (ValueError,OSError,RuntimeError) as exc:editor.status=f'{exc} | Zonas conservadas; S reintenta.'
            else:editor.key(key)
            if editor.exit_requested:break
            try:visible=cv2.getWindowProperty(window,cv2.WND_PROP_VISIBLE)
            except cv2.error:visible=-1
            if visible<1:
                editor.request_exit()
                if not editor.exit_requested:open_window()
    finally:
        try:cv2.destroyWindow(window)
        except cv2.error:pass
    if on_save:
        if not saved:raise Cancelled()
        return saved[0]
    return store.load_active()


def freeze_camera(index,backend):
    import cv2
    config={**load_config(),'camera_index':index,'backend':backend}
    window='LimpIA - Espacio: capturar frame | Esc: cancelar'
    try:
        with native_camera_session(config) as (capture,frame):
            cv2.namedWindow(window,cv2.WINDOW_NORMAL)
            while True:
                validate_frame(frame,None);cv2.imshow(window,frame)
                key=cv2.waitKey(20)&255
                if key==32:return frame.copy()
                if key in (27,ord('q')) or cv2.getWindowProperty(window,cv2.WND_PROP_VISIBLE)<1:raise Cancelled()
                ok,frame=capture.read()
                if not ok:raise RuntimeError('La camara dejo de entregar imagenes.')
    finally:
        try:cv2.destroyWindow(window)
        except cv2.error:pass


def calibrate_video(video,output,frame_index,reviewer,seed=None,on_save=None):
    if output is not None:output=new_output(output)
    case=discover_cases(video=video)[0]
    video=case.path
    frame=reference_frame(video,frame_index)
    if on_save:
        def save(profile,advanced):
            if (profile.width,profile.height)!=(frame.shape[1],frame.shape[0]):raise ValueError('Resolucion del perfil incompatible.')
            if file_sha256(video)!=case.sha256:raise RuntimeError('El MP4 cambio durante la calibracion.')
            return on_save(profile,advanced)
        return edit_profile(frame,seed=seed,on_save=save)
    profile=edit_profile(frame,seed=seed)
    if file_sha256(video)!=case.sha256:
        raise RuntimeError('El MP4 cambio durante la calibracion; no se exportaron zonas.')
    export_video_zones(output,video,profile,frame_index,reviewer)
    load_profile(output,'video',video)
    return output


def calibrate_camera(index,backend,output,reviewer,seed=None,on_save=None):
    if on_save:
        frame=freeze_camera(index,backend)
        return edit_profile(frame,index,seed,camera=True,on_save=on_save)
    if not isinstance(reviewer,str) or not reviewer.strip():raise ValueError('Indique un responsable.')
    output=new_output(output)
    sidecar=new_output(output.with_name(output.stem+'.provenance.json'))
    frame=freeze_camera(index,backend)
    profile=edit_profile(frame,index,seed,camera=True)
    profile=ZoneProfile.from_dict(profile.to_dict())
    if (profile.width,profile.height)!=(frame.shape[1],frame.shape[0]):
        raise ValueError('La calibracion no coincide con el frame capturado.')
    with output.open('x',encoding='utf-8') as stream:json.dump(profile.to_dict(),stream,ensure_ascii=False,indent=2)
    load_profile(output,'camera',confirmed=True)
    provenance=dict(kind='limpia_camera_profile_provenance',schema_version=1,camera_index=index,
                    orientation={'A':'exterior','B':'puerta'},orientation_confirmed=True,backend=backend,reference_size=[profile.width,profile.height],reviewer=reviewer,
                    created_at=datetime.now(timezone.utc).isoformat(),frame_storage='not_saved',physical_count_validated=False,
                    warning='Valido solo con el mismo encuadre, orientacion A exterior/B puerta y geometria. Recalibrar al mover la camara.')
    with sidecar.open('x',encoding='utf-8') as stream:json.dump(provenance,stream,ensure_ascii=False,indent=2)
    return output
