# HigieneSmart — Reporte Hito 4: calibrador visual y zonas persistentes

Fecha de trabajo: 27 de octubre de 2026 en Chile / registros del entorno del 28 de octubre UTC.

Fuente de verdad: `capstone-vision(4).zip`, adjunto actualizado. El contenido coincide exactamente con la entrega anterior utilizada para registrar el baseline: mismos 70 archivos y mismos bytes. Este informe distingue implementación, pruebas simuladas y aceptación física.

## 1. Estado general del Hito 4

Implementación terminada mediante archivos nuevos. Se pueden crear, editar, guardar y activar perfiles de dos polígonos; el nuevo visualizador integra sus posiciones con el tracker existente. Se completaron tres ejecuciones independientes de la batería automatizada disponible, todas satisfactorias. **La aceptación física y la suite con dependencias reales siguen pendientes.** No se declara el hito completamente validado en cámara o GPU.

## 2. Archivos inspeccionados

Se leyó `AGENTS.md`, el encargo y el ZIP completo; se inspeccionaron `README.md`, `requirements.txt`, los JSON/YAML existentes y los módulos `config`, `camera`, `camera_selector`, `devices`, `device_selector`, `detector`, `tracker`, `detect`, `track`, los tres puntos de entrada de trackers experimentales y sus tests. También se revisaron las incorporaciones MP4 presentes en la fuente (`process_videos`, `video_source`, `video_runner`, `video_results` y sus pruebas), para conservarlas y cubrir su regresión. Se consultó la documentación oficial de HighGUI de OpenCV para los eventos y ventanas, sin instalar OpenCV en este entorno.

El ZIP no contiene metadatos `.git`; la inspección Git indicó que no era un repositorio. No se creó uno ni se realizó ninguna operación de ramas, commits, push o configuración global. La inspección final se realizó mediante comparación de contenido con el ZIP fuente, no mediante un `git diff` inexistente.

## 3. Archivos creados

| Archivo nuevo | Función |
| --- | --- |
| `src/zones.py` | Geometría, perfiles, validación, persistencia, clasificación, observaciones y dibujo de regiones |
| `src/zone_calibrator.py` | Editor visual OpenCV sin cargar IA |
| `src/track_zones.py` | Integración pequeña con la cámara y BoT-SORT + ReID existentes |
| `config/zones/.gitignore` | Exclusión local de perfiles y temporales |
| `tests/test_zones.py` | 29 tests de geometría, persistencia y observaciones |
| `tests/test_zone_calibrator.py` | 19 tests del editor y su ciclo de cámara |
| `tests/test_track_zones.py` | 11 tests de integración y presentación simuladas |
| `tests/zone_test_support.py` | Dobles de cámara/GUI y datos sintéticos para los tests nuevos |
| `tests/hito4_simulated_regression.py` | Arnés auxiliar explícitamente simulado y reproducible |
| `docs/hito4_zonas.md` | Guía de uso y plan físico ZON-01 a ZON-17 |
| `REPORTE_HITO4_ZONAS.md` | Este reporte de entrega |

Total: **11 archivos nuevos**. No se distribuyen JSON de calibraciones ficticias ni reales.

## 4. Archivos anteriores intactos

Los **70 archivos originales** se compararon byte por byte con el ZIP actualizado y permanecen intactos. La comprobación comprende módulos, pruebas, documentación, README, requirements, configuraciones, selectores, `.gitignore` raíz y los módulos MP4 preexistentes. No se reemplazaron interfaces ni se revirtieron ajustes del usuario. El ZIP final contiene los 70 originales más los 11 nuevos, bajo `capstone-vision/`.

## 5. Diseño del calibrador

`CalibrationEditor` separa las operaciones de edición de la cámara y la representación visual. El ciclo usa `camera_session` existente, una vista previa proporcional y las ventanas/eventos de OpenCV. La geometría está centralizada en `zones.py`. El calibrador importa OpenCV solo al ejecutar la aplicación y no importa YOLO, PyTorch ni Ultralytics. El frame congelado permanece exclusivamente en RAM.

