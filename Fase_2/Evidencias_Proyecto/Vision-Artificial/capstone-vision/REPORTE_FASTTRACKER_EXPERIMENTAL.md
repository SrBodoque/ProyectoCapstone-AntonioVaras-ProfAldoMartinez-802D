# Reporte final — FastTracker experimental

Fecha: 2026-10-09. Fuente: ZIP actual `capstone-vision(2).zip` adjuntado por el usuario.

## 1. Estado general

Integración y validación técnica completadas. `python -m src.track` conserva
ByteTrack estable; `python -m src.track_fast` agrega FastTracker experimental.
Ambos comparten el pipeline existente. No se decide cuál tracker será definitivo.
Los cruces y las oclusiones con cámara/personas reales quedan pendientes.

## 2. Compatibilidad FastTracker confirmada

Antes de modificar se comprobó la instalación exacta: existe el YAML integrado,
`TRACKER_MAP['fasttrack']` apunta a `FASTTracker` y el callback real
`on_predict_start` inicializa esa clase. La confirmación no depende únicamente
de encontrar un archivo YAML. Después se ejecutó también `model.track()` real.
No fue necesario actualizar dependencias ni instalar un tracker externo.

## 3. Versión Ultralytics

Declarada e instalada: **8.4.163**. Sus parámetros específicos se leyeron del
archivo instalado `ultralytics/cfg/trackers/fasttrack.yaml`, antes de implementar.
Entorno de validación aislado: Linux x64, Python **3.12.14**, OpenCV **4.14.0.94**,
PyTorch **2.14.0+cpu**, torchvision **0.29.0+cpu**, lap **0.5.12**.
Los builds CPU conservan las versiones base declaradas; no se alteró el entorno
del computador del usuario. El objetivo documentado Windows/Python 3.13.15 no se
ejecutó aquí.

## 4. Arquitectura implementada

Se reutiliza la inyección existente `PersonTracker(detection_config, tracking_config)`.
No se agregó otro modelo ni se copió el loop. El nuevo entrypoint llama al mismo
`src.track.main()` con un override de ruta y etiqueta. El override es una copia
en memoria del diccionario; no se escribe `tracking.json`.

El validador anterior aceptaba exclusivamente YAML ByteTrack. Por eso el cambio
adicional necesario en `src/config.py` introduce `load_tracker_config` para
ByteTrack/FastTracker y conserva `load_bytetrack_config` como wrapper estricto
ByteTrack. La validación compartida se reutiliza y se rechazan campos extra/ReID.
Se conserva el atributo `bytetrack_config` por compatibilidad con consumidores H3.

`Track`, `FrameTracks`, `TrackHistory`, dibujo, cámara, carga YOLO, resolución de
dispositivo, extracción de IDs, medición de tiempos y cierres siguen compartidos.
Una instancia nueva de modelo por sesión evita transportar estado entre comandos.

## 5. src.track — ByteTrack

Sin argumentos sigue leyendo `config/tracking.json`, que apunta explícitamente a
`config/bytetrack_capstone.yaml`. No depende del default de Ultralytics.
Se conserva el título ByteTrack, overlay, colores, trails, métricas y controles.
El YAML ByteTrack y `tracking.json` son idénticos byte por byte al ZIP original.

## 6. src.track_fast — FastTracker

Nuevo módulo `src/track_fast.py`: selecciona explícitamente
`config/fasttrack_capstone.yaml` y la etiqueta `FastTracker`, y delega en el mismo
main/loop. No incluye selector, cámara, modelo, GPU ni preferencias propios.
El título y la identificación existente permiten distinguir la ejecución.

## 7. Configuración FastTracker

Nuevo `config/fasttrack_capstone.yaml`, con `tracker_type: fasttrack`.
Se resuelve desde la raíz del proyecto, incluso si cambia el directorio actual.
Contiene los seis valores compartidos del baseline y ocho defaults específicos
de la versión instalada. No contiene modelo de apariencia ni opciones ReID.

## 8. Parámetros compartidos con ByteTrack

| Parámetro | ByteTrack | FastTracker |
| --- | --- | --- |
| track_high_thresh | 0.25 | 0.25 |
| track_low_thresh | 0.1 | 0.1 |
| new_track_thresh | 0.25 | 0.25 |
| track_buffer | 30 | 30 |
| match_thresh | 0.8 | 0.8 |
| fuse_score | true | true |

