"""Opt-in local acceptance. Never stores frames, weights or predictions.
Run from capstone-vision: python -B -m tests.validate_presentation_local is NOT
required: use python -B tests/validate_presentation_local.py with project on sys.path.
Prefer: python -B -m src.view_presentation for the actual window.
"""
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.view_presentation import parser, resolve_choices
from src.presentation_session import Session
from src.video_source import file_sha256


def main():
    p = parser()
    p.add_argument('--report', type=Path, required=True, help='NEW JSON technical report.')
    p.add_argument('--expected-in', type=int, default=21)
    p.add_argument('--expected-out', type=int, default=20)
    args = resolve_choices(p.parse_args())
    if args.source != 'video' or args.video is None:
        p.error('Acceptance runner requires --source video --video PATH.')
    if args.report.exists():
        p.error('Report must be a new file.')
    hashes = {str(path):file_sha256(path) for path in (args.video,args.zones)}
    started=time.perf_counter()
    session=Session(args)
    session.start()
    try:
        while session.running:
            session.thread.join(5)
            state=session.snapshot()
            print(f'frame={state.index+1} IN={state.entries} OUT={state.exits} status={state.status}',flush=True)
    except KeyboardInterrupt:
        session.stop()
        session.thread.join()
    state=session.snapshot()
    elapsed=time.perf_counter()-started
    unchanged=all(file_sha256(Path(path))==digest for path,digest in hashes.items())
    report=dict(interpreter=sys.executable,python=sys.version,device_requested=args.device,
                device_effective=args.device if not args.predictions and state.frames_processed else None,
                tracker=args.tracker,predictions=str(args.predictions) if args.predictions else None,
                input_hashes=hashes,inputs_unchanged=unchanged,frames=state.frames_processed,
                entries=state.entries,exits=state.exits,status=state.status,error=state.error,
                elapsed_seconds=elapsed,session_fps=state.frames_processed/elapsed,
                final_processing_fps=state.processing_fps,
                accepted=unchanged and state.status=='Finalizado' and
                         (state.entries,state.exits)==(args.expected_in,args.expected_out))
    with args.report.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['accepted'] else 1


if __name__=='__main__':
    raise SystemExit(main())
