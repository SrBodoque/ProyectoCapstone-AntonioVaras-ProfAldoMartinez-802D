"""Bounded presentation mailbox and one sequential processing session per worker."""
from dataclasses import dataclass, replace
import logging
import threading
import time

from .presentation_processing import open_processor
from .presentation_sources import load_profile, open_source, validate_frame
from .video_source import file_sha256
from .presentation_playback import DisplayQueue

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PresentationState:
    frame: object = None
    index: int = -1
    timestamp: float = 0.
    tracks: tuple = ()
    detections: tuple = ()
    entries: int = 0
    exits: int = 0
    last_event: object = None
    status: str = 'Listo para iniciar'
    processing_fps: float = 0.
    delivery_fps: float = 0.
    frames_processed: int = 0
    error: str = ''
    read_ms: float = 0.
    processing_ms: float = 0.
    frame_age_ms: float = 0.
    capture_fps: float = 0.
    capture_frames_skipped: int = 0
    captured_at: float | None = None
    source_fps: float = 0.
    source_frames: int | None = None


class Session:
    def __init__(self, options, *, source_factory=open_source, processor_factory=open_processor,
                 profile_loader=load_profile, display_buffer=False):
        self.options = options
        self.display_buffer = display_buffer
        self.display_queue = DisplayQueue(nominal=options.source=='camera') if self.display_buffer else None
        self.source_factory, self.processor_factory = source_factory, processor_factory
        self.profile_loader = profile_loader
        self.condition = threading.Condition()
        self.state = PresentationState(entries=None, exits=None) if getattr(options, 'tracking_only', False) else PresentationState()
        self.thread = None
        self.stopped = self.paused = False
        self.profile = None
        self.paused_seconds = 0.

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def snapshot(self):
        with self.condition:
            return self.state

    def publish(self, **changes):
        with self.condition:
            self.state = replace(self.state, **changes)
            state = self.state
        if self.display_queue is not None and 'frame' in changes:
            # Do not flash the stale camera startup image after model warmup.
            if self.options.source=='camera' and state.index==0 and state.frame_age_ms>250:
                return
            self.display_queue.put(state)

    def start(self):
        if self.running:
            return False
        if self.display_buffer:
            self.display_queue = DisplayQueue(capacity=4 if self.options.source=='video' else 2, prefill=4 if self.options.source=='video' else 2, nominal=self.options.source=='camera')
        with self.condition:
            self.state = PresentationState(status='Inicializando', entries=None if getattr(self.options, 'tracking_only', False) else 0, exits=None if getattr(self.options, 'tracking_only', False) else 0)
            self.stopped = self.paused = False
            self.paused_seconds = 0.
        self.thread = threading.Thread(target=self._run, name='LimpIA-processing', daemon=False)
        self.thread.start()
        return True

    def stop(self):
        if self.display_queue is not None:
            self.display_queue.cancel()
        with self.condition:
            self.stopped = True
            self.condition.notify_all()

    def toggle_pause(self):
        if self.options.source != 'video' or not self.running:
            return
        with self.condition:
            self.paused = not self.paused
            self.condition.notify_all()

    def _gate(self, delay=0.):
        remaining = max(0., delay)
        with self.condition:
            while not self.stopped:
                if self.paused:
                    self.state = replace(self.state, status='Pausado')
                    pause_started = time.monotonic()
                    self.condition.wait()
                    self.paused_seconds += time.monotonic() - pause_started
                elif remaining > 0:
                    before = time.monotonic()
                    self.condition.wait(timeout=remaining)
                    remaining -= time.monotonic() - before
                else:
                    return True
            return False

    def _run(self):
        try:
            o = self.options
            zones_hash = file_sha256(o.zones) if o.zones.is_file() else None
            self.profile = (None if getattr(o, 'tracking_only', False) else
                            self.profile_loader(o.zones, o.source, o.video, o.confirm_camera_zones))
            # Load the model before opening a camera so the initial frame cannot age during loading.
            with self.processor_factory(o, self.profile) as processor:
                with self.source_factory(o, self.profile) as source:
                    iterator = iter(source)
                    media_origin = wall_origin = None
                    previous = None
                    delivered_at = None
                    while self._gate():
                        try:
                            packet = next(iterator)
                        except StopIteration:
                            if source.status != 'completed':
                                raise RuntimeError(source.reason)
                            break
                        validate_frame(packet.frame, self.profile)
                        before = time.perf_counter()
                        frame_started = time.monotonic()
                        result = processor.update(packet)
                        elapsed = time.perf_counter() - before
                        if media_origin is None:
                            media_origin, wall_origin = packet.timestamp_ms, time.monotonic() - self.paused_seconds
                        if o.source == 'video' and o.realtime and not self.display_buffer:
                            due = wall_origin + (packet.timestamp_ms - media_origin) / 1000 + self.paused_seconds
                            now = time.monotonic()
                            interval = (packet.timestamp_ms - previous)/1000 if previous is not None else 0.
                            if previous is not None and now - due > interval:
                                # A real stall shifts the clock; never fast-forward to repay it.
                                wall_origin += now - due
                                due = now
                            if not self._gate(due - now):
                                break
                        delivery = 1 / (frame_started - delivered_at) if delivered_at is not None and frame_started > delivered_at else 0.
                        self.publish(frame=packet.frame, index=packet.index,
                                     timestamp=packet.timestamp_ms / 1000,
                                     captured_at=source.started_at+packet.timestamp_ms/1000 if hasattr(source, 'started_at') else None,
                                     source_fps=getattr(source, 'metadata', {}).get('reported_fps') or 0.,
                                     source_frames=getattr(source, 'metadata', {}).get('reported_frames'),
                                     tracks=result.tracks, detections=result.detections,
                                     entries=result.entries, exits=result.exits, last_event=result.last_event,
                                     status='Cámara activa' if o.source == 'camera' else 'Reproduciendo video',
                                     capture_frames_skipped=getattr(source, 'frames_skipped', 0),
                                     read_ms=packet.read_ms, processing_ms=elapsed*1000,
                                     frame_age_ms=max(0., (time.monotonic() - source.started_at - packet.timestamp_ms/1000)*1000) if hasattr(source, 'started_at') else 0.,
                                     capture_fps=1000/(packet.timestamp_ms-previous) if o.source=='camera' and previous is not None and packet.timestamp_ms>previous else 0.,
                                     processing_fps=1 / elapsed if elapsed else 0., delivery_fps=delivery,
                                     frames_processed=self.state.frames_processed + 1)
                        previous, delivered_at = packet.timestamp_ms, frame_started
            if self.display_queue is not None:
                self.display_queue.finish()
                self.display_queue.wait_drained()
            if zones_hash is not None and file_sha256(o.zones) != zones_hash:
                raise ValueError('Las zonas cambiaron durante la sesión.')
            self.publish(status='Detenido' if self.stopped else 'Finalizado')
        except Exception as exc:
            LOGGER.exception('Sesión de presentación interrumpida')
            self.publish(status='Error de fuente o procesamiento', error=str(exc))
