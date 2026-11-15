"""Adapters around the protected tracker and A/B counter; no new inference logic."""
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .count_engine import Observation, TransitionCounter
from .counting_config import load_counting_config
from .presentation_sources import validate_frame


@dataclass(frozen=True)
class ProcessedFrame:
    tracks: tuple
    detections: tuple
    entries: int
    exits: int
    last_event: object


class CountAdapter:
    def __init__(self, profile, process, settings=None, timestamps=None):
        self.profile, self.process = profile, process
        self.counter = TransitionCounter(profile, settings or load_counting_config().thresholds)
        self.last_event = None
        self.timestamps = timestamps

    def update(self, packet):
        validate_frame(packet.frame, self.profile)
        result = self.process(packet)
        if packet.timestamp_ms is None:
            raise ValueError('La fuente carece de timestamps fiables; se detiene el conteo.')
        observations = [Observation(t.track_id, ((t.x1 / 2 + t.x2 / 2) / self.profile.width,
                                               t.y2 / self.profile.height)) for t in result.tracks]
        timestamp = self.timestamps[packet.index] if self.timestamps is not None else packet.timestamp_ms / 1000
        events = self.counter.update(timestamp, observations)
        if events:
            self.last_event = events[-1]
        detections = getattr(result, 'untracked_detections', getattr(result, 'untracked', ()))
        return ProcessedFrame(result.tracks, detections, self.counter.total_entries,
                              self.counter.total_exits, self.last_event)


class TrackingAdapter:
    """Uncalibrated camera diagnostics: deliberately no occupancy or count."""
    def __init__(self, process):
        self.process = process

    def update(self, packet):
        result = self.process(packet.frame)
        return ProcessedFrame(result.tracks, result.untracked_detections, None, None, None)


@contextmanager
def open_processor(options, profile):
    if options.predictions:
        from .count_replay import validate_case, _timeline
        from .saved_results import select_case
        from .video_zones import load_video_zones
        from .video_source import file_sha256
        video, case = select_case(options.predictions, options.video)
        zones = load_video_zones(options.zones, video)
        validate_case(case, zones)
        config = case.metadata.get('configuration') or {}
        if config.get('tracker_name') != options.tracker:
            raise ValueError('El tracker guardado no coincide con --tracker.')
        paths = [case.directory / n for n in ('metadata.json', 'predictions.jsonl')]
        hashes = {p: file_sha256(p) for p in paths}
        def replay(packet):
            if packet.index not in case.frames:
                raise ValueError('Faltan predicciones para un frame; no se inventan detecciones.')
            return case.frames[packet.index]
        adapter = CountAdapter(profile, replay, timestamps=tuple(_timeline(case)[0]))
        yield adapter
        if any(file_sha256(p) != digest for p, digest in hashes.items()):
            raise ValueError('Las predicciones cambiaron durante la reproducción.')
        return
    from .video_runner import RunOptions, prepare_runtime
    from .tracker import PersonTracker
    from .tracker_runtime import local_processing
    prepared = prepare_runtime(RunOptions('tracking', options.device, options.tracker, str(options.weights_dir)))
    files = [w['path'] for w in prepared.weights]
    if options.video:
        files.append(Path(options.video))
    with local_processing(files):
        tracker = PersonTracker(prepared.detection, prepared.tracking,
                                device_override=options.device,
                                experimental_botsort=prepared.experimental_botsort)
        if (tracker.device_resolution.effective_device != options.device
                or tracker.device_resolution.fallback):
            raise RuntimeError('El dispositivo efectivo difiere del solicitado; sesión cancelada.')
        try:
            if getattr(options, 'tracking_only', False):
                yield TrackingAdapter(tracker.track)
            else:
                yield CountAdapter(profile, lambda packet: tracker.track(packet.frame))
        finally:
            tracker = None
