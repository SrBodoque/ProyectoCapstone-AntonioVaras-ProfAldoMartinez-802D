"""Portable, read-only review contracts for the three audited MOT recordings."""

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path, PurePosixPath, PureWindowsPath

from .dataset_audit import annotations
from .dataset_annotations import scale_annotation, summarize
from .video_source import VideoSource, file_sha256

SUPPORTED = {'PETS09-S2L1': 'mot15', 'MOT17-02': 'mot17', 'MOT17-04': 'mot17'}
OFFSETS = (-2, -1, 0, 1, 2)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def read_json(path):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError(f'Duplicate JSON key: {k}')
            result[k] = v
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique,
                      parse_constant=lambda v: (_ for _ in ()).throw(ValueError(f'Invalid JSON number: {v}')))


def relative_file(root, value):
    """Resolve portable POSIX paths, never a legacy personal dataset_root."""
    if not isinstance(value, str) or not value or '\\' in value:
        raise ValueError('Expected a nonempty relative POSIX path')
    p = PurePosixPath(value)
    if p.is_absolute() or PureWindowsPath(value).drive or any(x in ('.', '..') for x in value.split('/')):
        raise ValueError('Absolute/traversing paths are forbidden')
    root = Path(root).resolve()
    target = root.joinpath(*p.parts)
    current = root
    for part in p.parts:
        current = current / part
        if current.is_symlink() or current.is_junction():
            raise ValueError('Linked input paths are unsupported')
    if not target.resolve().is_relative_to(root) or not target.is_file():
        raise ValueError(f'Missing or escaped input: {value}')
    return target


def new_output(path, datasets):
    p, root = Path(path).resolve(), Path(datasets).resolve()
    if p.is_relative_to(root) or root.is_relative_to(p):
        raise ValueError('Output must be outside and not an ancestor of datasets')
    if p.exists():
        raise FileExistsError(f'Output already exists: {p}')
    return p


def write_new_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2) + '\n')


def policy(kind):
    """Versioned proposal, not execution of matching/preprocessing or metrics."""
    if kind not in ('mot15', 'mot17'):
        raise ValueError('Unsupported review protocol')
    return {
        'id': f'limpia-{kind}-review-v1', 'target': 'person',
        'source_person_class': 1 if kind == 'mot17' else None,
        'target_rule': 'mark!=0 and class==1' if kind == 'mot17' else 'mark!=0; person derived from MOT15 protocol',
        'zero_marked_gt': 'not scored as target; not a universal suppression mask',
        'distractor_classes': [2, 7, 8, 12] if kind == 'mot17' else [],
        'future_distractor_preprocessing': 'one-to-one match against all GT at IoU>=0.5; discard predictions assigned to distractor classes' if kind == 'mot17' else 'none (MOT15 profile)',
        'other_classes': 'retain raw; not targets and not universal ignore regions',
        'crowd_ignore_regions': [], 'add_manual_regions': False,
        'visibility_filter': 'none; keep original fractions or null; never invent visibility',
        'body_geometry': 'amodal source extents retained; clipping only when drawing',
        'source': 'https://github.com/JonathonLuiten/TrackEval/blob/master/trackeval/datasets/mot_challenge_2d_box.py',
        'implementation_scope': 'classification/display only; evaluator preprocessing is future 2B',
    }


def role(record, kind):
    # Preserve mark separately: a distractor can also have mark=0.
    if kind == 'mot17' and record.source_class in (2, 7, 8, 12):
        return 'distractor'
    if kind == 'mot17' and record.source_class != 1:
        return 'other_class'
    if record.raw['mark'] == 0:
        return 'ignored_mark0'
    if kind == 'mot15' or record.source_class == 1:
        return 'active_person'
    return 'other_class'


def spatial_transform(source_dimensions, video_dimensions):
    return {'source_origin': 1, 'normalised_origin': 0, 'source_box': 'xywh',
        'target_box': 'xyxy', 'scale': [video_dimensions[0]/source_dimensions[0], video_dimensions[1]/source_dimensions[1]],
        'translation_px': [0.0, 0.0], 'crop': 'none', 'clipping': 'display_only',
        'formula': '(source_left_or_top - 1) * scale + translation; extent * scale'}


