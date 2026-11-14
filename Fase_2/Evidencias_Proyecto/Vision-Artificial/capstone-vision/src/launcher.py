"""Unified selection and orchestration. Vision/calibration engines stay unchanged."""
import argparse
import logging
import os
from pathlib import Path
import platform

from .config import PROJECT_ROOT,load_detection_config
from .launcher_calibration import Cancelled,new_output,validate_video,calibrate_video,calibrate_camera
from .launcher_probe import scan_cameras,probe_camera
from .presentation_sources import load_profile

from . import launcher_resources as resources

LOGGER=logging.getLogger(__name__)


def parser():
    p=argparse.ArgumentParser(description='LimpIA - video, camara y calibracion desde un unico lanzador.')
    sources=p.add_mutually_exclusive_group()
    sources.add_argument('--mp4',action='store_true');sources.add_argument('--camara',action='store_true')
    p.add_argument('--calibrar',action='store_true')
    p.add_argument('--video',type=Path);p.add_argument('--zones',type=Path)
    p.add_argument('--camera-index',type=int);p.add_argument('--camera-backend',default='msmf' if platform.system()=='Windows' else 'auto',choices=('auto','msmf','dshow','v4l2','avfoundation'))
    p.add_argument('--camera-limit',type=int,default=5);p.add_argument('--probe-timeout',type=float,default=4.)
    p.add_argument('--frame',type=int);p.add_argument('--output',type=Path);p.add_argument('--reviewer')
    p.add_argument('--tracker',choices=('bytetrack','botsort'));p.add_argument('--device')
    p.add_argument('--weights-dir',type=Path,default=None)
    p.add_argument('--tracking-only',action='store_true');p.add_argument('--confirm-camera-zones',action='store_true')
    return p


def validate_args(args):
    if not 1<=args.camera_limit<=16 or not .1<=args.probe_timeout<=30:raise ValueError('Rango de camaras o timeout invalido.')
    if args.camera_index is not None and not 0<=args.camera_index<2**31:raise ValueError('Indice de camara invalido.')
    if args.frame is not None and args.frame<0:raise ValueError('El frame debe ser no negativo.')
    if args.video and not args.mp4:raise ValueError('--video requiere --mp4.')
    if args.tracking_only and (not args.camara or args.zones or args.calibrar):raise ValueError('--tracking-only requiere --camara sin zonas ni calibracion.')
    if args.output and not args.calibrar:raise ValueError('--output requiere --calibrar.')


