"""Independent GT viewer and local evidence export. No model or tracker imports."""

import argparse
import base64
from collections import defaultdict
from pathlib import Path

from .dataset_review import (SUPPORTED, OFFSETS, canonical, decode_frames, digest,
    frame_boxes, load_sequence, new_output, read_json, relative_file, select_frames, write_new_json)
from .video_source import file_sha256

COLORS = {'active_person': (80, 240, 80), 'ignored_mark0': (0, 180, 255),
          'distractor': (255, 200, 0), 'other_class': (170, 170, 170)}


def group_records(records):
    result = defaultdict(list)
    for r in records:
        result[r.frame_index].append(r)
    return result


def render_frame(frame, info, context, offset, *, include_other=False):
    """Display clipping affects only pixels; source extents remain untouched."""
    import cv2
    import numpy as np
    image = frame.copy()
    height, width = image.shape[:2]
    for b in info['boxes']:
        if b['role'] == 'other_class' and not include_other:
            continue
        x0, y0, x1, y1 = b['xyxy']
        color = COLORS[b['role']]
        # Draw on the image canvas only. Clamp graphics coordinates, never data.
        xa, ya, xb, yb = [int(round(v)) for v in (max(0, min(width-1, x0)), max(0, min(height-1, y0)),
                                                max(0, min(width-1, x1)), max(0, min(height-1, y1)))]
        if x1 <= 0 or y1 <= 0 or x0 >= width or y0 >= height:
            continue
        cv2.rectangle(image, (xa, ya), (xb, yb), color, 1 if b['mark'] == 0 else 2)
        label = f"ID {b['id']} c={b['class']} m={b['mark']}"
        cv2.putText(image, label, (xa, max(13, ya-3)), cv2.FONT_HERSHEY_SIMPLEX, .34, color, 1, cv2.LINE_AA)
    header = np.zeros((108, width, 3), dtype=np.uint8)
    scale = context['spatial_transform']['scale']
    shift = context['spatial_transform']['translation_px']
    lines = [f"{context['sequence_id']} | VIDEO index {info['gt_index']-offset} | offset {offset:+d}",
             f"GT index {info['gt_index']} | source frame {info['source_frame']} | GT = video + offset",
             f"origin MOT 1 -> 0; scale {scale}; translation {shift}; crop none; display clip only",
             'GREEN person | ORANGE ignored person | CYAN distractor | GRAY other (toggle)',
             'PENDING HUMAN REVIEW' if info['in_domain'] else 'OUTSIDE GT DOMAIN - NOT A NEGATIVE FRAME']
    for j, text in enumerate(lines):
        cv2.putText(header, text, (8, 18+j*20), cv2.FONT_HERSHEY_SIMPLEX, .40, (255, 255, 255), 1, cv2.LINE_AA)
    return np.vstack((header, image))


