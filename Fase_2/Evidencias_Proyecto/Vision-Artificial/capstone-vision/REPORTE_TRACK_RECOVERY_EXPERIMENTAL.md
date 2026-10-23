# Reporte final — ByteTrack Recovery experimental

Fecha: 2026-10-18. Fuente: `Vision-Artificial(1).zip`, idéntico al primer
`Vision-Artificial.zip` recibido. Se conservó su estructura `Vision-Artificial/capstone-vision/`.

**Implementación realizada; validación completa con las dependencias reales pendiente.**
No se afirma mejora física de cruces u oclusiones. La entrega permite realizar
ese experimento después de ejecutar la suite completa en el entorno funcional.

## 1. Estado general

Se agregó `python -m src.track_recovery` reutilizando el pipeline actual.
Compilación e imports correctos; 21 pruebas nuevas simuladas y 191 anteriores
en arnés con OpenCV simulado pasan. La suite estándar no queda certificada:
este servidor no dispone de OpenCV, Ultralytics, torch, torchvision ni lap.
No se reemplazó ByteTrack/FastTracker ni se implementó conteo.

## 2. Archivos inspeccionados

Se revisaron `src/tracker.py`, `src/track.py`, `src/track_fast.py`, `src/config.py`,
`src/detector.py`, `src/devices.py`, `src/camera.py`, `src/detect.py`, configuraciones
JSON/YAML, requirements, `.gitignore`, README, pruebas de H1/H2/H3, FastTracker,
cámara y dispositivos, y documentación de tracking/comparación/dispositivos.
Se compararon todos los archivos originales contra el ZIP para proteger el baseline.

SHA-256 del ZIP fuente:
`8a0f107976b7ee0372a7c9a08c81004d223b9fcbc2375bc05f8038d3da2f9b53`.

## 3. Hallazgo técnico original

El código pasa `confidence_threshold=0.65` a `model.track()`. Los YAML originales
usan umbrales high/low/new de 0.25/0.10/0.25. El filtro previo impide que lleguen
los candidatos débiles a la segunda asociación. La advertencia existente ya
explica esa limitación. No se cambió la confianza general elegida físicamente.

## 4. Hipótesis de Recovery

Permitir candidatos débiles para intentar mantener una trayectoria activa y
reservar las altas nuevas a detecciones fuertes. Esto podría reducir algunos
cambios de ID por caída de confianza durante una oclusión parcial. No implica
resolver toda oclusión ni eliminar falsos positivos, intercambios de IDs o pérdidas.

## 5. Cambios implementados

Nuevo entrypoint de 16 líneas y YAML experimental. Se añadió un argumento
opcional a `PersonTracker`, `track.main` y `run_tracking`, y logs del valor efectivo.
La llamada de inferencia usa ese valor; el resto del pipeline permanece compartido.
El cuerpo del bucle, dibujo, `Track`, `FrameTracks` y `TrackHistory` se verificaron
idénticos mediante comparación estructural del código (AST).

## 6. Comportamiento de src.track_recovery

Selecciona explícitamente `config/bytetrack_recovery_capstone.yaml` y conf 0.10,
lee la cámara existente, resuelve el dispositivo existente y carga YOLO26n una
vez por sesión. Muestra `ByteTrack Recovery (Experimental)` con las cajas, IDs,
trails y métricas existentes. No presenta selectores ni escribe preferencias.

## 7. Override de confianza

`tracking_confidence_override=None` conserva la confianza general. Recovery
proporciona 0.10 y se almacena aparte como `self.tracking_confidence`; nunca se
sobrescribe `self.config['confidence_threshold']` con ese valor.
Se aceptan int/float finitos en [0, 1]; se rechazan strings, booleanos, NaN,
infinito y valores fuera de rango. `None` se resuelve al valor general, que también
debe ser válido. Un override inválido falla antes de cargar el modelo.
No se cambia `model.predict()` del detector.

## 8. Parámetros exactos

