"""Versioned, validated, exclusive publication for launcher calibration only."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from .config import PROJECT_ROOT
from .launcher_calibration import new_output
from .presentation_sources import load_profile
from .video_zones import export_video_zones
from .zones import ZoneProfile


def next_output(label,catalog=()):
    directory=PROJECT_ROOT/'results_testing'/'calibration_profiles'
    if not directory.resolve().is_relative_to(PROJECT_ROOT.resolve()):raise ValueError('La salida automatica debe permanecer en el worktree actual.')
    versions=[]
    for path,name in catalog:
        for text in (Path(path).stem,name):
            match=re.search(r'v(\d+)$',text,re.I)
            if match:versions.append(int(match[1]))
    label=re.sub(r'[^\w-]+','_',label).strip('_') or 'perfil'
    for path in directory.glob(f'{label}.zones.v*.json'):
        match=re.fullmatch(re.escape(label)+r'\.zones\.v(\d+)\.json',path.name)
        if match:versions.append(int(match[1]))
    version=max(versions,default=0)+1
    while True:
        path=directory/f'{label}.zones.v{version}.json'
        side=path.with_name(path.stem+'.provenance.json')
        if not path.exists() and not path.is_symlink() and not side.exists() and not side.is_symlink():return path
        version+=1


def save_calibration(profile,source,video,camera,backend,frame,reviewer,output=None,catalog=()):
    if not isinstance(reviewer,str) or not reviewer.strip():raise ValueError('Indique un responsable de la revision.')
    profile=ZoneProfile.from_dict(profile.to_dict())
    automatic=output is None
    label=Path(video).stem if source=='video' else f'camera_{camera.index}'
    if source=='camera':
        profile.check_camera(camera.index,camera.width,camera.height)
        if (profile.width,profile.height)!=(camera.width,camera.height):raise ValueError('Resolucion de camara incompatible.')
    while True:
        target=next_output(label,catalog) if automatic else Path(output)
        if automatic:target.parent.mkdir(parents=True,exist_ok=True)
        target=new_output(target)
        side=target.with_name(target.stem+'.provenance.json')
        if source=='camera':new_output(side)
        # Validate complete staged bytes before publishing. Hard-link publication is
        # atomic and exclusive: an existing target can never be replaced.
        with TemporaryDirectory(prefix='.calibration-',dir=target.parent) as folder:
            staged=Path(folder)/'profile.json'
            if source=='video':export_video_zones(staged,video,profile,frame,reviewer)
            else:staged.write_text(json.dumps(profile.to_dict(),ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
            load_profile(staged,source,video,True)
            published_side=False
            try:
                if source=='camera':
                    provenance=dict(kind='limpia_camera_profile_provenance',schema_version=1,camera_index=camera.index,
                        orientation={'A':'exterior','B':'puerta'},orientation_confirmed=True,backend=backend,
                        reference_size=[profile.width,profile.height],reviewer=reviewer.strip(),
                        created_at=datetime.now(timezone.utc).isoformat(),frame_storage='not_saved',physical_count_validated=False,
                        warning='Valido solo con el mismo encuadre, orientacion A exterior/B puerta y geometria. Recalibrar al mover la camara.')
                    metadata=Path(folder)/'provenance.json'
                    metadata.write_text(json.dumps(provenance,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
                    os.link(metadata,side);published_side=True
                os.link(staged,target)
            except OSError as exc:
                if published_side:side.unlink()  # Only the sidecar exclusively created by this attempt.
                if automatic and isinstance(exc,FileExistsError):continue
                raise
        return target
