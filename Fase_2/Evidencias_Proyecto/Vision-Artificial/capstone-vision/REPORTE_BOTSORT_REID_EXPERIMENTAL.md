# Informe de entrega — BoT-SORT + ReID experimental

Fecha: 23-10-2026. Fuente única: `Vision-Artificial(2).zip` adjunto, con 52 archivos
originales y estructura `Vision-Artificial/capstone-vision/`.

**Código integrado y pruebas simuladas aprobadas. Validación real de ReID pendiente.**
No se declara superada la aceptación funcional completa: no se pudo ejecutar
Ultralytics, inicializar el extractor real ni medir FPS en este entorno.

## 1. Estado de la implementación

Existe el cuarto modo experimental, separado de los anteriores, con controles de
ReID durante la ejecución. No basta con activar el YAML: el programa comprueba
instancia, encoder, características y paso a asociación. La validación con modelos
reales está bloqueada por dependencias ausentes; las pruebas físicas están pendientes.
No se implementaron zonas, FSM, conteo, eventos IN/OUT ni integración backend.

## 2. Archivos inspeccionados

Se inventarió y comparó el ZIP completo. Se revisaron `src/config.py`, `tracker.py`,
`track.py`, `track_fast.py`, `track_recovery.py`, `detector.py`, cámara, dispositivos
y diagnóstico; los seis archivos de configuración existentes, `requirements.txt`,
README y documentación de los hitos, selectores, FastTracker y Recovery. Se revisó
la suite existente, sus casos de regresión y los patrones de integración real.
Los informes históricos se conservaron como antecedentes, sin convertir sus
resultados en evidencia de esta entrega.

## 3. Archivos creados

| Archivo | Propósito |
| --- | --- |
| `src/track_botsort_reid.py` | Entrada pequeña que delega al loop compartido. |
| `config/botsort_reid_capstone.yaml` | Configuración experimental exacta. |
| `src/reid_diagnostics.py` | Comprobaciones de ReID, aisladas del núcleo y de los otros modos. |
| `tests/test_botsort_reid.py` | 43 pruebas con dobles explícitos. |
| `tests/test_botsort_reid_integration.py` | 10 pruebas reales, con requisitos y omisiones explícitas. |
| `docs/06_botsort_reid.md` | Uso, interpretación, límites y protocolo BOT-01 a BOT-15. |
| `REPORTE_BOTSORT_REID_EXPERIMENTAL.md` | Este informe de 40 puntos. |

## 4. Archivos modificados

Solo `src/config.py`, `src/tracker.py` y `README.md`. Se conservaron los finales de
línea originales. No fue necesario modificar `src/track.py` ni duplicar su loop.

## 5. Archivos preservados

**49 de los 52 archivos originales permanecen idénticos byte a byte.** Incluye
todos los tests anteriores; `requirements.txt`; `detection.json`, `tracking.json`,
`camera.json`; los tres YAML originales; los módulos FastTracker y Recovery;
detector, preview, cámara, selectores, dispositivos y diagnóstico. No se creó ni
se escribió `device.local.json`. No hubo commit, push, cambios de rama, remotes
ni configuración global de Git.

## 6. Arquitectura utilizada

La entrada nueva inyecta ruta YAML y etiqueta en `track.main`. El mismo
`run_tracking` administra captura, dibujo, métricas y cierre. `PersonTracker`
conserva el cargador compartido y una llamada a `model.track` por frame.
El módulo diagnóstico se activa únicamente para `botsort`; no interviene en los
otros modos. Observa la instancia oficial, sin copiar la implementación del tracker.

## 7. Nuevo comando

```powershell
python -m src.track_botsort_reid
```

Se ejecuta desde `capstone-vision`, con el entorno existente activo. No pregunta
por cámara o dispositivo; utiliza las preferencias ya seleccionadas. Título:
`CAPSTONE - BoT-SORT + ReID - q / ESC para salir`.

## 8. YAML final

```yaml
tracker_type: botsort
track_high_thresh: 0.25
track_low_thresh: 0.10
new_track_thresh: 0.25
track_buffer: 30
match_thresh: 0.80
fuse_score: true
gmc_method: none
proximity_thresh: 0.50
appearance_thresh: 0.80
with_reid: true
model: auto
```

Sin ajuste automático. Los parámetros compartidos coinciden con ByteTrack original.
La aceptación del YAML por la instalación exacta 8.4.163 está cubierta por una
prueba real preparada, aún no ejecutada.