| Parámetro | Recovery | ByteTrack/FastTracker originales |
| --- | --- | --- |
| Confianza enviada a model.track | 0.10 | 0.65 |
| track_high_thresh | 0.65 | 0.25 |
| track_low_thresh | 0.10 | 0.10 |
| new_track_thresh | 0.65 | 0.25 |
| track_buffer | 30 | 30 |
| match_thresh | 0.80 | 0.80 |
| fuse_score | true | true |
| persist | true | true |

Comunes: YOLO26n, person 0, IoU 0.7, imgsz 640, trails 30, misma cámara y
dispositivo efectivo. Sin ajustes de rendimiento ni de otros umbrales.

## 9. YAML Recovery

Nuevo `config/bytetrack_recovery_capstone.yaml`, `tracker_type: bytetrack` y los
seis parámetros ya reconocidos por el validador original. El YAML pasa dicho
validador. Se conserva `track_low_thresh < track_high_thresh`; con override se
comprueba además `new_track_thresh >= track_high_thresh` antes de cargar YOLO.
`src/config.py` y las reglas de los modos originales no se modificaron.
La inicialización en Ultralytics 8.4.163 instalado queda pendiente por el entorno.

## 10. Control de creación de nuevos tracks

La configuración reserva nuevas trayectorias a detecciones altas que además
alcanzan `new_track_thresh`. Las débiles se destinan a asociación temporal.
Se prepararon pruebas reales para comprobar que detecciones 0.15–0.649, incluso
repetidas, no inician tracks, y que una detección 0.35 continúa un ID activo.
Estas pruebas del motor no se pudieron ejecutar aquí; no se presentan como aprobadas.
No se agregó un filtro artificial que oculte candidatos o invente IDs.

## 11. Limitaciones de asociación de baja confianza

La documentación oficial actual limita la segunda asociación a tracks que siguen
en estado activo; usa detecciones con score mayor que low y menor que high.
Los tracks perdidos o sin confirmar siguen otras reglas. Una detección alta
posterior puede recuperar un perdido si la asociación y el buffer lo permiten.
Eso no garantiza recuperar su ID tras una oclusión completa prolongada.
La documentación consultada no sustituye ejecutar la versión exacta 8.4.163.

## 12. ByteTrack original intacto

El comando `src.track` conserva conf 0.65 y su ruta explícita original. Se
mantienen los argumentos previos cuando no se suministra override. El YAML y
`tracking.json` son idénticos byte por byte. Continúa como baseline estable.

## 13. FastTracker intacto

`src/track_fast.py` y `config/fasttrack_capstone.yaml` permanecen idénticos.
El pipeline compartido sigue recibiendo conf 0.65 al no tener override.
Los tests originales FastTracker no se modificaron.

## 14. Detección original intacta

`src/detect.py`, `src/detector.py` y `config/detection.json` permanecen idénticos.
La prueba simulada confirma `predict(conf=0.65)`. No se incorpora Recovery a H2.
El modelo, IoU, tamaño, clase y configuración general se conservan.

## 15. Cámara

Misma configuración: índice 1, 1280×720, 60 FPS solicitados y backend auto.
`camera.json`, `camera.py` y `camera_selector.py` no se modificaron. Recovery
reutiliza `camera_session`. No se selecciona otra cámara ni se guardan cambios.
No se realizó apertura de hardware físico en este servidor.

## 16. CPU/GPU

Resolver y selector sin cambios. Recovery comparte `load_person_model` y
`resolve_effective_device`: CPU por defecto, preferencia CPU, GPU disponible y
fallback temporal a CPU sin reescritura. Las variantes se comprobaron con mocks.
No se ejecutó inferencia física CPU/GPU ni se instaló CUDA.

## 17. Recursos y cierre

Se conservan q, ESC, cierre de ventana, Ctrl+C, `release()` y
`destroyAllWindows()`. Las pruebas ejecutan la sesión de cámara del proyecto
con OpenCV simulado y comprueban liberación ante fallos de modelo, tracking,
lectura, GUI y override inválido. No se duplicó la gestión de recursos.

## 18. Archivos nuevos

- `src/track_recovery.py`
- `config/bytetrack_recovery_capstone.yaml`
- `tests/test_recovery.py`
- `tests/test_recovery_integration.py`
- `docs/05_bytetrack_recovery.md`
- `REPORTE_TRACK_RECOVERY_EXPERIMENTAL.md`

