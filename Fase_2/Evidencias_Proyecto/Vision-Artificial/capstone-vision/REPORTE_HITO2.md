# REPORTE FINAL — HITO 2

## ESTADO HITO 2
Implementado sobre el proyecto real adjunto. Validación automática OK en Linux; aceptación física en Windows/DroidCam PENDIENTE.

## RESUMEN
Detección local exclusiva de personas con YOLO26 Nano. Cajas, confianza, personas por frame y métricas, sin IDs ni entradas/salidas. El modelo se carga una vez; se reutiliza la sesión de cámara ya validada y se conserva el preview sin IA.

## ÁRBOL REAL DEL PROYECTO ENTREGADO
Raíz: capstone-vision. Cada ruta siguiente corresponde a un archivo incluido en el ZIP.

| Ruta | Estado |
| --- | --- |
| `config/detection.json` | Nuevo |
| `docs/02_deteccion_personas.md` | Nuevo |
| `src/detect.py` | Nuevo |
| `src/detector.py` | Nuevo |
| `tests/test_hito2.py` | Nuevo |
| `REPORTE_HITO2.md` | Nuevo |
| `.gitignore` | Modificado |
| `README.md` | Modificado |
| `docs/resultados_pruebas.md` | Modificado |
| `docs/validacion_tecnica.md` | Modificado |
| `requirements.txt` | Modificado |
| `src/config.py` | Modificado |
| `src/diagnostics.py` | Modificado |
| `.vscode/extensions.json` | Conservado |
| `.vscode/settings.json` | Conservado |
| `config/camera.json` | Conservado |
| `docs/00_contexto_vision.md` | Conservado |
| `docs/01_entorno_y_webcam.md` | Conservado |
| `logs/.gitkeep` | Conservado |
| `src/__init__.py` | Conservado |
| `src/camera.py` | Conservado |
| `src/main.py` | Conservado |
| `tests/test_hito1.py` | Conservado |

## ARCHIVOS NUEVOS
config/detection.json, docs/02_deteccion_personas.md, src/detect.py, src/detector.py, tests/test_hito2.py, REPORTE_HITO2.md.

## ARCHIVOS MODIFICADOS
.gitignore, README.md, docs/resultados_pruebas.md, docs/validacion_tecnica.md, requirements.txt, src/config.py, src/diagnostics.py.

## ARCHIVOS DELIBERADAMENTE NO MODIFICADOS
.vscode/extensions.json, .vscode/settings.json, config/camera.json, docs/00_contexto_vision.md, docs/01_entorno_y_webcam.md, logs/.gitkeep, src/__init__.py, src/camera.py, src/main.py, tests/test_hito1.py.

## VERSIONES INSTALADAS
Python de validación: 3.12.14, Linux x86_64. Se conserva Python objetivo 3.13.15 Windows x64.

- opencv-python 4.14.0.94; cv2 cargado 4.14.0.
- ultralytics 8.4.163.
- torch 2.14.0; runtime Linux 2.14.0+cu130.
- torchvision 0.29.0; runtime Linux 0.29.0+cu130.
- Inferencia en CPU; CUDA disponible False.

Los wheels PyPI Linux resolvieron runtimes GPU como transitivas; no se configuró CUDA manualmente ni se utilizó GPU. Las versiones directas se mantuvieron exactamente. Se comprobó disponibilidad de los cuatro wheels directos para Windows/CPython 3.13; la ejecución de Windows y sus DLL queda pendiente.

## MODELO UTILIZADO
Checkpoint oficial yolo26n.pt. Descarga/carga real mediante Ultralytics. Dos frames negros sintéticos: 0 detecciones. Imagen de muestra del paquete: 4 cajas, todas person/clase 0. Repetición con red bloqueada y pesos locales: 0 intentos de conexión y ningún resultado visual guardado. Esto no equivale a validación física de webcam ni precisión estadística.

## PRUEBAS HITO 1 ANTES DE CAMBIOS
16/16 OK; compileall, diagnóstico y pip check OK. No había fallos base de código. El .venv de Windows incluido en el RAR no se modificó; se utilizó un entorno temporal de Linux para validar.

## PRUEBAS AUTOMÁTICAS HITO 2
32/32 OK: JSON, rutas, rangos, tipos, modelo único, filtro person, parámetros, cajas, tiempos, errores de dependencia/modelo/inferencia, opciones sin guardado y liberación ante q/ESC/X/Ctrl+C/fallos.