El tipo de tracker difiere intencionalmente. Los parámetros ByteTrack no se ajustaron.

## 9. Parámetros específicos FastTracker

| Parámetro | Default oficial 8.4.163 utilizado |
| --- | --- |
| reset_velocity_offset_occ | 5 |
| reset_pos_offset_occ | 3 |
| enlarge_bbox_occ | 1.1 |
| dampen_motion_occ | 0.5 |
| active_occ_to_lost_thresh | 10 |
| init_iou_suppress | 0.7 |
| occ_cover_thresh | 0.7 |
| occ_reappear_window | 40 |

Se compararon automáticamente contra el YAML de la instalación exacta. Sin tuning.

## 10. Confidence 0.65

`config/detection.json` permanece idéntico. Ambas ejecuciones utilizan **0.65**,
YOLO26n (`yolo26n.pt`), IoU **0.7**, imgsz **640** y clase person **0**.
Se conserva `persist=True` y trails de **30** puntos. No se añadieron reglas
para cama/mochila, filtros de objetos estáticos ni otro umbral para FastTracker.
La advertencia existente sobre filtrado previo a la asociación no cambia el valor.

## 11. ReID

No se agregó ni activó ReID. En la API y en la inferencia real, el FastTracker
creado no tiene encoder de apariencia ni hook de extracción de características.
IDs temporales, procesamiento local y flags `save=False`, `save_txt=False`,
`save_conf=False`, `save_crop=False`, `visualize=False` se conservan. El proyecto
no guarda imágenes, frames, video ni audio, y no sube inferencia a cloud.

## 12. CPU/GPU

`load_person_model` y el resolver existentes se reutilizan sin modificación.
Se verificaron CPU sin preferencia, preferencia CPU, GPU válida simulada y
GPU no disponible con fallback CPU; la preferencia local se conserva.
La ejecución real se realizó en CPU. No hubo hardware CUDA para prueba física GPU.

## 13. camera_selector

Código y configuración de cámara intactos. Ambos entrypoints leen el mismo
`camera.json`: índice **1**, resolución solicitada **1280×720**, FPS solicitados
**60**, backend **auto**. No se creó otro selector y no se escriben esos archivos.
Los 24 tests originales del selector pasan. Los FPS reales no se midieron aquí.

## 14. src.main

Sin cambios. Conserva preview OpenCV/cámara sin incorporar YOLO ni tracker.
Se conservan y pasan los tests H1.

## 15. src.detect

Sin cambios, igual que `src/detector.py`. Continúa como H2 de detección YOLO;
FastTracker no se incorpora a ese comando. Pasan sus 32 tests originales.

## 16. Archivos nuevos

- `src/track_fast.py`
- `config/fasttrack_capstone.yaml`
- `tests/test_fasttracker.py`
- `tests/test_fasttracker_integration.py`
- `docs/04_comparacion_trackers.md`
- `REPORTE_FASTTRACKER_EXPERIMENTAL.md` (este reporte)

## 17. Archivos modificados

| Archivo | Cambio limitado |
| --- | --- |
| src/config.py | Validador compartido para los dos tipos; wrapper ByteTrack conservado |
| src/tracker.py | Leer ambos YAML; etiquetas/logs según tracker; API y llamada de tracking conservadas |
| src/track.py | Override en memoria y etiqueta opcionales en el mismo main/loop |
| README.md | Referencia breve al comando experimental |
| docs/resultados_pruebas.md | Añadir comparación física pendiente sin alterar historia |

No se removió ningún archivo de código/documentación original.

## 18. Archivos no modificados deliberadamente

Comparación binaria contra el ZIP original confirmó iguales: `requirements.txt`,
`.gitignore`, `config/camera.json`, `config/detection.json`, `config/tracking.json`,
`config/bytetrack_capstone.yaml`, `src/main.py`, `src/camera.py`,
`src/camera_selector.py`, `src/devices.py`, `src/device_selector.py`,
`src/detector.py`, `src/detect.py`, `src/diagnostics.py` y todos los tests previos.
También se conservaron los documentos/reportes históricos. El checkpoint adjunto
permaneció idéntico durante la validación y se excluye de la entrega solicitada.

## 19. README diff

Únicamente en la sección de comandos: el título existente pasa a «Tracking
ByteTrack estable» y se agregan el comando FastTracker experimental y un párrafo
breve con objetivo/link al procedimiento. El resto del README no se reorganizó
ni reformateó. No se declara tracker definitivo.