def validate_transform(transform):
    keys = set(spatial_transform([1, 1], [1, 1]))
    if not isinstance(transform, dict) or set(transform) != keys:
        raise ValueError('Unexpected spatial transform schema')
    fixed = spatial_transform([1, 1], [1, 1])
    if any(transform[k] != fixed[k] for k in keys - {'scale', 'translation_px'}):
        raise ValueError('Unsupported coordinate/crop/clipping convention')
    for key in ('scale', 'translation_px'):
        v = transform[key]
        if not isinstance(v, list) or len(v) != 2 or any(type(n) not in (int, float) or not math.isfinite(n) for n in v):
            raise ValueError('Transform must have two finite numeric values per axis')
    if min(transform['scale']) <= 0:
        raise ValueError('Scale must be positive')


def transform_record(record, transform):
    validate_transform(transform)
    r = scale_annotation(record, *transform['scale'])
    if r.bbox_xyxy is None:
        return None
    x0, y0, x1, y1 = r.bbox_xyxy
    dx, dy = transform['translation_px']
    return [x0+dx, y0+dy, x1+dx, y1+dy]


def gt_index(video_index, offset):
    if type(video_index) is not int or type(offset) is not int or offset not in OFFSETS:
        raise ValueError('Integer video index and offset in [-2,2] required')
    return video_index + offset


def evaluable_interval(frame_count, offset):
    gt_index(0, offset)
    if type(frame_count) is not int or frame_count < 5:
        raise ValueError('At least five frames required')
    return [max(0, -offset), min(frame_count-1, frame_count-1-offset)]


def load_sequence(manifest_path, datasets, sequence_id, transform=None):
    """Only rehash the requested inputs; no full audit and no Oxford/CAVIAR reads."""
    if sequence_id not in SUPPORTED:
        raise ValueError('Review is limited to PETS09-S2L1/MOT17-02/MOT17-04')
    manifest = read_json(manifest_path)
    if manifest.get('schema_version') != 1:
        raise ValueError('Unsupported audit schema')
    rows = [c for c in manifest['sequences'] if c['id'] == sequence_id]
    if len(rows) != 1 or rows[0]['kind'] != SUPPORTED[sequence_id]:
        raise ValueError('Missing/duplicate or incompatible audited sequence')
    item = rows[0]
    root = Path(datasets).resolve()
    vp, ap = item['video_path'], item['annotations']['path']
    video, annotation = relative_file(root, vp), relative_file(root, ap)
    expected_v = manifest['input_inventory'][vp]['sha256']
    expected_a = manifest['input_inventory'][ap]['sha256']
    if file_sha256(video) != expected_v or file_sha256(annotation) != expected_a:
        raise ValueError('Video/annotation hash differs from audit')
    parsed, details = annotations(root, item['kind'], item['original_sequence'])
    if details['path'] != ap or details['selected_member'] != item['annotations']['selected_member']:
        raise ValueError('Annotation source location changed')
    if not details['variant_ground_truth_identical']:
        raise ValueError('Detector variants do not share identical GT')
    if details['variants'] != item['annotations']['variants']:
        raise ValueError('GT/seqinfo variants differ from audit')
    v = item['video']
    count = v['decoded_frames']
    if (type(count) is not int or count < 5 or v['decode_status'] != 'completed'
            or count != details['expected_frames'] or not math.isclose(v['reported_fps'], details['expected_fps'], rel_tol=1e-6)):
        raise ValueError('Incomplete/inconsistent audited video metadata')
    summary = summarize(parsed, count, details['annotation_dimensions'])
    if summary['invalid_rows'] or summary['duplicate_frame_id_pairs'] or summary['frames_outside_expected_ranges'] or summary['frames_without_rows_ranges']:
        raise ValueError('Incomplete/invalid GT; review cannot approve this sequence')
    shape = [int(v['width']), int(v['height'])]
    if transform is None:
        transform = spatial_transform(details['annotation_dimensions'], shape)
    validate_transform(transform)
    implementation = {name: file_sha256(Path(__file__).parent/name) for name in (
        'dataset_review.py', 'dataset_approval.py', 'view_ground_truth.py', 'ground_truth_review.html',
        'dataset_annotations.py', 'dataset_audit.py', 'video_source.py')}
    context = {'schema_version': 1, 'sequence_id': sequence_id, 'kind': item['kind'],
        'implementation_sha256': implementation,
        'recording_group': item['original_sequence'],
        'video': {'path': vp, 'sha256': expected_v, 'dimensions': shape, 'frames': count, 'fps': v['reported_fps']},
        'annotations': {'path': ap, 'sha256': expected_a, 'member': details['selected_member'],
                        'member_sha256': details['variants'][0]['sha256'], 'dimensions': details['annotation_dimensions']},
        'spatial_transform': transform, 'policy': policy(item['kind']),
        'temporal_convention': 'GT zero-based index = decoded video index + offset; source frame = GT index + 1',
        'offset_candidates': list(OFFSETS)}
    if file_sha256(video) != expected_v or file_sha256(annotation) != expected_a:
        raise ValueError('Inputs changed while loading GT')
    return context, parsed.records