class Launcher:
    def __init__(self,ui):self.ui=ui

    def choose_camera(self,args):
        index=args.camera_index
        while True:
            try:
                if index is not None:
                    camera=self.ui.busy(lambda cancel:probe_camera(index,args.camera_backend,args.probe_timeout,cancel),'Comprobando camara')
                else:
                    cameras=self.ui.busy(lambda cancel:scan_cameras(args.camera_limit,args.camera_backend,args.probe_timeout,cancel),'Buscando camaras')
                    if not cameras:raise RuntimeError('No se encontro una camara que entregue imagenes correctamente.')
                    if len(cameras)==1:
                        camera=cameras[0];self.ui.notice(f'Se utilizara camara {camera.index} | {camera.backend} | {camera.width}x{camera.height}')
                    else:
                        selected=self.ui.choose('Seleccionar camara','Camaras que entregaron imagenes validas',[(c.index,f'{c.index} | {c.backend} | {c.width}x{c.height}') for c in cameras])
                        camera=next(c for c in cameras if c.index==selected)
                return camera
            except (RuntimeError,OSError) as exc:
                LOGGER.warning('Camara: %s',exc)
                choice=self.ui.choose('Camara no disponible',str(exc),[('retry','Reintentar deteccion'),('manual','Indice y backend manual'),('video','Cambiar a MP4')])
                if choice=='retry':index=None
                elif choice=='manual':index,args.camera_backend=self.ui.manual_camera(args.camera_backend)
                elif choice=='video':
                    args.camara=False;args.mp4=True;args.tracking_only=False;args.confirm_camera_zones=False;args.zones=None
                    return None

    def calibrate(self,args,video,camera,seed=None,offer_seed=False):
        if offer_seed and seed is None and args.output is None:
            base=self.ui.choose('Base de calibracion','Dibujar zonas nuevas o modificar un perfil existente',[('new','Dibujar zonas nuevas'),('edit','Modificar JSON existente')])
            if base=='edit':
                path=self.ui.open_json()
                seed=load_profile(path,'video' if args.mp4 else 'camera',video,True)
        output=args.output or self.ui.save_json()
        output=new_output(output)
        reviewer=args.reviewer or self.ui.text('Responsable','Nombre de quien revisa la orientacion A exterior / B puerta')
        if not reviewer.strip():raise ValueError('Indique un responsable de la revision.')
        if args.mp4:
            frame=args.frame if args.frame is not None else self.ui.integer('Frame de referencia','Indice desde cero',0)
            return calibrate_video(video,output,frame,reviewer,seed)
        self.ui.notice('Vista previa: Espacio congela una imagen; Esc cancela. Dibuje A exterior y B puerta. Recalibre al cambiar el encuadre.')
        return calibrate_camera(camera.index,args.camera_backend,output,reviewer,seed)

    def prepare(self,args):
        validate_args(args)
        if args.weights_dir is None:args.weights_dir=resources.default_weights()
        camera=None;video=None;profile=None
        review_needed=getattr(args,'review',False) or (args.zones is None and not args.tracking_only)
        if args.camara:
            camera=self.choose_camera(args)
            if camera is not None:args.camera_index=camera.index
        if args.mp4:
            if args.video:video=args.video
            else:
                catalog=self.ui.busy(lambda cancel:resources.videos(),'Buscando videos')
                choice=self.ui.choose('Videos disponibles','Seleccione un video o busque otro archivo',[(str(p),f'{p.name} | {p.parent}') for p in catalog]+[('external','Buscar otro archivo...')])
                video=Path(choice) if choice in [str(p) for p in catalog] else self.ui.open_video()
            video,width,height=self.ui.busy(lambda cancel:validate_video(video),'Comprobando video')
            args.video=video
        zones=args.zones
        if args.calibrar:
            if zones is not None:profile=load_profile(zones,'video' if args.mp4 else 'camera',video,True)
            zones=self.calibrate(args,video,camera,profile,offer_seed=True)
            args.calibrar=False
            if not self.ui.confirm('Perfil guardado',f'{zones.name}\nIniciar ahora el visualizador con este perfil?'):raise Cancelled()
        if zones is None and not args.tracking_only:
            catalog=self.ui.busy(lambda cancel:resources.profiles('video' if args.mp4 else 'camera',video,camera),'Buscando perfiles compatibles')
            choices=[(str(p),f'{name} | {p}') for p,name in catalog]+[('existing','Buscar otro JSON...'),('new','Calibrar nuevas zonas...')]
            if len(catalog)==1:self.ui.notice(f'Perfil compatible predeterminado: {catalog[0][1]}')
            if args.camara:choices.append(('tracking','Solo tracking (conteo deshabilitado)'))
            choice=self.ui.choose('Zonas de transicion','Seleccione o cree un perfil para esta fuente',choices)
            if choice=='existing':zones=self.ui.open_json()
            elif choice=='new':zones=self.calibrate(args,video,camera)
            elif choice=='tracking':args.tracking_only=True
            else:zones=Path(choice)
        if zones is not None:
            while True:
                try:
                    profile=self.ui.busy(lambda cancel:load_profile(zones,'video' if args.mp4 else 'camera',video,True),'Validando perfil')
                    if args.mp4:
                        if (profile.width,profile.height)!=(width,height):raise ValueError('Las dimensiones del video no coinciden con el perfil.')
                    else:
                        profile.check_camera(camera.index,camera.width,camera.height)
                        if (profile.width,profile.height)!=(camera.width,camera.height):raise ValueError('El perfil requiere otra resolucion de camara. Calibre para esta fuente.')
                        if not args.confirm_camera_zones:
                            if not self.ui.confirm('Confirmar encuadre',f'{profile.name} | {profile.width}x{profile.height}\nConfirma misma posicion y orientacion A exterior / B puerta?'):raise Cancelled()
                            args.confirm_camera_zones=True
                    break
                except (ValueError,OSError,RuntimeError) as exc:
                    if args.zones is not None:raise
                    self.ui.error(str(exc))
                    zones=self.ui.open_json()
        from .devices import load_device_preference,validate_device
        if args.device is None:
            args.device=resources.load_preferences().get('device')
            if args.device is None:
                try:args.device=load_device_preference()
                except ValueError:pass
            if args.device is None:
                from .devices import discover_devices,load_torch
                inventory=self.ui.busy(lambda cancel:discover_devices(load_torch()),'Detectando CPU/GPU')
                args.device=next((d.device for d in inventory.devices if d.device=='cuda:0'),'cpu')
        if args.device:
            try:self.ui.busy(lambda cancel:validate_device(args.device),'Comprobando dispositivo')
            except RuntimeError:
                self.ui.notice(f'El dispositivo {args.device} no esta disponible. Elija uno antes de iniciar.')
                args.device=None
        # A single review screen offers tracker/device/weights when any is unspecified.
        if review_needed or args.tracker is None or args.device is None or not resources.valid_weights(args.weights_dir):
            args.tracker,args.device,args.weights_dir=self.ui.settings(args,profile)
        else:
            self.ui.notice(f'Perfil: {profile.name if profile else "Sin calibrar: solo tracking"} | {args.tracker} | {args.device}')
        from .devices import validate_device
        from .tracker_runtime import resolve_resources
        self.ui.busy(lambda cancel:(validate_device(args.device),resolve_resources(args.tracker,args.weights_dir,load_detection_config()['model'])),'Comprobando recursos locales')
        from .view_presentation import parser as presentation_parser
        argv=['--source','video' if args.mp4 else 'camera','--tracker',args.tracker,'--device',args.device,'--weights-dir',str(args.weights_dir)]
        if args.mp4:argv+=['--video',str(video)]
        else:argv+=['--camera-index',str(camera.index),'--camera-backend',args.camera_backend]
        if zones is not None:argv+=['--zones',str(zones)]
        if args.tracking_only:argv+=['--tracking-only']
        if args.confirm_camera_zones:argv+=['--confirm-camera-zones']
        resources.save_preferences(weights_dir=str(args.weights_dir.resolve()),device=args.device,video=str(video) if video else resources.load_preferences().get('video'),zones=str(Path(zones).resolve()) if zones else resources.load_preferences().get('zones'),profile_dirs=list(dict.fromkeys(resources.load_preferences().get('profile_dirs',[])+([str(Path(zones).resolve().parent)] if zones else []))))
        return presentation_parser().parse_args(argv)


