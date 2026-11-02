"""Read-only GT readers. No predictions, inference, extraction or source writes."""

import csv
import math
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class Annotation:
    source_frame: int
    frame_index: int
    object_id: str
    bbox_xyxy: tuple | None
    source_class: int | None
    class_label: str | None
    visibility: float | None
    ignored: bool | None
    raw: dict
    transformations: tuple = ()


@dataclass
class AnnotationRead:
    records: list = field(default_factory=list)
    explicit_frames: set = field(default_factory=set)
    errors: list = field(default_factory=list)
    sequence_name: str | None = None


def integer(value):
    n = float(value)
    if not math.isfinite(n) or not n.is_integer():
        raise ValueError(f"Not a finite integer: {value!r}")
    return int(n)


def numbers(values):
    result = tuple(float(v) for v in values)
    if not all(math.isfinite(v) for v in result):
        raise ValueError("Non-finite numeric field")
    return result


def xyxy(values):
    x, y, w, h = numbers(values)
    if w <= 0 or h <= 0:
        raise ValueError("Non-positive bbox extent")
    return x, y, x + w, y + h


def _error(result, line, exc):
    result.errors.append({"line": line, "reason": str(exc)})


def read_mot(text, *, version):
    """MOT17: 9 columns; MOT15: 10, trailing XYZ are NOT class/visibility."""
    if version not in (15, 17):
        raise ValueError("Only MOT15/MOT17 GT is supported")
    result = AnnotationRead()
    for line, fields in enumerate(csv.reader(text.splitlines()), 1):
        if not fields:
            continue
        try:
            if len(fields) != (9 if version == 17 else 10):
                raise ValueError(f"Expected {9 if version == 17 else 10} columns; got {len(fields)}")
            nums = numbers(fields)
            frame, identity, mark = integer(fields[0]), integer(fields[1]), integer(fields[6])
            if frame < 1 or identity < 1 or mark not in (0, 1):
                raise ValueError("Invalid frame, ID or GT mark")
            box = xyxy((nums[2] - 1, nums[3] - 1, nums[4], nums[5]))
            cls = integer(fields[7]) if version == 17 else None
            vis = nums[8] if version == 17 else None
            if version == 17 and (not 1 <= cls <= 13 or not 0 <= vis <= 1):
                raise ValueError("Invalid MOT17 class or visibility")
            result.records.append(Annotation(frame, frame - 1, str(identity), box, cls,
                "person" if version == 15 or cls == 1 else None, vis,
                mark == 0,
                {"columns": fields, "mark": mark, "world_xyz": list(nums[7:10]) if version == 15 else None},
                ("frame_minus_1", "left_top_minus_1", "xywh_to_xyxy",
                 *(["person_from_MOT15_protocol_not_source_class"] if version == 15 else []))))
        except (ValueError, OverflowError) as exc:
            _error(result, line, exc)
    return result


def read_oxford(text):
    """TOP candidate interpretation, retaining head/body validity and raw columns.

    Coordinate-origin convention and body evaluation policy still need verification.
    A short row is reported; it is never padded or silently accepted.
    """
    result = AnnotationRead()
    for line, fields in enumerate(csv.reader(text.splitlines()), 1):
        if not fields:
            continue
        try:
            if len(fields) != 12:
                raise ValueError(f"Expected 12 TOP columns; got {len(fields)}")
            values = numbers(fields)
            identity, frame, head, body = (integer(v) for v in fields[:4])
            if identity < 0 or frame < 0 or head not in (0, 1) or body not in (0, 1):
                raise ValueError("Invalid TOP ID/frame/validity flag")
            if head and (values[6] <= values[4] or values[7] <= values[5]):
                raise ValueError("Invalid TOP head bbox")
            box = tuple(values[8:12]) if body else None
            if box and (box[2] <= box[0] or box[3] <= box[1]):
                raise ValueError("Invalid TOP body bbox")
            result.records.append(Annotation(frame, frame, str(identity), box, None, "person", None,
                not bool(body), {"columns": fields, "head_valid": head, "body_valid": body,
                "head_xyxy": list(values[4:8]), "coordinate_origin_verified": False},
                ("TOP_body_columns_candidate", "person_from_dataset_protocol")))
        except (ValueError, OverflowError) as exc:
            _error(result, line, exc)
    return result