## REGRESIÓN HITO 1 DESPUÉS DE CAMBIOS
16/16 OK. main.py, camera.py, camera.json y test_hito1.py idénticos al adjunto por SHA-256. La configuración de cámara del archivo adjunto era auto; se conservó. Las anotaciones físicas previas no se borraron.

## ERRORES ENCONTRADOS Y CORRECCIONES
Se corrigieron un fallback innecesario del directorio de ajustes de Ultralytics, bloques PowerShell mal formados del README heredado, la sugerencia de git init anidado y la expresión de exclusión de .venv/.git en la nueva ficha de pruebas.

La resolución completa de pip para Windows desde Linux falló al usar marcadores del sistema anfitrión. Se verificaron por separado wheels directos y metadata; no se atribuye ese fallo a incompatibilidad real de Windows. main/detect detectan ausencia de sesión gráfica y devuelven 1 con mensaje claro en este servidor, como corresponde.

## RESULTADO PIP CHECK
No broken requirements found. Código 0.

## RESULTADO COMPILEALL
python -m compileall src tests: código 0.

## RESULTADO SUITE DE TESTS
python -m unittest discover -s tests -v: 48 tests, OK.

## ESTADO DE GIT
El RAR no incluye .git. Se revisaron diferencias sin repositorio y hashes contra el adjunto. No se inicializó Git ni hubo staging, commit, push o cambios de remotos. Pesos *.pt ya ignorados; se añadieron runs/ y .ultralytics/. Revisar los cambios en el repositorio real al aplicar la entrega.

## PRUEBAS FÍSICAS PENDIENTES
Las 17 pruebas A–Q están preparadas en docs/resultados_pruebas.md: regresión, diagnóstico, descarga/carga, escena vacía, una/dos personas, movimiento, distancia, orientación, oclusión, falsos positivos, >=60 s de rendimiento, q/ESC (también X/Ctrl+C), liberación, privacidad y reinicios. Ejecutar en ambos equipos.

## COMANDOS EXACTOS QUE DEBE EJECUTAR EL USUARIO
Extraer el ZIP y copiar su contenido sobre el módulo existente. Conservar tu .venv y los ajustes locales de cámara que uses. No borrar la carpeta para reemplazarla: el ZIP no lleva entornos ni pesos. Abrir la carpeta que contiene src y requirements.txt. Desde esa raíz, una línea a la vez:

```powershell
.\.venv\Scripts\Activate.ps1
python --version
python -m pip install -r requirements.txt
python -m pip check
python -m unittest discover -s tests -v
python -m compileall src tests
python -m src.diagnostics
python -m src.main
python -m src.detect
```

Cerrar main antes de iniciar detect. Enfocar ventana para q/ESC. Tras cerrar detect, volver a ejecutar main para verificar liberación. Si la activación está bloqueada, reemplazar python por .\.venv\Scripts\python.exe; no hace falta recrear el entorno ni cambiar políticas.

Solo si NO existe .venv en ese equipo: comprobar py -3.13 --version (debe ser 3.13.15), crear con py -3.13 -m venv .venv y seguir los pasos anteriores. Escaneo opcional: python -m src.diagnostics --scan.

Revisar el repositorio real después de aplicar los archivos:

```powershell
git status --short --untracked-files=all
git diff
```

## RESULTADOS QUE EL USUARIO DEBE DEVOLVER
Consola de pip check, tests, diagnostics y detect; CPU/equipo/configuración; FPS pipeline e inferencia durante >=60 s posteriores al arranque; cierres y reaperturas; resultados por escena, falsos positivos/omisiones y verificación de ausencia de imágenes/videos/labels/runs. No es necesario enviar fotos/videos de personas.

## LIMITACIONES CONOCIDAS
No hay prueba física Windows/DroidCam desde Linux. No se garantizan 30 FPS ni exactitud en poca luz, distancia u oclusión. Bucle secuencial sin reconexión automática ni medida de latencia Wi-Fi de extremo a extremo. Solo CPU y checkpoint oficial en este hito. Personas por frame no significa personas únicas u ocupación. Requirements fija versiones directas; pip resuelve transitivas, no es un lockfile completo.

## SIGUIENTE HITO
ByteTrack + IDs temporales, después de aprobar físicamente Hito 2. No se implementó.

Los detalles de las tres revisiones y evidencia están en docs/validacion_tecnica.md; fundamentos/fuentes oficiales en docs/02_deteccion_personas.md. No se cambió la licencia del repositorio.
