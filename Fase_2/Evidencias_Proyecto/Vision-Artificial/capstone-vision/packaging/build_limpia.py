"""Build candidate Windows onedir distribution; never installs dependencies."""
import argparse
from importlib.util import find_spec
from pathlib import Path
import subprocess,sys,uuid


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Only check build dependencies; create no artifacts.')
    args=parser.parse_args()
    missing=[name for name in ('PyInstaller','torch','torchvision','cv2','ultralytics','tkinter','PIL','yaml','lap') if find_spec(name) is None]
    if missing:
        print('Build pendiente: faltan '+', '.join(missing)+'. No se instala ni actualiza nada.',file=sys.stderr)
        return 2
    if args.check:
        print('Dependencias localizadas. Esto no acredita construccion ni ejecucion del EXE.')
        return 0
    if sys.platform!='win32':
        parser.error('Construir la distribucion Windows desde Windows.')
    project=Path(__file__).resolve().parent.parent
    run=project/'logs'/'packaging'/uuid.uuid4().hex
    run.mkdir(parents=True,exist_ok=False)
    result=subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--workpath',str(run/'build'),
                           '--distpath',str(run/'dist'),str(project/'packaging/LimpIA.spec')],cwd=project)
    if result.returncode:return result.returncode
    bundle=run/'dist'/'LimpIA'
    prohibited=[p for p in bundle.rglob('*') if p.is_file() and
                (p.suffix.lower() in ('.pt','.pth','.onnx','.mp4','.mov','.avi') or
                 p.name.lower() in ('device.local.json','counting.local.json'))]
    if prohibited:
        print('No distribuir: hay pesos, videos o preferencias dentro del candidato.',file=sys.stderr)
        return 1
    print(f'Candidato NO VALIDADO: {bundle / "LimpIA.exe"}')
    print('Probar MP4, camara, calibracion, cancelacion y cierre antes de distribuir.')
    return 0

if __name__=='__main__':raise SystemExit(main())
