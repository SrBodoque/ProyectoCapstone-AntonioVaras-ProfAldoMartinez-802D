"""Portable Windows bootstrap. Existing environments are read-only."""
import struct
import argparse,hashlib,json,logging,os,re,shutil,subprocess,sys,tempfile,uuid
from pathlib import Path
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parent
logger=logging.getLogger('limpia.bootstrap')
MODEL_HASH='9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef'
MODEL_URL='https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n.pt'
VERSIONS={'torch':'2.14.0','torchvision':'0.29.0','ultralytics':'8.4.163','opencv-python':'4.14.0.94','lap':'0.5.12'}
class Cancelled(Exception):pass

def run(argv,**kw):
    logger.info('Running %s',argv)
    return subprocess.run([str(x) for x in argv],check=True,**kw)

def ask(message):return input(message+' [s/N]: ').strip().lower()=='s'
def require(message):
    if not ask(message):raise Cancelled()

def read(path):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}

def state_path():return Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'LimpIA'/'bootstrap.json'
def save_state(data):
    path=state_path();path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as f:json.dump(data,f);name=f.name
    os.replace(name,path)

def candidates(explicit=None):
    remembered=read(state_path())
    roots=[ROOT]
    # Worktree pointer discovery does not require git.exe and is bounded.
    for parent in ROOT.parents:
        pointer=parent/'.git'
        if pointer.is_file():
            line=pointer.read_text(encoding='utf-8').strip()
            if line.startswith('gitdir: '):
                gitdir=(parent/line[8:]).resolve();common=gitdir/'commondir'
                if common.is_file():
                    original=(gitdir/common.read_text().strip()).resolve().parent
                    roots.append(original/ROOT.relative_to(parent))
            break
    values=[ROOT/'.venv/Scripts/python.exe',explicit or os.environ.get('LIMPIA_PYTHON'),remembered.get('python')]
    values.extend(r/'.venv/Scripts/python.exe' for r in roots[1:])
    return list(dict.fromkeys(Path(v).expanduser().resolve() for v in values if v))

def probe(python,device='cpu',full=False,weights=None):
    code="""import sys,struct,json,importlib.metadata as m
assert sys.version_info[:2]==(3,13) and struct.calcsize('P')==8,'Requiere Python 3.13 x64'
import tkinter,cv2,ultralytics,torch,torchvision,lap,yaml,PIL
expected=json.loads(sys.argv[1])
for name,version in expected.items():
 assert m.version(name).split('+')[0]==version,(name,m.version(name),version)
device=sys.argv[2]
t=torch.ones(1,device=device);t.add_(1)
assert t.item()==2
if device.startswith('cuda'):
 assert torch.cuda.is_available() and t.is_cuda
 torch.cuda.synchronize()
assert torchvision.ops.nms(torch.tensor([[0.,0.,1.,1.]]),torch.tensor([1.]),.5).numel()==1
if len(sys.argv)>3:
 import numpy as np
 from ultralytics import YOLO
 YOLO(sys.argv[3]).predict(np.zeros((64,64,3),dtype=np.uint8),device=device,verbose=False)
print(json.dumps({'python':sys.executable,'torch':torch.__version__,'cuda':torch.version.cuda,'device':device}))
"""
    argv=[python,'-B','-c',code,json.dumps(VERSIONS),device]
    if weights is not None:argv.append(weights)
    result=run(argv,capture_output=True,text=True,timeout=120)
    logger.info('%s %s',result.stdout,result.stderr)
    if full:run([python,'-m','pip','check'],capture_output=True,text=True,timeout=60)
    return result.stdout

def hardware():
    try:return run(['nvidia-smi','--query-gpu=name,driver_version','--format=csv,noheader'],capture_output=True,text=True,timeout=10).stdout.strip()
    except (OSError,subprocess.SubprocessError):return ''

def gpu_ready():
    try:
        output=run(['nvidia-smi'],capture_output=True,text=True,timeout=10).stdout
        match=re.search(r'CUDA Version:\s*(\d+)\.(\d+)',output)
        return bool(match and tuple(map(int,match.groups()))>=(13,2))
    except (OSError,subprocess.SubprocessError):return False