def read_caviar(text):
    """Only individual objects. Group boxes are deliberately not detections."""
    result = AnnotationRead()
    # Reject entities/DTDs instead of resolving resources or expanding entity data.
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise ValueError("DTD/entities are not supported")
    root = ET.fromstring(text)
    if root.tag != "dataset":
        raise ValueError("Expected CAVIAR dataset element")
    result.sequence_name = root.get("name")
    for node in root.findall("frame"):
        try:
            frame = integer(node.attrib["number"])
            if frame < 0 or frame in result.explicit_frames:
                raise ValueError("Negative or duplicate XML frame")
            if node.find('objectlist') is None:
                raise ValueError("Missing XML objectlist; cannot certify empty frame")
            result.explicit_frames.add(frame)
        except (KeyError, ValueError, OverflowError) as exc:
            _error(result, node.get("number"), exc)
            continue
        for obj in node.findall("./objectlist/object"):
            try:
                identity = integer(obj.attrib["id"])
                if identity < 0:
                    raise ValueError("Negative CAVIAR ID")
                box = obj.find("box")
                if box is None:
                    raise ValueError("Missing individual box")
                xc, yc, w, h = numbers([box.attrib[k] for k in ("xc", "yc", "w", "h")])
                roles = sorted({a.text for a in obj.findall("./hypothesislist/hypothesis/role") if a.text})
                appearance = obj.findtext("appearance")
                # 'occluded' is categorical, not a visibility ratio.
                result.records.append(Annotation(frame, frame, str(identity),
                    xyxy((xc - w / 2, yc - h / 2, w, h)), None,
                    "person" if roles == ["walker"] else None, None, None,
                    {"id": obj.attrib["id"], "box": dict(box.attrib), "roles": roles,
                     "appearance": appearance, "coordinate_origin_verified": False},
                    ("center_wh_to_xyxy", "walker_to_person_if_applicable")))
            except (KeyError, ValueError, OverflowError) as exc:
                _error(result, frame, exc)
    return result


def scale_annotation(record, sx, sy):
    """Explicit candidate scale; caller must verify image registration first."""
    sx, sy = numbers((sx, sy))
    if sx <= 0 or sy <= 0:
        raise ValueError("Scale must be positive")
    b = record.bbox_xyxy
    return replace(record, bbox_xyxy=(b[0]*sx, b[1]*sy, b[2]*sx, b[3]*sy) if b else None,
                   transformations=record.transformations + (f"scale_candidate:{sx},{sy}",))


def ranges(values):
    """Inclusive integer ranges; stable order, including explicit empty result."""
    result = []
    for n in sorted(set(values)):
        if result and n == result[-1][1] + 1:
            result[-1][1] = n
        else:
            result.append([n, n])
    return result


def summarize(parsed, expected_frames=None, dimensions=None):
    rows = parsed.records
    frames = {r.frame_index for r in rows}
    counts = Counter((r.frame_index, r.object_id) for r in rows)
    classes = Counter(str(r.source_class) if r.source_class is not None else "absent" for r in rows)
    missing = set(range(expected_frames)) - frames if expected_frames is not None else set()
    explicit_missing = set(range(expected_frames)) - parsed.explicit_frames if expected_frames is not None else set()
    outside = 0
    if dimensions:
        w, h = dimensions
        outside = sum(bool(r.bbox_xyxy and (r.bbox_xyxy[0] < 0 or r.bbox_xyxy[1] < 0 or
            r.bbox_xyxy[2] > w or r.bbox_xyxy[3] > h)) for r in rows)
    by_id = {}
    for r in rows:
        by_id.setdefault(r.object_id, set()).add(r.frame_index)
    gaps = 0
    for fs in by_id.values():
        ordered = sorted(fs)
        gaps += sum(b > a+1 for a, b in zip(ordered, ordered[1:]))
    return {"valid_rows": len(rows), "invalid_rows": len(parsed.errors),
        "errors": parsed.errors[:20], "unique_ids": len(by_id),
        "source_frame_min": min((r.source_frame for r in rows), default=None),
        "source_frame_max": max((r.source_frame for r in rows), default=None),
        "duplicate_frame_id_pairs": sum(c - 1 for c in counts.values()),
        "source_classes": dict(sorted(classes.items())),
        "active_person_rows": sum(r.class_label == "person" and r.ignored is False for r in rows),
        "ignored_rows": sum(r.ignored is True for r in rows),
        "non_person_target_rows": sum(r.class_label != "person" for r in rows),
        "ignore_policy_unknown_rows": sum(r.ignored is None for r in rows),
        "visibility_unknown_rows": sum(r.visibility is None for r in rows),
        "bbox_outside_image_rows": outside,
        "frames_with_any_valid_rows": len(frames), "frames_without_rows_ranges": ranges(missing),
        "frames_outside_expected_ranges": ranges(f for f in frames if expected_frames is not None and not 0 <= f < expected_frames),
        "explicit_xml_frames": len(parsed.explicit_frames),
        "missing_explicit_xml_frame_ranges": ranges(explicit_missing) if parsed.sequence_name is not None else None,
        "explicit_empty_xml_frame_ranges": ranges(parsed.explicit_frames - frames),
        "identity_gap_count": gaps,
        "coverage_caveat": "Missing row != verified negative frame; gaps may be legitimate occlusions.",
        "examples": [{"source_frame": r.source_frame, "frame_index": r.frame_index,
            "object_id": r.object_id, "bbox_xyxy": r.bbox_xyxy, "source_class": r.source_class,
            "class_label": r.class_label, "visibility": r.visibility, "ignored": r.ignored,
            "raw": r.raw, "transformations": r.transformations} for r in rows[:2]]}