## 19. Archivos modificados

Solo tres archivos anteriores: `src/tracker.py` (override, validación y logs),
`src/track.py` (propagar el argumento opcional) y `README.md` (referencia breve).
Se preservaron los finales de línea originales para evitar reformateo global.

## 20. Archivos preservados

Los 43 archivos anteriores restantes se verificaron idénticos, incluidos todos
los JSON/YAML originales, todos los tests previos, main, detect, detector,
FastTracker, cámara/selectores, dispositivos, diagnostics, config, requirements,
`.gitignore`, reportes históricos, documentación y ajustes de VS Code.
No se eliminó ningún archivo original del proyecto.

## 21. Tests nuevos

**29 tests nuevos**: 21 de pipeline/configuración con mocks, aprobados, y ocho
de integración ByteTrack real, pendientes por dependencias ausentes.
Cubren imports, YAML, .10 exclusivo, .65 en modos anteriores, validación,
relaciones de umbrales, persistencia, una carga y una llamada por frame,
ausencia de predict adicional, dispositivo, no escritura, estado separado,
logs, caja débil visible, métricas/colores y liberación de recursos.

Los ocho tests reales incluyen registro/inicialización, altas débiles rechazadas,
continuidad activa con score bajo, perdido no recuperado por score bajo,
límites low/high, confirmación de tracks y falsos positivos altos persistentes.
No contienen una reimplementación de ByteTrack.

## 22. Tests anteriores

Se conservaron los **201 tests originales** sin editar sus archivos ni aserciones.
Un arnés auxiliar fuera del proyecto permitió ejecutar 191 con OpenCV simulado;
los diez que requieren Ultralytics real/configuración instalada quedaron aparte.
Ese arnés se ejecutó tanto contra una extracción intacta como contra la versión
final. No se incluye ni se activa en el proyecto entregado.

## 23. Compileall

`python -m compileall src tests`: **salida 0**, antes y después.
Imports de `src.tracker`, `src.track`, `src.track_fast` y
`src.track_recovery`: **salida 0**. No cargan IA ni abren cámara al importar.

## 24. Pip check

`python -m pip check`: **salida 0**, antes y después, para las dependencias
presentes en el entorno. Esto **no certifica requirements del proyecto**, porque
OpenCV, Ultralytics, torch, torchvision y lap no están instalados aquí.

## 25. Unittest

| Ejecución | Resultado |
| --- | --- |
| Suite estándar sobre ZIP intacto | Salida 1: 68 ejecuciones, 3 fallos y 8 errores de entorno |
| Suite estándar final | Salida 1: 89 ejecuciones, 3 fallos y 9 errores de entorno |
| Pruebas nuevas locales `test_recovery.py` | 21/21 OK |
| Baseline con OpenCV simulado | 191/191 OK |
| Final con OpenCV simulado | 212/212 OK: 191 previas + 21 nuevas |
| Tests dependientes de instalación real | 18 pendientes: 10 previos + 8 Recovery |

Los tres fallos estándar se deben a entrypoints que devuelven 1 cuando falta
OpenCV. Los errores son imports de cv2 y preparación de integraciones sin
Ultralytics. El único grupo de error agregado es el nuevo setUpClass de
integración Recovery por la misma dependencia ausente. No se ocultaron estos
errores convirtiéndolos en skips o sustituyendo el motor por una copia.
Con todas las dependencias, la suite contiene **230 tests**; no se afirma
haber ejecutado 230/230 ni haber validado la integración real.

## 26. Diagnostics

`python -m src.diagnostics`: **salida 1**, antes y después. Informa Python y
cámara configurada, y luego `No module named 'cv2'`. El módulo no se modificó.
La salida incompleta corresponde al entorno de esta sesión, no a una nueva
incompatibilidad comprobada del proyecto.

## 27. Validación de ByteTrack real

**Pendiente**. Se intentó preparar un entorno temporal con las versiones fijadas;
la política de red bloqueó la descarga y la solicitud de ampliar permisos fue
rechazada automáticamente. No se completó la instalación ni se alteraron
dependencias del proyecto. No se ejecutó el motor real o YOLO con pesos.
Se revisó la referencia oficial actual; el acceso al código de la etiqueta
8.4.163 también falló. No se atribuyen a esa versión comprobaciones no realizadas.
El YAML usa únicamente campos ya admitidos por el baseline y su validador.