## 9. Validaciones añadidas en config.py

Se admite `botsort` con exactamente los siete campos comunes y sus cinco campos
específicos. Proximidad y apariencia deben ser números finitos entre 0 y 1;
`with_reid` debe ser el booleano `true`; `model` solo puede ser `auto`. Se rechazan
campos faltantes, extras, rutas arbitrarias y métodos GMC desconocidos. Se admiten
`none`, `sparseOptFlow`, `orb`, `sift`, `ecc`. Se mantiene `low < high` y para
BoT-SORT se exige `new >= high`. Continúan los límites de buffer y `fuse_score`
booleano. `load_bytetrack_config` sigue aceptando exclusivamente ByteTrack;
las reglas previas de FastTracker y Recovery se conservan.

## 10. Modificaciones en PersonTracker

Añade etiqueta `BoT-SORT + ReID` y el diagnóstico de sesión. El modo nuevo rechaza
un override de Recovery y exige confianza general 0.65. Se mantienen `Track`,
`FrameTracks`, `track_id`, BGR, tratamiento de cajas sin ID y el alias histórico
`bytetrack_config`. No se cambian asociaciones, IDs o cajas para aparentar continuidad.

## 11. Comportamiento de model.track()

Una llamada por frame, con el YAML explícito, clase `[0]`, persistencia `True`,
IoU 0.7, imgsz 640 y dispositivo efectivo del cargador común. Se conservan las
opciones de no guardado, no visualización interna y no augment. El detector no se
invoca aparte mediante `predict`. El extractor oficial puede inferir sobre recortes
internos de apariencia; ese trabajo adicional no es otro pase del detector principal.

## 12. Confianza efectiva

| Modo | Confianza YOLO |
| --- | --- |
| Detección | 0.65 |
| ByteTrack original | 0.65 |
| FastTracker | 0.65 |
| Recovery | 0.10, override de sesión |
| BoT-SORT + ReID | 0.65, sin override |

Observaciones inferiores a 0.65 se filtran antes de BoT-SORT. Su segunda asociación
no recibe esas detecciones débiles. ReID no puede recuperar una detección inexistente.

## 13. Confirmación de BoT-SORT real

**Pendiente en este entorno.** Durante la ejecución, el control exige una única
instancia cuyo tipo sea exactamente el `BOTSORT` importado de Ultralytics 8.4.163;
comprueba además `tracker_type`. Una configuración que termine usando ByteTrack
se rechaza. El test simulado demuestra el control, no la creación del motor real.

## 14. Confirmación de ReID activo

**Pendiente de ejecución real.** Se comprueba `with_reid is True`, encoder invocable,
características válidas y ejecución del método oficial de distancias con tracks
y detecciones. El mensaje “ReID activo verificado” solo se emite después de esa
última evidencia. No implica que apariencia decida cada asignación ni prueba una
mejora de calidad. Sin personas, extracción/asociación permanecen pendientes.

## 15. Modelo ReID configurado

`auto`, como solicitó el encargo. No se introduce una segunda variante ni rutas
arbitrarias de modelos. La resolución concreta corresponde a Ultralytics.

## 16. Modelo ReID efectivo

**No observado aquí.** Se espera `yolo26n-cls.pt` para YOLO26n end-to-end, conforme
al encargo y la documentación oficial consultada. Es un clasificador que aporta
características de apariencia, no un extractor especializado en personas. La
aplicación inspecciona el modelo realmente inicializado antes de anunciarlo.
La rama nativa exige el hook de características del detector.

## 17. Evidencia de inicialización del extractor

No existe evidencia de inicialización real en esta ejecución. El control preparado
verifica el encoder, modelo efectivo, tarea de clasificación, checkpoint y
predictor de apariencia inicializado. También contrasta el dispositivo con el del
detector. Rechaza encoder ausente, modelo inesperado o predictor sin inicializar.
Las pruebas unitarias ejercitan esas condiciones con dobles.

## 18. Evidencia de extracción y asociación

No se extrajeron embeddings reales aquí. El diagnóstico observa los resultados
originales de `init_track`: una trayectoria con `curr_feat` y `smooth_feat` válidas
por detección. Contrasta la cantidad con las detecciones observadas antes del
tracking. Verifica características de tracks actuales y entradas/salida de
`get_dists`. Si hay tracks previos y detecciones, exige observar asociación.