def main(argv=None):
    args=parser().parse_args(argv)
    try:validate_args(args)
    except ValueError as exc:parser().error(str(exc))
    import uuid
    directory=PROJECT_ROOT/'logs'/'launcher'
    directory.mkdir(parents=True,exist_ok=True)
    handler=logging.FileHandler(directory/(uuid.uuid4().hex+'.log'),mode='x',encoding='utf-8')
    root_logger=logging.getLogger();previous_level=root_logger.level
    root_logger.addHandler(handler);root_logger.setLevel(logging.INFO)
    from .launcher_ui import TkDialogs
    ui=TkDialogs();controller=Launcher(ui)
    menu=not(args.mp4 or args.camara)
    try:
        while True:
            choosing_menu=not(args.mp4 or args.camara)
            try:
                if choosing_menu:
                    args.review=True
                    action='calibrate' if args.calibrar else ui.menu()
                    if action=='calibrate':
                        source=ui.choose('Calibrar zonas','Elegir fuente',[('video','Video MP4'),('camera','Camara')])
                        args.mp4=source=='video';args.camara=source=='camera';args.calibrar=True
                    else:
                        args.mp4=action=='video';args.camara=action=='camera';args.calibrar=False
                choosing_menu=False
                options=controller.prepare(args)
                failed=ui.run_view(options)
                if not menu and not failed:return 0
            except Cancelled:
                if choosing_menu or not menu:return 0
            except (ValueError,OSError,RuntimeError,ImportError) as exc:
                LOGGER.exception('No se pudo completar el flujo del lanzador')
                ui.error(str(exc))
                if not menu and not args.camara:return 1
            preferences=(args.tracker,args.device,args.weights_dir)
            args=parser().parse_args([])
            args.tracker,args.device,args.weights_dir=preferences
            menu=True
    except Cancelled:return 0
    finally:
        ui.close();root_logger.removeHandler(handler);root_logger.setLevel(previous_level);handler.close()