def prepare(manifest, datasets, sequence, output, *, transform=None, extra_frames=()):
    """Create a fresh self-contained HTML packet, contact sheet and pending template."""
    import cv2
    context, records = load_sequence(manifest, datasets, sequence, transform)
    selected = select_frames(records, context['video']['frames'])
    reasons = {r['video_index']: r['reasons'] for r in selected}
    for i in extra_frames:
        if type(i) is not int or not 0 <= i < context['video']['frames']:
            raise ValueError('Extra review frame outside video')
        reasons.setdefault(i, []).append('user_selected')
    selected = [{'video_index': i, 'reasons': sorted(set(v))} for i, v in sorted(reasons.items())]
    output = new_output(output, datasets)
    frames = decode_frames(relative_file(datasets, context['video']['path']), reasons, context['video']['dimensions'])
    by_frame = group_records(records)
    payload = {'context': context, 'context_sha256': digest(context), 'selected_frames': selected, 'frames': {}}
    for i, image in frames.items():
        ok, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 94])
        if not ok:
            raise RuntimeError('Could not encode review image')
        payload['frames'][str(i)] = {'image': 'data:image/jpeg;base64,' + base64.b64encode(encoded).decode('ascii'),
            'offsets': {str(o): frame_boxes(by_frame, i, o, context) for o in OFFSETS}}
    html = (Path(__file__).parent/'ground_truth_review.html').read_text(encoding='utf-8')
    # JSON is data in a script, never executable source from XML/paths.
    embedded = canonical(payload).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    html = html.replace('__REVIEW_DATA__', embedded)
    event = next((s['video_index'] for s in selected if 'geometric_overlap_candidate_neighborhood' in s['reasons']
                  and 2 <= s['video_index'] < context['video']['frames']-2), context['video']['frames']//2)
    import numpy as np
    panels = []
    for o in OFFSETS:
        panel = render_frame(frames[event], frame_boxes(by_frame, event, o, context), context, o)
        panels.append(cv2.resize(panel, (768, round(panel.shape[0]*768/panel.shape[1]))))
    contact = np.vstack(panels)
    ok, encoded = cv2.imencode('.jpg', contact, [cv2.IMWRITE_JPEG_QUALITY, 94])
    if not ok:
        raise RuntimeError('Could not encode contact sheet')
    # Detect changes during decoding before creating any evidence directory.
    current, _ = load_sequence(manifest, datasets, sequence, context['spatial_transform'])
    if canonical(current) != canonical(context):
        raise ValueError('Context changed during evidence preparation')
    output.mkdir(parents=True, exist_ok=False)
    with (output/'review.html').open('x', encoding='utf-8', newline='\n') as f:
        f.write(html)
    with (output/'contact_sheet.jpg').open('xb') as f:
        f.write(encoded.tobytes())
    packet = {'schema': 'limpia.gt-review.v1', 'status': 'PENDING_HUMAN_REVIEW',
        'context': context, 'context_sha256': digest(context), 'selected_frames': selected,
        'offset_candidates': list(OFFSETS), 'evidence': {n: file_sha256(output/n) for n in ('review.html', 'contact_sheet.jpg')},
        'sampling_method': 'start/quartiles/middle/end + two separated GT-overlap neighborhoods; not certified occlusions',
        'certification': 'No alignment approval was inferred from boxes, overlaps or successful decoding'}
    write_new_json(output/'review.json', packet)
    from .dataset_approval import decision_template
    write_new_json(output/'decision.pending.json', decision_template(output/'review.json'))
    return output


def view(manifest, datasets, sequence, *, offset=0, transform=None, extra_frames=(), cv2_module=None):
    """Native inspection: n/p selected samples; ./, exact adjacent frame; a/d offsets."""
    if offset not in OFFSETS:
        raise ValueError('Offset must be -2,-1,0,1,2')
    if cv2_module is None:
        import cv2 as cv2_module
    cv2 = cv2_module
    context, records = load_sequence(manifest, datasets, sequence, transform)
    samples = sorted({s['video_index'] for s in select_frames(records, context['video']['frames'])} | set(extra_frames))
    if any(type(i) is not int or not 0 <= i < context['video']['frames'] for i in samples):
        raise ValueError('Selected sample outside video')
    frames = decode_frames(relative_file(datasets, context['video']['path']), samples, context['video']['dimensions'])
    grouped = group_records(records)
    index, include_other = samples[0], False
    window = 'LimpIA GT - PENDING HUMAN REVIEW'
    try:
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        while True:
            if index not in frames:
                # Nearby ad-hoc requests are sequentially decoded, never approximate seeks.
                frames.update(decode_frames(relative_file(datasets, context['video']['path']), [index], context['video']['dimensions']))
            cv2.imshow(window, render_frame(frames[index], frame_boxes(grouped, index, offset, context), context, offset, include_other=include_other))
            key = cv2.waitKey(40) & 0xff
            if key in (27, ord('q')) or cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                break
            if key == ord('n'):
                index = next((i for i in samples if i > index), index)
            elif key == ord('p'):
                index = next((i for i in reversed(samples) if i < index), index)
            elif key == ord('.'):
                index = min(index+1, context['video']['frames']-1)
            elif key == ord(','):
                index = max(0, index-1)
            elif key == ord('a'):
                offset = max(-2, offset-1)
            elif key == ord('d'):
                offset = min(2, offset+1)
            elif key == ord('o'):
                include_other = not include_other
            # Bound the cache when browsing beyond the prepared samples.
            if len(frames) > len(samples)+8:
                frames = {k: v for k, v in frames.items() if k in samples or k == index}
    finally:
        cv2.destroyWindow(window)


def main(argv=None):
    p = argparse.ArgumentParser(description='MOT GT review only: no predictions, inference or metrics')
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--datasets', type=Path, default=Path(__file__).resolve().parent.parent/'videos_testing')
    p.add_argument('--sequence', choices=tuple(SUPPORTED), required=True)
    p.add_argument('--transform', type=Path, help='Optional new spatial candidate JSON; requires fresh evidence/review')
    p.add_argument('--frames', default='', help='Extra decoded zero-based indices, comma separated')
    p.add_argument('--offset', type=int, choices=OFFSETS, default=0)
    p.add_argument('--export', type=Path, help='Fresh evidence directory; omitting this opens the native viewer')
    a = p.parse_args(argv)
    try:
        extra = [int(i.strip()) for i in a.frames.split(',') if i.strip()]
        t = read_json(a.transform) if a.transform else None
        if a.export:
            output = prepare(a.manifest, a.datasets, a.sequence, a.export, transform=t, extra_frames=extra)
            print(f'Pending human review: {output / "review.html"}')
        else:
            view(a.manifest, a.datasets, a.sequence, offset=a.offset, transform=t, extra_frames=extra)
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        print(f'GT review error: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
