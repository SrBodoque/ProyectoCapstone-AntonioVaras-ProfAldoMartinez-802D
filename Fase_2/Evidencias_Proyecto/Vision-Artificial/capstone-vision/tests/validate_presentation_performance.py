"""Three independent real UI runs for MP4 and uncalibrated physical camera."""
import argparse,json,subprocess,sys,uuid
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--resources',type=Path,required=True);p.add_argument('--camera-index',type=int,default=0);p.add_argument('--resume-prefix',type=Path);p.add_argument('--runs',type=int,default=3);p.add_argument('--sources',nargs='+',choices=('video','camera'),default=('video','camera'))
    o=p.parse_args();prefix=o.resume_prefix or Path('logs')/('presentation-cards-'+uuid.uuid4().hex[:8]);reports=[]
    common=['--device','cuda:0','--weights-dir',str(o.resources)]
    for run in range(1,o.runs+1):
        unit=Path(f'{prefix}-unit-{run}.txt')
        if not unit.exists():
            with unit.open('x',encoding='utf-8') as log:
                result=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests','-v'],stdout=log,stderr=subprocess.STDOUT)
            if result.returncode:raise RuntimeError(f'Unit regression failed: {unit}')
        elif 'OK (skipped=3)' not in unit.read_text(encoding='utf-8'):
            raise RuntimeError(f'Cannot resume failed unit regression: {unit}')
        summary=[x for x in unit.read_text(encoding='utf-8').splitlines() if x.startswith(('Ran ','OK','FAILED'))]
        print(json.dumps(dict(run=run,unit=summary)),flush=True)
        for source in o.sources:
            report=Path(f'{prefix}-{source}-{run}.json');log=Path(f'{prefix}-{source}-{run}.txt')
            command=[sys.executable,'-B','tests/benchmark_presentation.py','--source',source,*common,'--report',str(report),'--maximized']
            if source=='video':command+=['--video',str(o.resources/'videos_testing/nuevo_angulo/video_03.mp4'),'--max-frames','0']
            else:command+=['--camera-index',str(o.camera_index),'--tracking-only','--max-frames','600']
            print(f'START run={run} source={source} report={report}',flush=True)
            if not report.exists():
                with log.open('x',encoding='utf-8') as stream:
                    result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
                if result.returncode or not report.exists():raise RuntimeError(f'Benchmark failed: {log}')
            else:
                print(f'Reusing existing report from this unchanged-code series: {report}',flush=True)
            data=json.loads(report.read_text(encoding='utf-8'))
            valid=not data['error'] and (.96<data['speed']<1.04)
            if source=='video':valid=valid and data['frames']==5732 and (data['entries'],data['exits'])==(21,20) and data['status']=='Finalizado' and data['display_unique_frames']==5732 and data['display_index_gaps']==0 and data['display_interval_ms_p95']<45 and data['display_interval_ms_max']<100
            else:valid=valid and data['frames']>=600 and data['entries'] is None and data['exits'] is None and data['capture_to_processing_ms_p95']<150 and data['display_interval_ms_p95']<45 and data['capture_to_display_ms_p95']<200
            reports.append(dict(run=run,accepted=valid,report=str(report),**data))
            with Path(f'{prefix}-summary.json').open('w',encoding='utf-8') as stream:json.dump(reports,stream,indent=2)
            print(json.dumps(reports[-1]),flush=True)
            if not valid:raise RuntimeError(f'Acceptance failed: {report}')
    print(f'ALL ACCEPTED: {prefix}-summary.json',flush=True)

if __name__=='__main__':main()