## 20. Requirements diff

**Sin diferencias byte por byte**. Se conserva:

```text
opencv-python==4.14.0.94
ultralytics==8.4.163
torch==2.14.0
torchvision==0.29.0
lap==0.5.12
```

No se agregó ningún paquete FastTracker externo ni se actualizó Ultralytics.

## 21. Tests nuevos

**24 tests**: 19 en `test_fasttracker.py` y 5 en
`test_fasttracker_integration.py`. Cubren imports livianos; selección explícita
de los dos YAML; defaults oficiales/validación; persist/person/confianza;
una carga de modelo y una llamada `track` por frame; ausencia de doble predict;
cajas sin ID; dispositivo/fallback; configuración de cámara sin escritura;
modelos separados; mismos colores/métricas; cierres q/ESC/ventana/Ctrl+C y
excepciones de carga/tracking/lectura/GUI.

Los cinco tests reales usan Ultralytics instalado: registro e inicialización
por callback, IDs en movimiento sintético, ausencia/reaparición, estado nuevo y
historial interno acotado. No requieren webcam, GPU ni descargar pesos.
Los tests previos continúan comprobando `TrackHistory` acotado.

## 22. Tests previos

Se conservaron los **177 tests** y sus archivos originales sin modificación.

| Módulo anterior | Tests |
| --- | --- |
| test_camera_selector | 24 |
| test_device_optional | 28 |
| test_device_selector | 35 |
| test_hito1 | 16 |
| test_hito2 | 32 |
| test_hito3 | 38 |
| test_hito3_integration | 4 |

## 23. Resultado unittest

Baseline anterior a cambios: **177/177 OK**. Final: **201/201 OK**, sin fallos ni
tests omitidos. Comando: `python -m unittest discover -s tests -v`.
No se atribuyeron fallos preexistentes a la tarea; el baseline pasó íntegro.

## 24. Resultado compileall

`python -m compileall src tests`: **OK, salida 0**, antes y después.
Imports de `src.tracker`, `src.track` y `src.track_fast`: **OK**.
Los imports no cargan modelos, abren cámara, piden selección ni escriben configs.

## 25. Resultado pip check

`python -m pip check`: **OK, salida 0**, antes y después.
Resultado: `No broken requirements found.`

## 26. Resultado diagnostics

`python -m src.diagnostics`: **OK, salida 0**, antes y después. Sigue reportando
ByteTrack como baseline, modelo/confianza originales, CPU base/efectiva y
ausencia de preferencia local. Detectó correctamente las versiones instaladas.
Conserva avisos de este entorno: Python 3.12.14 frente al objetivo 3.13.15,
PyTorch sin CUDA y confianza 0.65 previa a la asociación. No se cambió diagnostics
para convertirlo en un nuevo selector o benchmark.

## 27. Prueba FastTracker real

Además de los cinco tests con cajas sintéticas, se cargó el **checkpoint adjunto
real** mediante `PersonTracker`. Se procesaron dos cuadros negros sintéticos
1280×720 por sesión en CPU: una sesión `BYTETracker` y otra `FASTTracker`.
Se confirmó la clase efectiva, dos actualizaciones, conf 0.65, IoU 0.7,
imgsz 640, person 0, modelos/trackers distintos y ausencia de encoder/hook ReID.
No hubo personas ni detecciones en esos cuadros y no se guardaron medios.

SHA-256 del checkpoint antes/después idéntico:
`9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`.
Esta prueba demuestra integración real; no mide continuidad física de IDs ni FPS.

## 28. Regresión ByteTrack

Pasaron **38 tests H3 + 4 de ByteTrack real** y la inferencia real CPU indicada.
La revisión de diff confirmó llamada `model.track`, extracción de IDs, drawing,
timing y controles conservados. El comando sin argumentos mantiene la ruta
explícita original y el mismo título/overlay. No se ajustaron parámetros ni IDs.

## 29. Regresión H1

**16 tests H1 + 24 de camera_selector OK**. Módulos y configuración de cámara
intactos. La prueba física del visor en Windows queda para el computador del usuario.

## 30. Regresión H2

**32 tests H2 OK**. Detector, entrypoint, modelo/confianza/IoU/clase y resolución
de dispositivo conservados. No se incorporó tracking a la detección.

## 31. Regresión CPU/GPU

