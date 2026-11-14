# Candidate onedir spec. Build and runtime smoke tests are REQUIRED before distribution.
from pathlib import Path
import os,uuid
os.environ["YOLO_OFFLINE"]="true"
os.environ["YOLO_AUTOINSTALL"]="false"
settings_dir=Path(SPECPATH).parent/"logs"/"packaging"/uuid.uuid4().hex/"ultralytics-settings"
settings_dir.mkdir(parents=True,exist_ok=False)
os.environ["YOLO_CONFIG_DIR"]=str(settings_dir)
from PyInstaller.utils.hooks import collect_data_files,collect_submodules
root=Path(SPECPATH).parent
configs=['camera.json','detection.json','tracking.json','counting.json','bytetrack_capstone.yaml','botsort_no_reid_capstone.yaml']
datas=[(str(root/'config'/name),'config') for name in configs]
datas+=collect_data_files('ultralytics',excludes=['**/*.pt','**/*.onnx','**/*.mp4'])
hidden=collect_submodules('ultralytics')+['PIL._tkinter_finder','lap','yaml']
a=Analysis([str(root/'ejecutable.py')],pathex=[str(root)],binaries=[],datas=datas,
           hiddenimports=hidden,hookspath=[],runtime_hooks=[],excludes=['pytest','notebook','IPython'])
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='LimpIA',debug=False,
        bootloader_ignore_signals=False,strip=False,upx=False,console=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='LimpIA')