## 28. Limitaciones del entorno

Linux x64/Python 3.12.14; objetivo Windows/Python 3.13.15 sin cambiar.
Sin las dependencias de visión/IA, sin cámara, sesión gráfica ni GPU validada.
Las pruebas con mocks verifican el código de integración, no el algoritmo real,
calidad del detector, continuidad física o rendimiento. La aprobación de la
suite completa en el equipo del usuario es el paso pendiente antes de comparar.

## 29. README diff

Ocho líneas agregadas únicamente en comandos: título Recovery, comando,
explicación de umbrales separados y enlace al documento. No se reconstruyó,
reordenó ni reformateó el resto del README.

## 30. Requirements diff

**Idéntico byte por byte**: OpenCV 4.14.0.94, Ultralytics 8.4.163, torch 2.14.0,
torchvision 0.29.0 y lap 0.5.12. Sin paquetes adicionales, nuevos modelos,
actualizaciones ni modificaciones del código interno de Ultralytics.

## 31. Documentación y pruebas pendientes

`docs/05_bytetrack_recovery.md` registra problema, hipótesis, parámetros,
arquitectura, límites, riesgos y REC-01 a REC-10. Incluye una tabla vacía para
repeticiones, continuidad, cambios/intercambios de ID, tracks falsos y rendimiento.
Especial atención a persona detrás de otra, oclusión parcial prolongada y objetos
que antes causaron falsos positivos. Nada se rellenó con mediciones inventadas.
No se confunden estas métricas con precisión IN/OUT.

## 32. ZIP final

`capstone-vision-track-recovery-experimental.zip`: proyecto completo, **52 archivos**,
estructura original `Vision-Artificial/capstone-vision/`, incluido este reporte.
Se comprobó integridad y coincidencia de bytes de los archivos empaquetados.
El ZIP fuente y las preferencias del usuario no se reemplazan.

## 33. Exclusiones locales

Sin `.venv/`, `__pycache__/`, bytecode, pesos `.pt`, `runs/`, `.ultralytics/`,
`config/device.local.json`, medios ni temporales. Se conserva `logs/.gitkeep`.
Los logs y scripts auxiliares usados aquí no se incluyen. Al aplicar los cambios
en el equipo funcional, conservar su entorno, pesos y preferencia local existentes.

## 34. Estado Git

Sin commit, push, cambio de branch ni remote. Se trabajó sobre la extracción
del ZIP recibido. El usuario guardará los cambios con GitHub Desktop después
de las validaciones. No se modificaron archivos personales.

## 35. Comandos exactos

Desde `Vision-Artificial/capstone-vision`, con el entorno existente activo:

```powershell
python -m compileall src tests
python -m pip check
python -m unittest discover -s tests -v
python -m src.diagnostics
python -c "import src.tracker; import src.track; import src.track_fast; import src.track_recovery"
```

Responsabilidades conservadas:

```powershell
python -m src.main
python -m src.camera_selector
python -m src.detect
python -m src.track
python -m src.track_fast
python -m src.track_recovery
python -m src.device_selector
python -m src.diagnostics
```

## 36. Siguiente paso recomendado

Primero ejecutar las validaciones anteriores en el entorno que ya funciona,
especialmente los ocho tests de integración Recovery. Después cerrar ByteTrack
y abrir Recovery con la misma cámara/dispositivo; completar REC-01 a REC-10,
idealmente diez repeticiones de cruces críticos. Comparar IDs y tracks falsos
antes de decidir si Recovery aporta una mejora. No se introdujeron ReID,
zonas, FSM, conteo, Django ni otra tecnología.

Fuentes consultadas: [API ByteTrack](https://docs.ultralytics.com/reference/trackers/byte_tracker/)
y [API Model.track](https://docs.ultralytics.com/reference/engine/model/).
Son referencias actuales; la confirmación ejecutable para 8.4.163 permanece pendiente.