Las pruebas reales preparadas incluyen: motor con características sintéticas,
cambio del coste al habilitar apariencia y observación de `embedding_distance`
real; y dos frames de la muestra oficial con detección y extracción aprendida.
No se sustituyen los cálculos reales en esas pruebas. Todos estos casos quedaron
pendientes por el entorno.

## 19. Límites de auto y compatibilidad de versión

`auto` puede implicar un modelo adicional y no garantiza coste mínimo. La versión
8.4.163 no está instalada aquí. Los tres enlaces GitHub a esa etiqueta y el enlace
raw consultado no pudieron recuperarse (`DisabledError`). Las referencias oficiales
accesibles reflejan `main`, por lo que no prueban equivalencia exacta de versión.

Se exige 8.4.163 al ejecutar el modo nuevo y se falla si sus APIs no permiten
verificar ReID. No se declara una inspección local ni compatibilidad real ya
comprobada. No se actualizaron dependencias para sortear esta limitación.

## 20. CPU/GPU

Se reutiliza `resolve_effective_device`: CPU por defecto o preferencia CUDA válida,
con fallback existente ante GPU local no utilizable. Las pruebas simuladas cubren
CPU, CUDA y fallback sin modificar preferencias. El diagnóstico contrasta el
dispositivo del predictor de clasificación con el efectivo del detector; un
mismatch termina la sesión. La propagación real a ambos modelos queda pendiente.
No se fuerza una GPU fija ni se modifica el selector.

## 21. GTX 1650 y VRAM

Se acepta la evidencia aportada por el usuario: PyTorch 2.14.0+cu132, build CUDA
13.2, operación en cuda:0 y ByteTrack aproximadamente 18–24 FPS. No se repitió aquí.
ReID añade carga de inferencia y puede aumentar VRAM en una tarjeta de 4 GB.
Medir con varias personas, después del calentamiento. No hay promesa de 20 FPS,
medición de memoria ni activación de FP16/TensorRT en esta entrega.

## 22. Embeddings temporales

La apariencia permanece en el estado de la sesión de Ultralytics. El diagnóstico
no crea colecciones de embeddings ni conserva copias. Retención de tracks perdidos
y retirados depende de las listas y reglas internas; `track_buffer=30` no es una
garantía de borrado a un segundo exacto. El cierre del proceso libera ese estado.
No se implementa reutilización de identidad entre sesiones o cámaras.

## 23. Privacidad

No se incorporan reconocimiento facial, nombres, perfiles, base de datos de
apariencia, transmisión de características, fotos, videos ni recortes guardados.
Se conservan las opciones de guardado desactivado, telemetría desactivada y
prohibición de autoinstalación del cargador previo. La descarga oficial de pesos
es independiente del procesamiento local de los frames. Los tests con imágenes
usan únicamente la muestra oficial si está disponible; no fotografías del usuario.

## 24. Tests nuevos

**43 pruebas unitarias con dobles: aprobadas.** Cubren configuración, rechazo de
ReID falso, extracción inválida/ausente, asociación ausente, mensajes por etapas,
modelo efectivo, dispositivos, comando compartido, privacidad, formatos y liberación
ante cierres y fallos.

**10 pruebas reales preparadas: no ejecutadas.** Siete de motor/álgebra y tres de
inferencia con pesos. Unittest muestra dos clases omitidas (`skipped=2`), que
agrupan esos diez casos; no son dos tests aprobados.

## 25. Tests anteriores

Los 11 archivos de pruebas anteriores se mantienen idénticos. Un arnés externo,
fuera del ZIP, simuló explícitamente OpenCV para poder ejecutar las regresiones
sin instalar paquetes: **212 antes y 212 después, todas aprobadas**. Se conservaron
sus mocks de inferencia. No es una prueba de OpenCV real, motores reales o hardware.
Los 18 casos anteriores que requieren la biblioteca real siguen pendientes.

## 26. Importaciones

Aprobadas las importaciones de `src.track`, `src.track_fast`, `src.track_recovery`
y `src.track_botsort_reid`. El test de importación nueva comprueba que no carga
PyTorch, Ultralytics, OpenCV, PyYAML ni NumPy, no solicita entrada y no escribe
configuraciones. Importar un comando no equivale a ejecutar inferencia.

## 27. Compileall

`python -m compileall src tests`: código de salida **0** antes y después.
Se excluyeron los bytecodes generados del ZIP.

## 28. Pip check

