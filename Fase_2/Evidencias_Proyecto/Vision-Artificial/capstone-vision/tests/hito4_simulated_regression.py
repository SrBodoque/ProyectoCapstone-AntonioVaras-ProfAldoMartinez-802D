"""Regresión auxiliar explícitamente SIMULADA; no certifica GUI, MP4 ni IA real.

Ejecutar: python tests/hito4_simulated_regression.py [ruta_resumen.json]
No reemplaza `python -m unittest discover -s tests -v` en el equipo completo.
Los tests reales excluidos se enumeran en el resumen opcional; nunca cuentan
como aprobados. Deduplica los tests que test_video_regression vuelve a cargar.
Los originales permanecen intactos. El doble de cv2 vive solo en este proceso.
"""
import importlib.machinery
import json
import os
import re
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

root=Path(__file__).resolve().parents[1]
os.chdir(root)
sys.path.insert(0,str(root));sys.path.insert(0,str(root/'tests'))
cv2=ModuleType('cv2');cv2.__spec__=importlib.machinery.ModuleSpec('cv2',None)
cv2.error=type('SimulatedCVError',(Exception,),{})
names=set()
for path in [*root.joinpath('src').glob('*.py'),*root.joinpath('tests').glob('*.py')]:
 names.update(re.findall(r'cv2\.([A-Z][A-Z0-9_]+)',path.read_text(encoding='utf-8-sig')))
for i,name in enumerate(sorted(names)):setattr(cv2,name,i+1)
for name in ('VideoCapture','namedWindow','destroyAllWindows','imshow','waitKey','getWindowProperty',
             'putText','line','rectangle','resize','fillPoly','polylines','addWeighted','circle','setMouseCallback'):
 setattr(cv2,name,MagicMock(name='simulated_cv2.'+name))
cv2.__version__='SIMULATED';sys.modules['cv2']=cv2

def flat(suite):
 for item in suite:
  if isinstance(item,unittest.TestSuite):yield from flat(item)
  else:yield item

selected=[];pending=[];seen=set();duplicates=0
for test in flat(unittest.defaultTestLoader.discover(str(root/'tests'))):
 name=test.id()
 if name in seen:duplicates+=1;continue
 seen.add(name)
 if (any(module in name for module in ('test_hito3_integration.','test_fasttracker_integration.',
      'test_recovery_integration.','test_botsort_reid_integration.','test_mp4_inference_integration.',
      'test_video_source.RealMp4Tests.','test_video_runner.RealDecoderRunnerTests.'))
      or name.endswith('.test_fast_specific_values_are_official_defaults')):
  pending.append(name)
 else:selected.append(test)
result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(selected))
summary={'mode':'OpenCV simulado; motores IA simulados en sus contratos', 'run':result.testsRun,
 'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
 'duplicate_invocations_removed':duplicates,'pending_real_tests':pending}
if len(sys.argv) > 1:
 Path(sys.argv[1]).write_text(json.dumps(summary,indent=2))
print(json.dumps({k:v for k,v in summary.items() if k!='pending_real_tests'}));print('Pending real:',len(pending))
raise SystemExit(not result.wasSuccessful())
