"""Superposiciones offline sobre copias de frames. Sin modelos ni GUI."""

import colorsys
from collections import deque


class TrailHistory:
    """Puntos de observaciones guardadas; no asocia detecciones ni recupera IDs."""

    def __init__(self, frames=30):
        if type(frames) is not int or not 1 <= frames <= 300:
            raise ValueError("trail_frames debe estar entre 1 y 300.")
        self.frames = frames
        self.points = {}
        self.last_index = None

    def update(self, saved):
        if not saved.available or (self.last_index is not None and saved.index != self.last_index + 1):
            self.points.clear()
        self.last_index = saved.index
        threshold = saved.index - self.frames + 1
        for identifier, points in tuple(self.points.items()):
            while points and points[0][0] < threshold:
                points.popleft()
            if not points:
                del self.points[identifier]
        for item in saved.tracks:
            self.points.setdefault(item.track_id, deque(maxlen=self.frames)).append((saved.index, item.center))


def track_color(identifier):
    red, green, blue = colorsys.hsv_to_rgb((identifier * .61803398875) % 1, .75, 1)
    return (round(blue * 255), round(green * 255), round(red * 255))


def _label(cv2, frame, text, point, scale=.5):
    cv2.putText(frame, text, point, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(frame, text, point, cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 1, cv2.LINE_AA)


def render_frame(cv2, frame, saved, history, *, total=None, timestamp_ms=None,
                 paused=False, overlays=()):
    """overlays permite futuras capas sin acoplar zonas/eventos al reproductor."""
    output = frame.copy()
    height, width = output.shape[:2]
    def clip(point):
        return tuple(round(max(0, min(limit - 1, value)))
                     for value, limit in zip(point, (width, height)))
    for item in (*saved.tracks, *saved.detections, *saved.untracked):
        first, last = clip((item.x1, item.y1)), clip((item.x2, item.y2))
        if first[0] >= last[0] or first[1] >= last[1]:
            continue
        identifier = item.track_id
        color = track_color(identifier) if identifier is not None else (0, 180, 255)
        cv2.rectangle(output, first, last, color, 2)
        label = f"ID {identifier}" if identifier is not None else "person | sin ID"
        if item.confidence is not None:
            label += f" | {item.confidence:.2f}"
        _label(cv2, output, label, (first[0], min(height - 1, max(14, first[1] - 5))))
        points = list(history.points.get(identifier, ())) if identifier is not None else []
        for (a_index, a), (b_index, b) in zip(points, points[1:]):
            if b_index == a_index + 1:
                cv2.line(output, clip(a), clip(b), color, 2)
    time_text = f"{timestamp_ms / 1000:.3f}s" if timestamp_ms is not None else "N/D"
    total_text = str(total) if total is not None else "?"
    _label(cv2, output, f"Frame {saved.index + 1}/{total_text} | t={time_text} | tracks: {len(saved.tracks)}", (8, 20))
    _label(cv2, output, f"{'PAUSA' if paused else 'REPRODUCIENDO'} | Espacio: pausa | n / .: siguiente | q / ESC: salir", (8, 42), .45)
    if not saved.available:
        _label(cv2, output, "SIN PREDICCION REGISTRADA PARA ESTE FRAME", (8, 64))
    for overlay in overlays:
        overlay(cv2, output, saved)
    return output
