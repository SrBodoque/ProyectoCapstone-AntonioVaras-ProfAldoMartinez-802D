"""Unified local sources. Captures stay owned by the processing worker."""
from contextlib import contextmanager
import time
import threading
from queue import Queue, Full, Empty
from pathlib import Path

from .camera import camera_session, backend_candidates, camera_info
from .count_orientation import profile_hash
from .saved_results import read_json
from .video_source import VideoSource, FramePacket, discover_cases, file_sha256
from .video_zones import load_video_zones
from .zones import ZoneProfile


def load_profile(path, source, video=None, confirmed=False):
    if source == 'video':
        return load_video_zones(path, video).profile
    if not confirmed:
        raise ValueError('Confirme encuadre y orientación A exterior / B puerta con --confirm-camera-zones; calibre si la cámara cambió de posición.')
    path = Path(path)
    if path.stat().st_size > 262144:
        raise ValueError('Perfil de zonas demasiado grande.')
    data = read_json(path.read_text(encoding='utf-8-sig'), 'zonas de cámara')
    if isinstance(data, dict) and data.get('kind') == 'limpia_video_zones':
        profile = ZoneProfile.from_dict(data['profile'])
        if (data.get('schema_version') != 1 or data.get('orientation_confirmed') is not True
                or data.get('orientation') != {'A': 'exterior', 'B': 'puerta'}
                or data.get('profile_sha256') != profile_hash(profile)):
            raise ValueError('Perfil de referencia sin orientación o integridad válida.')
        return profile
    return ZoneProfile.from_dict(data)


def validate_frame(frame, profile):
    if (frame is None or frame.size == 0 or len(frame.shape) != 3 or frame.shape[2] != 3):
        raise ValueError('La fuente no entregó una imagen BGR válida.')
    if profile is not None and frame.shape[:2] != (profile.height, profile.width):
        raise ValueError(f'Resolución incompatible: se requiere {profile.width}×{profile.height}. Seleccione o calibre un perfil para esta fuente; no se escalan zonas automáticamente.')


@contextmanager
def native_camera_session(config):
    """Reuse backend selection, without issuing CAP_PROP_FPS to the driver.

    The protected camera_session always sets FPS; this additive adapter keeps it
    intact while preserving the source rate requested for the presentation UI.
    """
    import cv2
    failures = []
    for name, api in backend_candidates(config['backend']):
        capture = cv2.VideoCapture()
        try:
            if not capture.open(config['camera_index'], api) or not capture.isOpened():
                raise RuntimeError('No se pudo abrir la camara.')
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, config['width'])
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config['height'])
            ok, first = capture.read()
            if not ok or first is None or first.size == 0:
                raise RuntimeError('La camara no entrego el primer frame.')
        except Exception as exc:
            capture.release()
            failures.append(f'{name}: {exc}')
            continue
        try:
            yield capture, first
        finally:
            capture.release()
        return
    raise RuntimeError('Camara indisponible: ' + '; '.join(failures))


class CameraFrames:
    """Capture independently of inference, bounded FIFO, never silently skip count frames."""
    def __init__(self, capture, first, clock=time.monotonic, latest_only=False):
        self.capture, self.first, self.clock = capture, first, clock
        self.status = 'running'
        self.reason = ''
        self.metadata = {'reported_fps': None}
        self.latest_only = latest_only
        self.frames_skipped = 0
        self.pending = Queue(maxsize=1 if latest_only else 8)
        self.stop_event = threading.Event()
        self.finished = threading.Event()
        self.thread = None
        self.error = None

    def _capture(self, start, previous):
        index = 1
        try:
            while not self.stop_event.is_set():
                before = self.clock()
                ok, frame = self.capture.read()
                now = self.clock()
                if not ok:
                    raise RuntimeError('La cámara dejó de entregar imágenes. Revise conexión y permisos.')
                timestamp = max(now - start, previous + 1e-9)
                previous = timestamp
                packet = FramePacket(index, timestamp * 1000, 'monotonic/capture-read', frame, (now-before)*1000)
                try:
                    self.pending.put_nowait(packet)
                except Full:
                    if not self.latest_only:
                        raise RuntimeError('Captura supera al procesamiento: cola de 8 frames llena. Sesion detenida sin descartar frames silenciosamente; revise dispositivo y FPS de captura.')
                    try:
                        self.pending.get_nowait()
                        self.frames_skipped += 1
                    except Empty:
                        pass
                    self.pending.put_nowait(packet)
                index += 1
        except Exception as exc:
            self.error = exc
        finally:
            self.finished.set()

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
            if self.thread.is_alive():
                # The owner releases the driver after this signal; no UI thread waits here.
                self.capture.release()
                self.thread.join(timeout=2)
                if self.thread.is_alive():
                    raise RuntimeError('El driver no libero la lectura de camara.')

    def __iter__(self):
        start = self.clock()
        self.started_at = start
        timestamp = max(0., self.clock() - start)
        try:
            yield FramePacket(0, timestamp*1000, 'monotonic/capture-read', self.first, 0.)
            self.thread = threading.Thread(target=self._capture, args=(start,timestamp),
                                           name='LimpIA-capture', daemon=True)
            self.thread.start()
            while not self.stop_event.is_set():
                try:
                    yield self.pending.get(timeout=.05)
                except Empty:
                    if self.finished.is_set():
                        if self.error:
                            raise self.error
                        return
        finally:
            self.close()


@contextmanager
def open_source(options, profile):
    if options.source == 'video':
        case = discover_cases(video=options.video)[0]
        with VideoSource(case.path) as source:
            yield source
        if file_sha256(case.path) != case.sha256:
            raise ValueError('El MP4 cambió durante la sesión.')
    else:
        from .config import load_config
        if profile is not None:
            profile.check_camera(options.camera_index, profile.width, profile.height)
        config = load_config()
        config = {**config, 'camera_index': options.camera_index,
                  'width': profile.width if profile else config['width'],
                  'height': profile.height if profile else config['height'],
                  'backend': options.camera_backend or config['backend']}
        with native_camera_session(config) as (capture, first):
            source = CameraFrames(capture, first, latest_only=getattr(options, 'tracking_only', False))
            source.metadata['reported_fps'] = camera_info(capture)['fps']
            try:
                yield source
            finally:
                source.close()