def install(python,variant,target):
    # Only a new, explicitly owned target may be installed. No repair of external envs.
    if variant=='gpu' and not gpu_ready():raise ValueError('Driver NVIDIA no acredita CUDA 13.2. Revise driver o elija CPU explicitamente.')
    target=Path(target)
    if target.exists():raise ValueError('El entorno ya existe. Elija otro directorio NUEVO; no se modifica.')
    if sys.version_info[:2]!=(3,13) or struct.calcsize('P')!=8:raise ValueError('Crear el entorno requiere Python 3.13 x64.')
    require(f'Crear entorno nuevo en {target} e instalar dependencias ({variant})?')
    run([python,'-m','venv',target])
    exe=target/'Scripts/python.exe'
    suffix='cpu' if variant=='cpu' else 'cu132'
    constraint=target/'limpia-torch-constraints.txt'
    constraint.write_text(f'torch==2.14.0+{suffix}\ntorchvision==0.29.0+{suffix}\n',encoding='utf-8')
    run([exe,'-m','pip','install','torch==2.14.0','torchvision==0.29.0','--index-url',f'https://download.pytorch.org/whl/{suffix}'])
    run([exe,'-m','pip','install','-r',ROOT/'requirements-bootstrap-common.txt','-c',constraint])
    return exe

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def weights(python,configured=None):
    prefs=read(state_path());launcher=read(state_path().with_name('launcher.json'))
    locations=[ROOT,configured,os.environ.get('LIMPIA_WEIGHTS_DIR'),prefs.get('weights'),launcher.get('weights_dir')]
    locations.extend(p.parent.parent.parent for p in candidates())
    while True:
        for location in locations:
            if not location:continue
            path=Path(location);path=path/'yolo26n.pt' if path.is_dir() else path
            if path.name!='yolo26n.pt' or not path.is_file():continue
            if digest(path)!=MODEL_HASH:
                print('SHA-256 diferente al baseline:',path)
                if not ask('Continuar con este modelo distinto (requiere validacion funcional)?'):continue
            return path.resolve()
        choice=input('Pesos ausentes. Ruta de yolo26n.pt, D descargar oficial, Enter cancelar: ').strip().strip('"')
        if not choice:raise Cancelled()
        if choice.lower()!='d':locations=[choice];continue
        require('Descargar yolo26n.pt oficial? No se redistribuyen pesos en Git; revise licencia Ultralytics')
        directory=state_path().parent/'weights';directory.mkdir(parents=True,exist_ok=True)
        target=directory/'yolo26n.pt'
        if target.exists():raise ValueError('Ya existen pesos en destino; no se sobrescriben.')
        with tempfile.TemporaryDirectory(dir=directory) as temp:
            staged=Path(temp)/'yolo26n.pt'
            with urlopen(MODEL_URL,timeout=60) as response,staged.open('xb') as stream:shutil.copyfileobj(response,stream)
            if digest(staged)!=MODEL_HASH:raise ValueError('Descarga no coincide con SHA-256 del baseline; no se publica.')
            os.link(staged,target)
        return target

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python',type=Path);parser.add_argument('--weights',type=Path)
    parser.add_argument('--device',choices=('cpu','cuda:0'));parser.add_argument('--check',action='store_true')
    opts=parser.parse_args(argv)
    logs=state_path().parent/'logs';logs.mkdir(parents=True,exist_ok=True)
    handler=logging.FileHandler(logs/(uuid.uuid4().hex+'.log'),encoding='utf-8')
    logger.addHandler(handler);logger.setLevel(logging.INFO)
    os.environ['YOLO_AUTOINSTALL']='false'
    try:
        remembered=read(state_path());device=opts.device or remembered.get('device') or 'cpu'
        if not opts.device and not remembered.get('device') and not opts.check:
            print('NVIDIA:',hardware() or 'No disponible o deteccion inconclusa')
            choice=input('Dispositivo: G intentar CUDA, C CPU, Enter cancelar: ').strip().lower()
            if choice not in ('g','c'):raise Cancelled()
            device='cuda:0' if choice=='g' else 'cpu'
        selected=None
        for candidate in candidates(opts.python):
            if not candidate.is_file():continue
            try:probe(candidate,device)
            except (OSError,subprocess.SubprocessError) as exc:
                logger.exception('Entorno no compatible');print('Entorno no compatible:',candidate);continue
            if candidate!=ROOT/'.venv/Scripts/python.exe' and remembered.get('python')!=str(candidate) and not opts.check:
                if not ask(f'Se encontro un entorno valido: {candidate}. Reutilizar sin modificarlo?'):continue
            selected=candidate;break
        while selected is None:
            choice=input('Ruta de Python externo, N crear entorno nuevo, Enter cancelar: ').strip().strip('"')
            if not choice:raise Cancelled()
            try:
                if choice.lower()=='n':
                    info=hardware();print('NVIDIA (compatibilidad aun no validada):',info or 'Deteccion inconclusa o GPU no disponible')
                    variant=input('GPU CUDA cu132 (G) o CPU (C): ').strip().lower()
                    if variant not in ('g','c'):raise Cancelled()
                    device='cuda:0' if variant=='g' else 'cpu'
                    if variant=='g':require('cu132 requiere GPU/driver compatibles. No se instalan drivers. Intentar y validar CUDA?')
                    target=ROOT/'.venv'
                    if target.exists():target=Path(input('El entorno local existe. Ruta de entorno NUEVO: ').strip())
                    selected=install(sys.executable,'gpu' if variant=='g' else 'cpu',target)
                else:selected=Path(choice)
                probe(selected,device,full=True)
            except (ValueError,OSError,subprocess.SubprocessError) as exc:
                logger.exception('Preparacion fallida');print('No fue posible validar. No se cambia a CPU automaticamente:',exc)
                selected=None
        model=weights(selected,opts.weights)
        # A changed model/env requires real loading and inference before recording success.
        fingerprint=[str(selected),selected.stat().st_mtime_ns,str(model),digest(model),device]
        if remembered.get('fingerprint')!=fingerprint:probe(selected,device,full=True,weights=model)
        else:probe(selected,device,full=True)
        print('Se encontro un entorno de LimpIA valido.',device)
        if opts.check:return 0
        save_state(dict(python=str(selected),weights=str(model.parent),device=device,fingerprint=fingerprint))
        env=dict(os.environ,LIMPIA_WEIGHTS_DIR=str(model.parent))
        return run([selected,'-B',ROOT/'ejecutable.py','--device',device,'--weights-dir',model.parent],cwd=ROOT,env=env).returncode
    except Cancelled:print('Preparacion cancelada; LimpIA no se inicia.');return 0
    except (KeyboardInterrupt,EOFError):print('Operacion interrumpida. Puede reintentar sin borrar el entorno.');return 2
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        logger.exception('Bootstrap fallo');print('No fue posible iniciar LimpIA:',exc,'Detalles en',logs);return 1
    finally:logger.removeHandler(handler);handler.close()
if __name__=='__main__':raise SystemExit(main())