`python -m pip check`: código de salida **0** antes y después, “No broken
requirements found”. Solo informa consistencia de los paquetes instalados en el
runtime; **no certifica que requirements.txt esté instalado**. Las dependencias
principales del proyecto faltan.

## 29. Unittest

| Ejecución | Resultado observado |
| --- | --- |
| Suite normal antes de editar | 89 reportados; 3 fallos, 9 errores; salida 1 |
| Suite normal después | 132 reportados; 3 fallos, 9 errores, 2 clases omitidas; salida 1 |
| Solo pruebas nuevas | 43 ejecutadas OK; 2 clases reales omitidas |
| Arnés externo OpenCV simulado antes | 212 OK; 18 casos reales apartados |
| Arnés externo OpenCV simulado después | 255 OK = 212 anteriores + 43 nuevos; 28 casos reales apartados |

Los números de la suite normal incluyen marcadores de módulos que no pudieron
importarse; no representan toda la suite. Los mismos nueve errores antes/después
son cinco módulos sin cv2, una prueba de fallback sin cv2 y tres `setUpClass` sin
Ultralytics. Los tres fallos son aserciones previas de entrypoints que esperaban
éxito, pero reciben error al faltar cv2 (`main_never_resolves_or_loads_inference`
y dos subcasos de `existing_commands_read_base_without_selecting`). No aparecieron
fallos nuevos en las regresiones simuladas.

## 30. Diagnostics

`python -m src.diagnostics`: salida **1** antes y después por `No module named
'cv2'`. Informa Python 3.12.14 Linux x86_64 y cámara configurada índice 1,
1280×720, 60 FPS solicitados, backend auto. No abre webcam sin `--scan`.
No se modificó el módulo para ocultar la carencia del entorno.

## 31. Límites del entorno

Python disponible 3.12.14 frente al objetivo 3.13.15. Ausentes cv2, Ultralytics,
torch, torchvision y lap. PyYAML/NumPy sí disponibles. No hay pesos de detector ni
clasificador en la entrega, ni se pudo inicializar un encoder. No hubo inferencia
real, pruebas con webcam, CUDA o GTX 1650. No se instalaron paquetes, se modificó
el entorno del usuario ni se intentó eludir las restricciones de descarga conocidas.
Las referencias oficiales actuales no sustituyen el código exacto instalado.

## 32. README diff

Se insertaron exclusivamente ocho líneas antes de “Diagnóstico”: un subtítulo,
el comando y un párrafo que explica experimento, confianza 0.65, cámara/dispositivo,
modelo adicional, comprobaciones y enlace a la guía. No se eliminó ni reformateó
contenido previo. Las instrucciones CUDA se conservaron. La mención histórica a
GTX 1650 pendiente en el README anterior no se reescribió; el dato actualizado del
usuario consta en este informe y la guía nueva.

````diff
+### Tracking BoT-SORT + ReID experimental
+
+```powershell
+python -m src.track_botsort_reid
+```
+
+Experimento con ReID temporal por apariencia, confianza **0.65** y la cámara y dispositivo ya seleccionados. Puede requerir el modelo oficial adicional `yolo26n-cls.pt`; comprueba el encoder, las características y su paso a la asociación durante la ejecución. Eficacia y rendimiento pendientes de pruebas físicas: [BoT-SORT + ReID](docs/06_botsort_reid.md).
+
````

## 33. Requirements diff

**Sin diferencias byte a byte.**

```text
opencv-python==4.14.0.94
ultralytics==8.4.163
torch==2.14.0
torchvision==0.29.0
lap==0.5.12
```

SHA-256 del archivo preservado:
`7e0beeb2827c3a83007226d711711fc1485ceb778acbcda236f2daf6335a57e9`.
No se alteraron builds CUDA, instalación ni requisitos de CPU/GPU.

## 34. Recovery intacto

Su módulo, YAML, documentación y tests están idénticos. Conserva override 0.10,
high/new 0.65, low 0.10, buffer 30, etiqueta, loop y métricas. El mecanismo del
override en `PersonTracker` y `track.py` sigue disponible sin cambios de semántica
para los modos previos. Sus 21 pruebas con dobles pasan; ocho reales pendientes.

## 35. ZIP final

`capstone-vision-botsort-reid-experimental.zip`: proyecto completo, estructura
original conservada, 59 archivos. Incluye los siete archivos nuevos y los 52
originales, con las tres modificaciones declaradas. El informe también se entrega
por separado para leer sin extraer el proyecto.

## 36. Exclusiones