## 6. Instrucciones del mouse

Clic izquierdo agrega vértices del contorno abierto. Arrastrar un vértice de la zona seleccionada cambia su posición, incluso con contorno cerrado. Clic derecho valida y cierra. Se ignoran los clics fuera de la imagen, sobre la ayuda o durante una confirmación. No hay que repetir el primer punto al cerrar. El límite es de 16 vértices por zona.

## 7. Atajos de teclado

| Tecla | Acción |
| --- | --- |
| A / B | Seleccionar zona |
| Enter | Cerrar contorno; en nombre confirma guardado; en lista carga perfil |
| U / Retroceso | Quitar último vértice; en nombre, borrar carácter |
| R | Redibujar zona; con incompatibilidad, recalibrar ambas |
| Espacio | Congelar/reanudar imagen |
| S | Validar, nombrar, guardar y activar |
| P | Lista de perfiles |
| J / K o ] / [ | Recorrer perfiles |
| G | Activar perfil revisado y compatible |
| N | Nuevo perfil |
| Q / Esc | Salir desde edición; Esc cancela las operaciones modales |
| Y / N | Confirmar/cancelar descarte o sobrescritura |

El cierre X y Ctrl+C durante la edición también solicitan confirmación cuando hay cambios. La ventana debe tener el foco para recibir teclas. Los mensajes muestran la zona elegida, número de vértices, perfil y estado pendiente.

## 8. Cómo crear Zona A

Ejecutar `python -m src.zone_calibrator`, pulsar A y marcar ordenadamente el espacio próximo al umbral. Usar tres o más puntos y cerrar con Enter o clic derecho. El relleno azul/celeste permite revisar la alineación sobre la imagen.

## 9. Cómo crear Zona B

Pulsar B y dibujar la zona exterior o de aproximación. Su relleno es naranja. Puede quedar separada de A o compartir un borde; sus interiores no pueden superponerse. No existe una tercera línea de cruce.

## 10. Cómo editar una zona

Reabrir el calibrador carga la calibración activa. Seleccionar A/B y arrastrar vértices para ajustar tamaño, posición o forma. U quita el último punto y reabre; R borra la zona seleccionada. Se pueden agregar puntos al contorno abierto y cerrarlo otra vez. Salir descartando no modifica lo guardado.

## 11. Cómo guardar

S valida ambas zonas, solicita nombre y Enter guarda y activa. Para reutilizar un nombre se exige Y en una confirmación adicional. N/Esc cancela. Ante errores de disco se informa el problema y se conservan los cambios editables mientras la aplicación continúa.

Cada JSON se escribe con temporal, `flush`, `fsync` y reemplazo atómico en el mismo directorio. Una exclusión mediante `.write-lock` impide escrituras concurrentes de los programas. Perfil y activo se reemplazan por separado; si falla la activación después de guardar el perfil, la instantánea activa anterior permanece vigente. No se afirma una transacción conjunta ni durabilidad probada frente a un corte eléctrico.

## 12. Cómo seleccionar perfiles

P abre la lista; J/K o ]/[ eligen; Enter carga para revisión sin activar automáticamente. G activa solo un perfil sin cambios pendientes y compatible con la cámara. Si el archivo cambió después de revisarlo, se debe volver a cargar. Cambiar de perfil con una edición pendiente solicita confirmación de descarte.

## 13. Persistencia

El visualizador carga la última activación sin preguntar ni solicitar nuevos polígonos. `active.json` contiene el nombre y la geometría completa activada: es una instantánea, no solo un puntero. Esto protege el activo si falla el segundo reemplazo al sobrescribir un perfil. Cambiar manualmente un archivo por nombre no cambia esa instantánea; P y G permiten revisarlo y activarlo nuevamente. La persistencia entre procesos está probada. El reinicio real de Windows queda en ZON-03.

## 14. Ruta de los JSON locales

`config/zones/<nombre>.json` y `config/zones/active.json`, relativos a la raíz real del proyecto. El `.gitignore` nuevo del directorio excluye estos archivos, el bloqueo y los temporales. No se modifica el `.gitignore` principal. La guía explica cómo retirar un bloqueo residual únicamente con todos los calibradores cerrados.

## 15. Formato de coordenadas

Vértices `[x/ancho, y/alto]`, finitos y entre 0 y 1. Se guarda versión 1, nombre, índice de cámara, resolución efectiva y relación de aspecto. Se conserva la geometría continua del frame; solo el dibujo se recorta a los píxeles visibles. La resolución de la vista previa no cambia las coordenadas persistidas.

## 16. Validación geométrica

Rechaza menos de 3 o más de 16 vértices, duplicados, booleanos, valores no finitos/fuera de rango, área normalizada ≤ `1e-6`, segmentos en retroceso, autointersecciones y contactos consigo mismo. Admite polígonos convexos/cóncavos y orientación horaria/antihoraria. Valida solapamiento de interiores mediante triangulación y comparación geométrica; admite separación y fronteras compartidas. Tolerancia numérica: `1e-9`.

## 17. Perfiles inválidos

Sin activo o con JSON corrupto, esquema incompatible o geometría inválida, el visualizador informa el error y termina antes de cargar IA. No crea zonas predeterminadas. El calibrador permite corregir la situación dibujando o cargando otro perfil. Se rechazan nombres peligrosos, nombres reservados, claves JSON repetidas, archivos demasiado grandes y enlaces simbólicos de perfiles.

## 18. Cambios de cámara

Un índice diferente bloquea la aplicación del perfil; el calibrador muestra el motivo y R permite redibujar ambas zonas. No busca otra webcam, no ejecuta el selector y no escribe la configuración de cámara. El mismo índice no identifica infaliblemente un dispositivo físico. Si se mueve o cambia la perspectiva, debe recalibrarse aunque los metadatos coincidan.

## 19. Cambios de resolución

Se admite un cambio proporcional mediante coordenadas normalizadas, con tolerancia relativa de aspecto del 0,5 %. Se bloquea otro aspecto; en el visualizador se comprueba cada frame antes de inferir. La misma relación de aspecto no detecta recortes, zoom o cambios de sensor: la revisión física sigue siendo necesaria.

## 20. Funcionamiento de track_zones

Carga el activo y la configuración, abre la cámara mediante la función existente, valida compatibilidad e instancia una sola vez `PersonTracker`. Llama `track(frame)` una vez por frame. Después dibuja zonas, cajas/trails existentes, punto inferior y etiquetas. No pasa el frame pintado al detector. Presenta FPS, inferencia YOLO y tiempo conjunto YOLO + tracking, tracks, detecciones sin ID, dispositivo y perfil. Q/Esc/X/Ctrl+C liberan los recursos; también se prueba la liberación ante errores.

El ciclo nuevo es pequeño porque el ciclo anterior no ofrece una función de superposición inyectable. Reutiliza captura, detector/tracker, resolución de dispositivo, historial y representación de cajas; no copia ni modifica el motor.

## 21. Confirmación de BoT-SORT + ReID

Reutilización confirmada por inspección y contratos simulados: el nuevo comando importa `BOTSORT_CONFIG` desde el punto de entrada existente y emplea su YAML actual. No hay otro YAML ni ajuste de parámetros. La inferencia real no se ejecutó aquí.

Valores preservados: `track_high_thresh=0.25`, `track_low_thresh=0.10`, `new_track_thresh=0.25`, `track_buffer=30`, `match_thresh=0.80`, `fuse_score=true`, `gmc_method=none`, `proximity_thresh=0.50`, `appearance_thresh=0.80`, `with_reid=true`, `model=auto`. Se conserva YOLO26n, confianza `0.65`, IoU `0.7`, tamaño de inferencia `640` y clase persona `0` del ZIP.

## 22. Confirmación de CPU/GPU

Se conserva el flujo de resolución de dispositivo de `PersonTracker`; el nuevo módulo no fuerza CPU ni GPU, no pasa overrides y muestra el dispositivo efectivo del motor. Los contratos CPU, `cuda:0` y `cuda:1` fueron simulados. El archivo base mantiene `device=cpu`; una selección local existente sigue siendo resuelta por el código anterior.

No se ejecutó CUDA real ni se midió la GTX 1650. La configuración funcional descrita por el usuario es antecedente de su equipo, no evidencia nueva de esta tarea. No se instalaron CUDA/PyTorch, no se activaron FP16/TensorRT y no se editaron selectores.

## 23. Bottom-center

Se calcula `((x1+x2)/2, y2)` sobre las cajas en coordenadas del frame original. Se marca en blanco. Las pruebas distinguen este punto del centro geométrico. Los trails existentes mantienen su centro anterior y no participan en la clasificación de zonas.

## 24. Clasificación

La pertenencia al polígono produce A, B o FUERA. No se usa proximidad ni máscaras de todo el frame. Los bordes se incluyen; si el punto está en una frontera compartida, A tiene prioridad determinista. Se comprueban también puntos fuera de imagen y separación entre regiones.

## 25. Transiciones observadas

La etiqueta de zona es inmediata. La transición reciente requiere tres frames consecutivos del mismo ID en una zona estable y después tres en otra. Se muestra durante 30 frames. Un frame sin ese ID descarta su continuidad; los nuevos IDs no heredan estados. No se conectan fragmentos. La oscilación breve del punto en un borde no produce transiciones repetidas, aunque un movimiento estable real sí puede producirlas.

Un intercambio de IDs que el tracker no manifieste como desaparición no puede distinguirse de continuidad real. Las transiciones son observaciones inciertas, no identidades ni entradas confirmadas.

## 26. Ausencia de conteo IN/OUT

Confirmada por revisión del código nuevo y de sus efectos: no hay línea final, FSM de acceso, contadores, eventos IN/OUT, ocupación, recuperación entre IDs, base de datos, API o backend. La memoria de observaciones guarda solo el estado reciente de los IDs visibles. Los trails son la visualización acotada ya existente. No se almacena un historial de recorridos ni se exportan imágenes/embeddings.

## 27. Tests nuevos

**59 tests aprobados**: 29 en `test_zones`, 19 en `test_zone_calibrator` y 11 en `test_track_zones`. Los 59 también forman parte de cada una de las tres regresiones finales. La geometría y los archivos temporales son reales; cámara, GUI y motores de inferencia son simulados.

Cubren los 32 puntos mínimos solicitados: importaciones ligeras; geometría válida e inválida; pertenencia A/B/FUERA y bordes; normalización y bottom-center; JSON y persistencia entre procesos; corrupción y nombres; guardado fallido/cancelación/sobrescritura; perfiles y activo; cámara/aspecto; integración con cámara/dispositivo/YAML existentes; ausencia de conteo y de guardado de imágenes; liberación ante salida, X, Ctrl+C y errores. La conservación de los trackers se comprueba adicionalmente mediante comparación binaria de todos los originales.

Casos adicionales relevantes: 300 rectángulos aleatorios deterministas comparados con la intersección analítica, concavidades, conservación de área al triangular, fallo de activación al sobrescribir el mismo nombre, exclusión de dos escritores, activo corrupto sin fallback, cambio del perfil después de su revisión y congelación del frame que estaba efectivamente visible.

## 28. Tests anteriores

Antes de modificar: la suite normal informó **167 tests, 3 fallos, 20 errores y 3 omisiones**. Al final: **226 tests, los mismos 3 fallos, 20 errores y 3 omisiones**. Se compararon los identificadores de cada incidencia: coinciden. Los tests anteriores no fueron editados. Los errores de importación impiden descubrir módulos enteros; por eso el total de la suite normal no equivale al de la batería simulada.

La regresión auxiliar previa ejecutó 286 tests únicos existentes con OpenCV simulado: todos aprobados. La final ejecuta esos mismos 286 y los 59 nuevos: 345. Se eliminan 56 invocaciones repetidas por `test_video_regression.load_tests`; no se elimina cobertura única. Quedan fuera 31 tests dependientes de componentes reales, identificados en el apéndice. Ninguno se cuenta como aprobado.

## 29. Importaciones

Pasaron en procesos nuevos: `src.zones`, `src.zone_calibrator`, `src.track_zones`, `src.main`, `src.detect`, `src.track`, `src.track_fast`, `src.track_recovery`, `src.track_botsort_reid`, `src.camera_selector`, `src.device_selector`, `src.detector`, `src.tracker`, `src.devices`, `src.config` y `src.process_videos`.

`src.camera` no se pudo importar directamente porque falta `cv2`. Es la misma condición del baseline. El test de importaciones nuevas también verifica que no se importen IA/cámara ni se escriban archivos al importar.

## 30. compileall

`python -m compileall src tests`: **salida 0**, antes y después. Verifica sintaxis/compilación, no funcionamiento de cámara ni inferencia. El bytecode generado se excluye del ZIP.

## 31. pip check

`python -m pip check`: **salida 0**, antes y después, sin incompatibilidades entre los paquetes instalados. Esto no significa que las dependencias del proyecto estén instaladas; cv2, torch, ultralytics y lap faltan en este entorno.

## 32. unittest y tres validaciones finales

La suite normal se ejecutó sin modificar su invocación y terminó con salida 1 por las incidencias preexistentes descritas en el punto 28. Los tests nuevos separados pasaron: 40 de geometría+tracking y 19 del editor.

Después del último cambio de código/pruebas, se ejecutó tres veces, en procesos nuevos y secuenciales:

```powershell
python tests/hito4_simulated_regression.py
```

| Ejecución final | Tests únicos | Fallos | Errores | Omisiones dentro de la batería | Excluidos reales | Resultado |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 345 | 0 | 0 | 0 | 31 | OK, 3,197 s |
| 2 | 345 | 0 | 0 | 0 | 31 | OK, 3,492 s |
| 3 | 345 | 0 | 0 | 0 | 31 | OK, 3,289 s |

En las ejecuciones se añadió como argumento la ruta absoluta de cada resumen `hito4_validation/final-run-1.json`, `final-run-2.json` y `final-run-3.json`; los logs se capturaron fuera del proyecto. Intérprete: `/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python`, Python 3.12.14. Directorio: `/workspace/scratch/7148027632de/hito4_latest/capstone-vision`. El arnés entregado puede reproducir la batería desde la raíz del proyecto y generar un resumen opcional.

Una ejecución preliminar del arnés externo falló porque el subproceso de persistencia se lanzó desde fuera del proyecto. Se corrigió el directorio de trabajo del arnés, no la expectativa del test ni el producto. Esa ejecución no se cuenta en las tres satisfactorias. Después de la serie final solo se añadieron documentación e informe.

## 33. diagnostics

`python -m src.diagnostics`: **salida 1**, antes y después. El comando leyó correctamente la configuración de cámara y avisó que el diagnóstico estaba incompleto por `No module named 'cv2'`. No se certifican webcam, backend OpenCV ni captura real.

## 34. Limitaciones del entorno

Linux x86_64, Python 3.12.14 del runtime; no hay `.venv` del proyecto. NumPy y PyYAML están disponibles. Faltan OpenCV, PyTorch, Ultralytics y lap. No se instalaron paquetes, no se descargaron pesos ni se ejecutó inferencia. No se probó cámara física, GUI real de Windows, decodificador MP4 real ni GPU. Todas las pruebas físicas ZON-01 a ZON-17 quedan pendientes. El rendimiento se debe medir en el computador del usuario.

## 35. requirements sin cambios

Contenido idéntico al original. SHA-256: `7e0beeb2827c3a83007226d711711fc1485ceb778acbcda236f2daf6335a57e9`. No se añadió ninguna dependencia.

## 36. README sin cambios

Contenido idéntico al original. SHA-256: `2f8cd27102132a50c117dea9358eeed23ee2156a202b5a2d6716a2c061e3e212`. La documentación del hito se mantiene en un archivo nuevo.

## 37. Documento de instrucciones

`docs/hito4_zonas.md` detalla comandos, mouse/teclado, perfiles, almacenamiento, atomicidad, bloqueo residual, normalización, bordes, cámara/resolución, métricas, continuidad de IDs y el plan completo ZON-01 a ZON-17. Ningún caso físico figura como aprobado.

## 38. Exclusión de archivos personales

El ZIP se construye con una lista explícita de los 70 archivos originales y los 11 nuevos. Se excluyen `.venv`, cachés, bytecode, pesos, selección CPU/GPU personal, fotografías, videos, capturas, resultados temporales de tests, logs de esta validación y perfiles locales. Los archivos MP4 sintéticos generados por tests preexistentes no se distribuyen. `config/zones/` contiene únicamente su nuevo `.gitignore`.

## 39. ZIP completo

`capstone-vision-hito4-zonas-calibrador.zip`, entregado como archivo descargable. Contiene 81 archivos bajo `capstone-vision/`, incluido este reporte. Se comprueban integridad CRC, igualdad de cada original contra la fuente y de cada archivo nuevo contra el árbol de trabajo. Se entrega también una copia independiente de este reporte. No se realizó commit ni push.

## 40. Comandos exactos para las pruebas físicas

Abra una terminal en `capstone-vision`, usando el entorno Python existente y funcional del proyecto. Si su entorno Windows está en `.venv`, puede activarlo como ya hacía con los comandos anteriores:

```powershell
.\.venv\Scripts\Activate.ps1
python -m src.diagnostics
python -m src.zone_calibrator
```

Dibuje A y B; S, nombre y Enter; confirme Y si sobrescribe. Cierre el calibrador y ejecute:

```powershell
python -m src.track_zones
```

Para comprobar persistencia, cierre y repita `python -m src.track_zones` sin abrir el calibrador. Para editar o activar otra ubicación, cierre el tracking, vuelva a `python -m src.zone_calibrator`, use P/Enter/G o edite y guarde; después reinicie el visualizador.

Si necesita cambiar una selección, use voluntariamente los comandos existentes, con los otros programas de cámara cerrados:

```powershell
python -m src.camera_selector
python -m src.device_selector
```

Para ZON-17 compare secuencialmente, nunca compartiendo simultáneamente la webcam:

```powershell
python -m src.track_botsort_reid
python -m src.track_zones
```

Mantenga escena, resolución y dispositivo iguales; espere la estabilización y registre al menos 60 segundos por modo. Complete ZON-01 a ZON-17 según la guía. No se necesita instalar ni actualizar nada como parte de esta entrega.

## Revisiones obligatorias

| Revisión | Evidencia disponible | Pendiente |
| --- | --- | --- |
| 1 — Calibrador | Edición, mouse simulado, cámara seleccionada, validaciones, guardado, cancelación, perfiles, persistencia entre procesos y cierre probados | Interacción con OpenCV y webcam reales, reinicio Windows |
| 2 — Tracking con zonas | Configuración activa, YAML/dispositivo, una inferencia por frame, bottom-center, zonas, métricas y recursos probados con dobles | Inferencia BoT-SORT/ReID real, CUDA, precisión y FPS |
| 3 — Regresiones | 70 originales idénticos, 59 tests nuevos, 286 contratos existentes simulados, tres ejecuciones finales OK, ZIP limpio | Suite completa con dependencias reales y aceptación física |

## Apéndice de evidencia

Los siguientes listados se incorporan desde los resultados efectivamente registrados. Las exclusiones no representan tests aprobados.

### Incidencias de la suite normal, idénticas antes y después

Las tres aserciones fallidas dependen de comandos que no pudieron cargar OpenCV; los 20 errores provienen de imports/decodificación OpenCV o integraciones sin Ultralytics. Las tres omisiones corresponden a dos clases ReID y una de inferencia MP4 sin dependencias/pesos. Identificadores de fallos y errores:

- `test_camera_selector (unittest.loader._FailedTest.test_camera_selector)`
- `test_fallback_still_releases_camera_in_both_apps (test_device_selector.IntegrationTests.test_fallback_still_releases_camera_in_both_apps)`
- `test_fasttracker (unittest.loader._FailedTest.test_fasttracker)`
- `setUpClass (test_fasttracker_integration.FastTrackerIntegrationTests)`
- `test_hito1 (unittest.loader._FailedTest.test_hito1)`
- `test_hito2 (unittest.loader._FailedTest.test_hito2)`
- `test_hito3 (unittest.loader._FailedTest.test_hito3)`
- `setUpClass (test_hito3_integration.ByteTrackIntegrationTests)`
- `setUpClass (test_recovery_integration.RecoveryByteTrackIntegrationTests)`
- `test_video_regression (unittest.loader._FailedTest.test_video_regression)`
- `test_existing_tracking_camera_loop_releases_on_all_paths (test_video_runner.CameraTrackingContractTests.test_existing_tracking_camera_loop_releases_on_all_paths)`
- `test_two_actual_mp4_files_with_simulated_inference (test_video_runner.RealDecoderRunnerTests.test_two_actual_mp4_files_with_simulated_inference)`
- `test_actual_decoder_preserves_frame_order_and_end (test_video_source.RealMp4Tests.test_actual_decoder_preserves_frame_order_and_end)`
- `test_completion_empty_early_unknown_excess (test_video_source.SourceTests.test_completion_empty_early_unknown_excess) (count=2, expected=2)`
- `test_completion_empty_early_unknown_excess (test_video_source.SourceTests.test_completion_empty_early_unknown_excess) (count=0, expected=2)`
- `test_completion_empty_early_unknown_excess (test_video_source.SourceTests.test_completion_empty_early_unknown_excess) (count=1, expected=2)`
- `test_completion_empty_early_unknown_excess (test_video_source.SourceTests.test_completion_empty_early_unknown_excess) (count=2, expected=0)`
- `test_completion_empty_early_unknown_excess (test_video_source.SourceTests.test_completion_empty_early_unknown_excess) (count=2, expected=1)`
- `test_invalid_frame_and_exception_release (test_video_source.SourceTests.test_invalid_frame_and_exception_release)`
- `test_open_failure_release (test_video_source.SourceTests.test_open_failure_release)`
- `test_main_never_resolves_or_loads_inference (test_device_optional.OptionalPipelineTests.test_main_never_resolves_or_loads_inference)`
- `test_existing_commands_read_base_without_selecting (test_device_selector.IntegrationTests.test_existing_commands_read_base_without_selecting) (app='src.detect')`
- `test_existing_commands_read_base_without_selecting (test_device_selector.IntegrationTests.test_existing_commands_read_base_without_selecting) (app='src.track')`

### 31 tests reales excluidos de la regresión simulada

Requieren Ultralytics/PyTorch/lap, metadatos oficiales del paquete o decodificación OpenCV real; no se sustituyen por resultados ficticios. La prueba de valores por defecto de FastTracker también necesita el paquete oficial.

- `test_botsort_reid_integration.RealBOTSORTTests.test_gmc_none_is_accepted_and_identity`
- `test_botsort_reid_integration.RealBOTSORTTests.test_native_encoder_transfers_synthetic_features_to_botracks`
- `test_botsort_reid_integration.RealBOTSORTTests.test_official_yaml_loader_and_real_type`
- `test_botsort_reid_integration.RealBOTSORTTests.test_proximity_still_blocks_distant_identical_features`
- `test_botsort_reid_integration.RealBOTSORTTests.test_real_embedding_distance_participates_and_changes_cost`
- `test_botsort_reid_integration.RealBOTSORTTests.test_real_update_preserves_id_with_synthetic_features`
- `test_botsort_reid_integration.RealBOTSORTTests.test_reset_clears_tracker_session_state`
- `test_botsort_reid_integration.RealInferenceTests.test_real_auto_resolution_encoder_and_device`
- `test_botsort_reid_integration.RealInferenceTests.test_real_detection_extraction_and_association_on_two_frames`
- `test_botsort_reid_integration.RealInferenceTests.test_real_empty_frame_does_not_raise_extraction_failure`
- `test_fasttracker.ConfigTests.test_fast_specific_values_are_official_defaults`
- `test_fasttracker_integration.FastTrackerIntegrationTests.test_empty_frame_and_reappearance_are_supported`
- `test_fasttracker_integration.FastTrackerIntegrationTests.test_real_api_registers_and_initializes_fasttrack_without_reid`
- `test_fasttracker_integration.FastTrackerIntegrationTests.test_rollback_history_is_bounded`
- `test_fasttracker_integration.FastTrackerIntegrationTests.test_sessions_start_with_independent_state`
- `test_fasttracker_integration.FastTrackerIntegrationTests.test_two_tracks_keep_ids_in_synthetic_motion`
- `test_hito3_integration.ByteTrackIntegrationTests.test_lost_track_expires_and_reentry_gets_new_id`
- `test_hito3_integration.ByteTrackIntegrationTests.test_second_association_can_use_low_score_boxes`
- `test_hito3_integration.ByteTrackIntegrationTests.test_static_false_detection_is_not_artificially_removed`
- `test_hito3_integration.ByteTrackIntegrationTests.test_two_moving_tracks_and_brief_occlusion`
- `test_mp4_inference_integration.LocalMp4InferenceTests.test_real_detection_and_tracking`
- `test_recovery_integration.RecoveryByteTrackIntegrationTests.test_equal_high_threshold_can_start_a_track`
- `test_recovery_integration.RecoveryByteTrackIntegrationTests.test_equal_low_threshold_is_not_in_second_association`
- `test_recovery_integration.RecoveryByteTrackIntegrationTests.test_exact_version_and_real_callback_initialize_bytetrack_without_reid`
- `test_recovery_integration.RecoveryByteTrackIntegrationTests.test_high_confidence_static_box_is_not_artificially_removed`
- `test_recovery_integration.RecoveryByteTrackIntegrationTests.test_lost_track_not_reactivated_by_low_confidence_but_high_can_match`
- `test_recovery_integration.RecoveryByteTrackIntegrationTests.test_unconfirmed_new_track_is_not_confirmed_by_low_detection`
- `test_recovery_integration.RecoveryByteTrackIntegrationTests.test_weak_detection_continues_active_id_without_new_weak_track`
- `test_recovery_integration.RecoveryByteTrackIntegrationTests.test_weak_detections_alone_never_start_tracks`
- `test_video_runner.RealDecoderRunnerTests.test_two_actual_mp4_files_with_simulated_inference`
- `test_video_source.RealMp4Tests.test_actual_decoder_preserves_frame_order_and_end`

### Comprobación del YAML principal

SHA-256 de `config/botsort_reid_capstone.yaml`, idéntico al ZIP fuente: `d098f1b15bd838d422e452bbac3d421e1e4fd91711629e37319fb592f526ae6b`.