def select_frames(records, count):
    """Select representative frames plus neighborhoods of geometric overlap candidates.

    This is GT geometry sampling, never detector inference or a certified occlusion label.
    """
    reasons = defaultdict(set)
    for i in [0, 1, 2, count//4, count//2, 3*count//4, count-3, count-2, count-1]:
        reasons[i].add('start/middle/end_or_quartile')
    by_frame = defaultdict(list)
    for r in records:
        if r.class_label == 'person' and r.raw['mark'] != 0 and r.bbox_xyxy:
            by_frame[r.frame_index].append(r.bbox_xyxy)
    scores = []
    for i, boxes in by_frame.items():
        score = 0.0
        for a_index, a in enumerate(boxes):
            for b in boxes[a_index+1:]:
                area = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
                smaller = min((a[2]-a[0])*(a[3]-a[1]), (b[2]-b[0])*(b[3]-b[1]))
                score = max(score, area/smaller if smaller else 0)
        if score > 0:
            scores.append((score, i))
    chosen = []
    for _, i in sorted(scores, key=lambda p: (-p[0], p[1])):
        if 2 <= i < count-2 and all(abs(i-j) >= max(5, count//8) for j in chosen):
            chosen.append(i)
            for k in range(i-2, i+3):
                reasons[k].add('geometric_overlap_candidate_neighborhood')
            if len(chosen) == 2:
                break
    return [{'video_index': i, 'reasons': sorted(v)} for i, v in sorted(reasons.items())]


def decode_frames(path, indices, expected_dimensions):
    """Exact sequential decode indices, no seeking by seconds or approximate frame seek."""
    indices = set(indices)
    if not indices or any(type(i) is not int or i < 0 for i in indices):
        raise ValueError('Nonnegative selected indices required')
    result = {}
    with VideoSource(Path(path)) as source:
        for packet in source:
            if packet.index in indices:
                if list(packet.frame.shape[:2][::-1]) != expected_dimensions:
                    raise ValueError('Decoded dimensions differ from audit')
                result[packet.index] = packet.frame
                if len(result) == len(indices):
                    break
    if set(result) != indices:
        raise ValueError('Could not decode all selected frames')
    return result


def frame_boxes(records_by_frame, video_index, offset, context):
    i = gt_index(video_index, offset)
    if not 0 <= i < context['video']['frames']:
        return {'gt_index': i, 'source_frame': i+1, 'in_domain': False, 'boxes': []}
    boxes = []
    for r in records_by_frame.get(i, []):
        boxes.append({'id': r.object_id, 'source_frame': r.source_frame,
            'xyxy': transform_record(r, context['spatial_transform']), 'role': role(r, context['kind']),
            'mark': r.raw['mark'], 'class': r.source_class, 'visibility': r.visibility,
            'source_xywh': r.raw['columns'][2:6]})
    return {'gt_index': i, 'source_frame': i+1, 'in_domain': True, 'boxes': boxes}
