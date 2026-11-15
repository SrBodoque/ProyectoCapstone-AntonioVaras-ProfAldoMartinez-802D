"""Bounded resource catalog and unversioned launcher preferences."""
import json,os,subprocess,tempfile
from pathlib import Path
from .config import PROJECT_ROOT


def preference_path():
    return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'LimpIA'/'launcher.json'

def load_preferences():
    try:
        if preference_path().stat().st_size>65536:return {}
        data=json.loads(preference_path().read_text(encoding='utf-8'))
        return data if isinstance(data,dict) else {}
    except (OSError,ValueError):return {}

def save_preferences(**updates):
    path=preference_path();path.parent.mkdir(parents=True,exist_ok=True)
    data=load_preferences();data.update(updates)
    fd,name=tempfile.mkstemp(dir=path.parent,suffix='.tmp')
    with os.fdopen(fd,'w',encoding='utf-8') as stream:json.dump(data,stream,indent=2)
    os.replace(name,path)

def resource_roots():
    roots=[PROJECT_ROOT]
    prefs=load_preferences()
    roots += [Path(p) for p in prefs.get('resource_roots',[]) if isinstance(p,str)]
    if prefs.get('weights_dir'):roots.append(Path(prefs['weights_dir']))
    if os.environ.get('LIMPIA_RESOURCES_DIR'):roots.append(Path(os.environ['LIMPIA_RESOURCES_DIR']))
    try:
        git=subprocess.run(['git','rev-parse','--path-format=absolute','--git-common-dir'],cwd=PROJECT_ROOT,capture_output=True,text=True,timeout=2)
        if git.returncode==0:
            original=Path(git.stdout.strip()).parent/PROJECT_ROOT.relative_to(next(p for p in PROJECT_ROOT.parents if (p/'.git').exists()))
            roots.append(original)
    except (OSError,ValueError,StopIteration,subprocess.TimeoutExpired):pass
    return list(dict.fromkeys(p.resolve() for p in roots if p.is_dir()))

def valid_weights(path):
    if not path:return False
    model=Path(path)/'yolo26n.pt'
    return model.is_file() and model.stat().st_size>0

def default_weights():
    prefs=load_preferences()
    candidates=[os.environ.get('LIMPIA_WEIGHTS_DIR'),prefs.get('weights_dir'),*resource_roots()]
    return next((Path(p).resolve() for p in candidates if valid_weights(p)),PROJECT_ROOT)

def bounded_files(directory,suffix,depth=3,limit=500):
    if not directory.is_dir() or directory.is_symlink():return []
    found=[];pending=[(directory,0)];visited=0
    while pending and visited<64 and len(found)<limit:
        folder,level=pending.pop(0);visited+=1
        try:entries=sorted(folder.iterdir(),key=lambda p:p.name.casefold())[:256]
        except OSError:continue
        for path in entries:
            if path.is_symlink():continue
            if path.is_file() and path.suffix.lower()==suffix:found.append(path.resolve())
            elif path.is_dir() and level<depth and path.name.lower() not in ('.venv','.git','backups','backup','respaldos','__pycache__','runs'):
                pending.append((path,level+1))
            if len(found)>=limit:break
    return found

def videos():
    prefs=load_preferences();paths=[]
    for root in resource_roots():paths+=bounded_files(root/'videos_testing','.mp4')
    last=prefs.get('video')
    if last and Path(last).is_file():paths.insert(0,Path(last).resolve())
    return list(dict.fromkeys(paths))

def profiles(source,video=None,camera=None):
    from .presentation_sources import load_profile
    prefs=load_preferences();paths=[]
    for root in resource_roots():
        for directory in ('config/baselines','config/zones','results_testing'):paths+=bounded_files(root/directory,'.json')
    for directory in prefs.get('profile_dirs',[]):paths+=bounded_files(Path(directory),'.json',depth=1)
    if prefs.get('zones'):paths.insert(0,Path(prefs['zones']))
    result=[]
    digest=None
    if source=='video':
        from .video_source import file_sha256
        from .launcher_calibration import validate_video
        _,w,h=validate_video(video);digest=file_sha256(Path(video))
    for path in dict.fromkeys(paths):
        try:
            if not path.is_file() or path.stat().st_size>262144:continue
            data=json.loads(path.read_text(encoding='utf-8-sig'))
            if source=='video' and (data.get('kind')!='limpia_video_zones' or data.get('video_sha256')!=digest):continue
            profile=load_profile(path,source,video,True)
            if source=='video':
                pass
            else:w,h=camera.width,camera.height;profile.check_camera(camera.index,w,h)
            if (w,h)!=(profile.width,profile.height):continue
            result.append((path,profile.name))
        except (ValueError,OSError,RuntimeError,KeyError,TypeError,AttributeError):continue
    return result