Sin `.venv`, `__pycache__`, bytecodes, pesos `.pt`/`.pth`, ONNX, engines, preferencias
locales de dispositivo, fotos, videos, caches, `.ultralytics`, `runs`, temporales
ni el arnés externo de simulación. Se conservaron `.gitignore`, configuración de
VS Code y `logs/.gitkeep` recibidos. No se eliminó ningún archivo original necesario.

## 37. Comandos exactos

Desde la carpeta `capstone-vision`, usando el entorno ya funcional, sin reinstalar
PyTorch/CUDA:

```powershell
python -c "import ultralytics; print(ultralytics.__version__)"
python -m compileall src tests
python -m pip check
python -m unittest discover -s tests -v
python -m src.diagnostics
python -c "import src.track"
python -c "import src.track_fast"
python -c "import src.track_recovery"
python -c "import src.track_botsort_reid"
python -m unittest discover -s tests -p "test_botsort_reid*.py" -v
python -m src.track_botsort_reid
```

La prueba real de inferencia busca ambos pesos oficiales en la raíz y `bus.jpg`
incluida por Ultralytics. Omite con motivo explícito si faltan; no descarga ni
instala automáticamente. La ejecución interactiva puede descargar pesos oficiales
por el mecanismo normal de Ultralytics. Cerrar el visor antes de comparar:

```powershell
python -m src.track
python -m src.track_fast
python -m src.track_recovery
```

Los selectores existentes siguen disponibles si se necesita cambiar una elección:
`python -m src.camera_selector` y `python -m src.device_selector`. No es requisito
volver a seleccionar ni crear un entorno nuevo.

## 38. Pruebas físicas

BOT-01 a BOT-15 están documentadas individualmente y todas pendientes en
`docs/06_botsort_reid.md`: caminar, detenerse, dos personas separadas, cruces rápidos
y lentos, pasar detrás, oclusiones parciales y completas, ropa similar, salir y
volver, falsos positivos, tres personas, GPU y comparación con ByteTrack.

Repetir los casos críticos manteniendo condiciones. Registrar IDs antes/después,
intercambios, recuperación, FPS, ms YOLO, ms totales, cajas sin ID, tracks falsos,
detecciones perdidas y dispositivo. No guardar imágenes ni vectores. La diferencia
de tiempo entre modos incluye más factores que el extractor; no llamarla coste
puro de ReID sin instrumentación adicional. No hay porcentajes de mejora inventados.

## 39. Riesgos y fallos pendientes

Bloqueo principal: falta ejecutar la integración en 8.4.163 con los pesos reales.
Debe comprobarse allí el orden de callbacks, atributos del encoder y propagación
de dispositivo. Los controles fallan explícitamente ante incompatibilidades;
no ocultan un modo sin ReID. La extracción de clasificación puede confundir ropa
parecida, iluminación y ángulos. La proximidad puede impedir un match aun con
apariencia similar. Oclusión total/ausencia prolongada no garantiza continuidad.
Aumentar retención podría asociar personas incorrectas; no se ajustó. VRAM/FPS
están pendientes. Los fallos normales de la suite por dependencias ya existían.
No se corrigieron asuntos ajenos al encargo.

## 40. Recomendación técnica

Primero ejecutar los tests reales y el nuevo comando en el entorno ya validado
del usuario. Confirmar las tres evidencias de consola (inicialización, extracción,
asociación) antes de aceptar ReID funcional. Si falla una, conservar el error
textual, sin fotos ni embeddings, y resolver esa incompatibilidad antes de comparar.
Después repetir BOT-04/05/06/08/10/13 contra ByteTrack con conf 0.65. Elegir tracker
a partir de continuidad correcta y coste observado; no por menos IDs o más cajas.
Mantener este modo como experimento hasta obtener esos resultados.

### Fuentes consultadas

Documentación oficial de [tracking](https://docs.ultralytics.com/modes/track/),
[callbacks](https://docs.ultralytics.com/reference/trackers/track/),
[BoT-SORT](https://docs.ultralytics.com/reference/trackers/bot_sort/),
[ReID](https://docs.ultralytics.com/reference/trackers/utils/reid/) y
[GMC](https://docs.ultralytics.com/reference/trackers/utils/gmc/), consultada el
23-10-2026. El comportamiento exacto de la instalación fijada sigue pendiente.
Los enlaces de versión solicitados y su limitación se detallan en la guía del
experimento; no se atribuye evidencia de ejecución a estas páginas.