**28 tests device_optional + 35 device_selector OK**, más nuevos casos del
pipeline FastTracker. CPU continúa siendo base, GPU es opcional por computador,
y el fallback no borra ni reescribe la preferencia local. GPU física pendiente.

## 32. Limitaciones

No se contó con cámara/personas reales, sesión gráfica ni GPU NVIDIA aquí.
Ambos comandos de tracking salen con código 1 y el mismo mensaje esperado
«No hay sesión gráfica disponible» en este entorno headless. Eso se distingue
de las comprobaciones positivas de módulos, mocks y API/inferencia real CPU.
No se midieron cruces, intercambios de IDs ni rendimiento comparativo.
Las pruebas se hicieron en Linux/Python 3.12.14; Windows/Python 3.13.15 queda pendiente.

## 33. Pruebas físicas pendientes

Preparadas en `docs/04_comparacion_trackers.md`: FT-01 una persona; FT-02 dos
sin cruce; FT-03 cruce rápido; FT-04 lento; FT-05 detrás de otra persona;
FT-06 oclusión parcial; FT-07 completa corta; FT-08 idealmente diez repeticiones
por caso crítico y tracker. Registrar IDs antes/después, duración, mantiene/cambia
ID y métricas actuales, con cámara, luz, hardware y dispositivo iguales.

## 34. Tabla de comparación pendiente

| Escenario | ByteTrack mantiene ID | FastTracker mantiene ID |
| --- | --- | --- |
| Cruce rápido | Usuario completa | Usuario completa |
| Cruce lento | Usuario completa | Usuario completa |
| Detrás de persona | Usuario completa | Usuario completa |
| Oclusión parcial | Usuario completa | Usuario completa |
| Oclusión completa corta | Usuario completa | Usuario completa |

No se rellenaron resultados ni se declaró un ganador.

## 35. ZIP final

`capstone-vision-fasttracker-experimental.zip`, con raíz `capstone-vision/` y
**46 archivos** de proyecto/documentación, incluido este reporte. Se revisaron
todos los cambios contra el ZIP adjunto y la integridad del archivo final.
Excluye `.venv/`, `__pycache__/`, bytecode, `.pt`, `runs/`, `.ultralytics/`,
logs temporales, imágenes y videos. Conserva `logs/.gitkeep` y los reportes
históricos. Los scripts/logs auxiliares de validación no forman parte del ZIP.

El checkpoint se omite según lo solicitado: al probar en el proyecto original,
conservar su `yolo26n.pt` existente y su entorno virtual.

## 36. Confirmación device.local.json excluido

`config/device.local.json` no está incluido en el ZIP. No se creó ni modificó
la preferencia real del usuario. Se comprobó la conservación mediante tests
con archivo temporal separado. `.gitignore` permanece idéntico.

## 37. Estado Git

No se realizó commit, push, cambio de branch ni cambio de remote.
Se trabajó directamente sobre una extracción del ZIP actual. No se afirmó
sincronización adicional con GitHub; el usuario hará su commit después de probar.

## 38. Comandos exactos

Desde la raíz del proyecto y con el entorno existente activo:

```powershell
# Preview H1
python -m src.main
# Selector de cámara
python -m src.camera_selector
# Detección H2
python -m src.detect
# ByteTrack estable
python -m src.track
# FastTracker experimental
python -m src.track_fast
# Selector CPU/GPU
python -m src.device_selector
# Diagnóstico
python -m src.diagnostics
```

Validación reproducible:

```powershell
python -m compileall src tests
python -m pip check
python -m unittest discover -s tests -v
python -m src.diagnostics
python -c "import src.tracker"
python -c "import src.track"
python -c "import src.track_fast"
```

## 39. Siguiente paso

En el mismo computador/cámara, ejecutar ByteTrack, cerrarlo con q/ESC y luego
FastTracker. Completar FT-01 a FT-08 y la tabla pendiente, especialmente FT-05.
Conservar confianza 0.65 y todas las condiciones; comparar continuidad de IDs y
métricas antes de decidir tracker o tuning. No se agregó selector persistente,
paleta por ID, optimización de rendimiento ni Hito 4.

Referencias primarias consultadas: [tracking oficial de Ultralytics](https://docs.ultralytics.com/modes/track/)
y [API FastTracker](https://docs.ultralytics.com/reference/trackers/fast_tracker/).
Los defaults entregados y la compatibilidad se verificaron en la instalación
exacta 8.4.163; las páginas generales pueden describir versiones más recientes.
