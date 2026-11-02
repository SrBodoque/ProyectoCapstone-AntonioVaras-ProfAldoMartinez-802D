"""Explicit human decisions tied to immutable review evidence and current inputs.

No metrics, no inference, no mutation of the audit manifest. A local approval is
an attributed decision, not authentication or a digital signature of a person.
"""

import argparse
import copy
from datetime import date
from pathlib import Path

from .dataset_review import (SUPPORTED, canonical, digest, evaluable_interval,
    load_sequence, new_output, policy, read_json, relative_file, write_new_json)
from .video_source import file_sha256

CONFIRMATIONS = ('visual_alignment_reviewed', 'all_five_offsets_compared',
                 'no_unmodelled_crop_or_spatial_shift', 'classes_and_exclusions_reviewed',
                 'interval_and_boundaries_reviewed', 'crossings_and_occlusions_reviewed')


def validate_packet(review_path, manifest, datasets):
    review_path = Path(review_path)
    packet = read_json(review_path)
    if packet.get('schema') != 'limpia.gt-review.v1' or packet.get('status') != 'PENDING_HUMAN_REVIEW':
        raise ValueError('Not a pending review packet')
    context = packet['context']
    current, _ = load_sequence(manifest, datasets, context['sequence_id'], context['spatial_transform'])
    if canonical(context) != canonical(current) or packet['context_sha256'] != digest(current):
        raise ValueError('Review context/policy/transform no longer matches original inputs')
    if set(packet['evidence']) != {'review.html', 'contact_sheet.jpg'}:
        raise ValueError('Required review evidence is missing')
    for name, expected in packet['evidence'].items():
        if file_sha256(relative_file(review_path.parent, name)) != expected:
            raise ValueError('Evidence content changed after packet generation')
    if packet['offset_candidates'] != [-2, -1, 0, 1, 2]:
        raise ValueError('All five offset candidates are required')
    selected = packet['selected_frames']
    indices = [r['video_index'] for r in selected]
    n = current['video']['frames']
    if (any(type(i) is not int or not 0 <= i < n for i in indices)
            or indices != sorted(set(indices)) or not {0, n//2, n-1}.issubset(indices)):
        raise ValueError('Review evidence must include start/middle/end without duplicate indices')
    if not any('geometric_overlap_candidate_neighborhood' in s['reasons'] for s in selected):
        raise ValueError('Review evidence lacks crossing/occlusion candidate neighborhoods')
    return packet


def decision_template(review_path):
    p = read_json(review_path)
    n = p['context']['video']['frames']
    return {'schema': 'limpia.gt-decision.v1', 'decision': 'PENDING',
        'sequence_id': p['context']['sequence_id'], 'review_sha256': file_sha256(Path(review_path)),
        'spatial_transform': p['context']['spatial_transform'], 'policy': p['context']['policy'],
        'offset': None, 'interval_video_indices_inclusive': [0, n-1],
        'reviewed_video_indices': [], 'reviewer': '', 'approval_date': '', 'notes': '',
        'confirmations': {key: False for key in CONFIRMATIONS}}


def validate_decision(decision, packet, review_sha256):
    c = packet['context']
    if decision.get('schema') != 'limpia.gt-decision.v1' or decision.get('decision') != 'APPROVE':
        raise ValueError('An explicit APPROVE decision is required after human review')
    if decision['sequence_id'] != c['sequence_id'] or decision['review_sha256'] != review_sha256:
        raise ValueError('Decision is for another sequence/review packet')
    if canonical(decision['spatial_transform']) != canonical(c['spatial_transform']) or canonical(decision['policy']) != canonical(c['policy']):
        raise ValueError('Transform or exclusion policy changed; generate and review new evidence')
    offset = decision['offset']
    allowed = evaluable_interval(c['video']['frames'], offset)
    interval = decision['interval_video_indices_inclusive']
    if (not isinstance(interval, list) or len(interval) != 2 or any(type(v) is not int for v in interval)
            or not allowed[0] <= interval[0] <= interval[1] <= allowed[1]):
        raise ValueError('Approved interval is outside video/GT overlap for the chosen offset')
    required = {s['video_index'] for s in packet['selected_frames']}
    reviewed = decision['reviewed_video_indices']
    if (not isinstance(reviewed, list) or any(type(v) is not int for v in reviewed)
            or len(reviewed) != len(set(reviewed)) or not required.issubset(reviewed)
            or not {interval[0], interval[1]}.issubset(reviewed)
            or any(not 0 <= v < c['video']['frames'] for v in reviewed)):
        raise ValueError('Review log must cover selected frames and both approved interval boundaries')
    if not isinstance(decision['reviewer'], str) or not decision['reviewer'].strip():
        raise ValueError('Named human reviewer required')
    date.fromisoformat(decision['approval_date'])
    if len(decision['approval_date']) != 10:
        raise ValueError('Approval date must be YYYY-MM-DD')
    if not isinstance(decision['notes'], str) or not decision['notes'].strip():
        raise ValueError('Record the review conclusion, ambiguities and limits in notes')
    if (set(decision['confirmations']) != set(CONFIRMATIONS)
            or any(decision['confirmations'][k] is not True for k in CONFIRMATIONS)):
        raise ValueError('Every human review confirmation must be explicit')


def register_approval(review_path, decision_path, manifest, datasets, output):
    output = new_output(output, datasets)
    packet = validate_packet(review_path, manifest, datasets)
    decision = read_json(decision_path)
    sha = file_sha256(Path(review_path))
    validate_decision(decision, packet, sha)
    approval = {'schema': 'limpia.gt-approval.v1', 'decision': decision,
        'context': packet['context'], 'context_sha256': packet['context_sha256'],
        'review_sha256': sha, 'evidence': packet['evidence'],
        'decision_sha256': digest(decision), 'status': 'APPROVED_BY_NAMED_REVIEWER'}
    # Revalidate before the exclusive output write: no source/config drift during registration.
    validate_packet(review_path, manifest, datasets)
    if file_sha256(Path(review_path)) != sha:
        raise ValueError('Review packet changed while recording approval')
    write_new_json(output, approval)
    return approval


def validate_approval(approval_path, review_path, manifest, datasets, *, expected_transform=None,
                      expected_offset=None, expected_policy=None):
    a = read_json(approval_path)
    if a.get('schema') != 'limpia.gt-approval.v1' or a.get('status') != 'APPROVED_BY_NAMED_REVIEWER':
        raise ValueError('Not a recorded human approval')
    p = validate_packet(review_path, manifest, datasets)
    sha = file_sha256(Path(review_path))
    if (a['review_sha256'] != sha or a['context_sha256'] != p['context_sha256']
            or canonical(a['context']) != canonical(p['context']) or a['evidence'] != p['evidence']
            or a['decision_sha256'] != digest(a['decision'])):
        raise ValueError('Approval no longer binds to this review/configuration/evidence')
    validate_decision(a['decision'], p, sha)
    if expected_transform is not None and canonical(expected_transform) != canonical(a['context']['spatial_transform']):
        raise ValueError('Requested transform differs from human approval')
    if expected_offset is not None and expected_offset != a['decision']['offset']:
        raise ValueError('Requested offset differs from human approval')
    if expected_policy is not None and canonical(expected_policy) != canonical(a['context']['policy']):
        raise ValueError('Requested policy differs from human approval')
    return a


def verified_manifest(manifest_path, datasets, bindings=()):
    """Compute READY, never accept a manually edited status/eligible flag as evidence.

    bindings are pairs (approval_path, review_path); relocation uses explicit datasets.
    A future experiment must call this validator again, not trust a saved READY bit.
    """
    original = read_json(manifest_path)
    result = copy.deepcopy(original)
    result['dataset_root'] = '.'
    result['path_resolution'] = 'All input paths relative to explicit --datasets root; legacy absolute root ignored'
    result['review_registry_schema'] = 'limpia.gt-approval.v1'
    result['eligible_sequence_ids'] = []
    by_id = {c['id']: c for c in result['sequences']}
    for sid in SUPPORTED:
        c = by_id[sid]
        c['status'] = 'NEEDS_VERIFICATION'
        c['evaluation_ready'] = False
        c['verification'] = {'temporal_alignment_verified': False, 'evaluation_policy_verified': False,
                             'visual_review': 'PENDING_HUMAN_APPROVAL'}
    # Unsupported sources are kept as data, never promoted via this extension.
    for c in result['sequences']:
        if c['id'] not in SUPPORTED:
            c['evaluation_ready'] = False
    seen = set()
    for approval_path, review_path in bindings:
        a = validate_approval(approval_path, review_path, manifest_path, datasets)
        sid = a['context']['sequence_id']
        if sid in seen:
            raise ValueError('Duplicate approvals for one sequence; select one explicit decision')
        seen.add(sid)
        c = by_id[sid]
        c.update(status='READY', evaluation_ready=True,
            approved_configuration={'spatial_transform': a['context']['spatial_transform'],
                'offset': a['decision']['offset'], 'policy': a['context']['policy'],
                'interval_video_indices_inclusive': a['decision']['interval_video_indices_inclusive'],
                'approval_sha256': file_sha256(Path(approval_path)),
                'review_sha256': a['review_sha256'], 'reviewer': a['decision']['reviewer'],
                'approval_date': a['decision']['approval_date']})
        c['verification'] = {'temporal_alignment_verified': True, 'evaluation_policy_verified': True,
                             'visual_review': 'NAMED_HUMAN_DECISION_VALIDATED_AGAINST_CURRENT_INPUTS'}
        result['eligible_sequence_ids'].append(sid)
    result['eligible_sequence_ids'].sort()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='Register/validate explicit GT review decisions; no metrics')
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--datasets', type=Path, default=Path(__file__).resolve().parent.parent/'videos_testing')
    commands = parser.add_subparsers(dest='command', required=True)
    approve = commands.add_parser('approve')
    approve.add_argument('--review', type=Path, required=True)
    approve.add_argument('--decision', type=Path, required=True)
    approve.add_argument('--output', type=Path, required=True)
    status = commands.add_parser('status')
    status.add_argument('--binding', action='append', nargs=2, metavar=('APPROVAL_JSON', 'REVIEW_JSON'), default=[])
    status.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'approve':
            a = register_approval(args.review, args.decision, args.manifest, args.datasets, args.output)
            print(f"Recorded human decision for {a['context']['sequence_id']}; revalidate before experiments")
        else:
            out = new_output(args.output, args.datasets)
            m = verified_manifest(args.manifest, args.datasets, args.binding)
            write_new_json(out, m)
            print(f"Validated eligible cases: {m['eligible_sequence_ids']}")
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f'Approval rejected: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
