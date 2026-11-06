# HigieneSmart — Reporte Hito 5.1: conteo de entradas

Fecha: 29 de octubre de 2026, America/Santiago. Fuente de verdad: `capstone-vision(5).zip` y `Texto pegado(9).txt` adjuntos. Implementación realizada únicamente sobre esa versión, sin instalar dependencias ni descargar pesos.

## 1. Estado general

Se implementó `python -m src.track_count`, con FSM independiente del tracker, confirmación geométrica/temporal de entradas y selección de cuatro trackers. Se añadieron **75 tests**, todos aprobados, y se completaron **tres ejecuciones independientes de 389 tests con componentes simulados**, sin fallos ni errores. La implementación está disponible para las pruebas físicas; no se declara precisión, rendimiento real ni aceptación física del Hito 5.1.

## 2. Archivos inspeccionados

Se inventariaron los 70 archivos del ZIP y se inspeccionaron los componentes de configuración, detector, tracker, dispositivos, cámara, entrypoints, geometría, calibrador/visualizador H4 y sus pruebas. Se revisaron JSON, YAML, requirements, README, reglas de exclusión y el arnés de regresión existente. La selección se buscó en `config.py`, `tracker.py`, `track.py`, entrypoints, configuraciones y referencias de los tests.

Esta fuente **no contiene AGENTS.md ni los módulos MP4** de otra entrega anterior. No se restauraron ni se incorporaron archivos de aquella versión. Tampoco contiene metadatos Git: `git status` informó que no era un repositorio; no se creó uno. Se utilizó comparación de bytes con el ZIP como control final de cambios.

## 3. Mecanismos existentes reutilizados

`ZoneStore.load_active`, `ZoneProfile`, su validación/clasificación y funciones geométricas, `bottom_center`, `draw_regions`, `draw_positions` y `ZoneObservations` para presentación H4; `camera_session`/`camera_info`; `PersonTracker`/`TrackHistory`; `draw_tracks`/`_label`; cargadores JSON y YAML, `resolve_tracker_path`; rutas/etiquetas de entrypoints y `RECOVERY_CONFIDENCE`. La resolución CPU/GPU sigue en el motor anterior.

## 4. Selectores y configuraciones

No se duplicaron los selectores interactivos de cámara/dispositivo ni los YAML. Sí existía una selección compartida por ruta en `config/tracking.json`, pero cambiarla afectaría comandos históricos y no representaba por sí misma el override de Recovery. Por eso se creó **una sola configuración exclusiva del contador**, `config/counting.json`, con nombre de tracker y ocho umbrales de la FSM. El adaptador reutiliza las rutas y validadores originales. No se añadió CLI alternativo de selección ni menú que compita con este archivo.

## 5. Archivos nuevos

| Archivo | Propósito |
| --- | --- |
| `src/count_geometry.py` | Orientación A → B, distancia relativa y cruce de bordes existentes |
| `src/count_engine.py` | FSM, episodios, estabilidad, rearme, limpieza y eventos de entrada |
| `src/counting_config.py` | Carga estricta del JSON y adaptación a los trackers existentes |
| `src/track_count.py` | Cámara, integración, reloj monotónico y presentación del contador |
| `config/counting.json` | BoT-SORT inicial y parámetros explícitos |
| `tests/count_test_support.py` | Perfiles y recorridos sintéticos |
| `tests/video_test_support.py` | Auxiliar de temporales faltante que importaban los tests H4 |
| `tests/test_count_engine.py` | 53 pruebas de FSM, geometría, tiempos y errores |
| `tests/test_counting_config.py` | 9 pruebas de selección, configuración, importaciones y motor común |
| `tests/test_track_count.py` | 13 pruebas de integración y recursos con cámara/IA simuladas |
| `docs/hito5_1_conteo_entradas.md` | Guía completa, umbrales, límites y CNT-01 a CNT-15 |
| `docs/cambiar_tracker_hito5.md` | Manual para elegir tracker sin editar Python |
| `REPORTE_HITO5_1_CONTEO_ENTRADAS.md` | Este reporte |

Total: **13 archivos nuevos**.

## 6. Archivos modificados

**Ninguno de los 70 archivos recibidos.** Se preservan byte por byte módulos, tests, configuraciones, documentación, selectores, README, requirements y reglas de exclusión. No fue necesaria ninguna adaptación de un archivo protegido.

El ZIP tenía un defecto previo: `test_zones.py`, `test_zone_calibrator.py` y `test_track_zones.py` importaban `video_test_support.temporary_directory`, pero el auxiliar no estaba incluido. Se agregó solo ese contrato de temporales como archivo nuevo. No se alteraron expectativas ni pruebas originales, y no se implementó procesamiento MP4.

## 7. Arquitectura final

El visualizador transforma las cajas comunes en `Observation(track_id, point)` con bottom-center normalizado. El motor recibe un frame completo y un timestamp, consulta la geometría H4 y actualiza estados por ID. No importa clases internas de BoT-SORT, no abre cámara y no carga IA. Los eventos se devuelven únicamente en el frame de confirmación.

`count_geometry` agrega solo las operaciones direccionales necesarias; la pertenencia a A/B/FUERA y la validación de perfiles permanecen en H4. `counting_config` adapta el nombre elegido a las rutas/override existentes. El loop nuevo es necesario porque los loops previos no admiten una función de actualización del contador; se reutilizan sus componentes sin copiar el detector ni modificar los comandos anteriores.

## 8. Máquina de estados

Estados: SIN_RECORRIDO, INICIO_EN_A, AVANZANDO_A_B, EN_B, CONFIRMANDO_SALIDA_B, ENTRADA_CONFIRMADA, CANCELADO y SALIDA_OBSERVADA. Los cuatro estados de progreso exigen continuidad y un tiempo máximo de episodio. Confirmado, cancelado y salida requieren un rearme espacial antes de permitir otra entrada. La guía documenta cada transición y su interpretación.

## 9. Regla exacta de entrada

Para un ID continuo: residencia estable con margen dentro de A; salida por un borde frontal de A en dirección a B; residencia estable dentro de B; cruce observado de un único borde frontal de B hacia FUERA; desplazamiento y margen suficientes; y evidencia de salida que satisfaga a la vez tiempo mínimo y mínimo de observaciones. Solo entonces se incrementa `total_entries` y se emite un `EntryEvent`.

Con valores iniciales: residencia de al menos 0.12 s y 2 observaciones en cada zona; confirmación de al menos 0.12 s y 2 observaciones válidas fuera; margen de 0.04 D. El episodio no debe superar 12 s. No se exige un frame FUERA entre A/B si el salto observado es coherente y las zonas alcanzan estabilidad. No se suma al alcanzar B ni al desaparecer dentro de ella.

## 10. Rechazo de retrocesos

Un retroceso longitudinal de más de 2 márgenes desde el máximo avance del episodio cancela. Regresar a A durante el avance, salir por un borde posterior/lateral o realizar un salto incompatible también cancela. Volver a B desde una confirmación de salida anula la evidencia pendiente; no mantiene un temporizador capaz de confirmar después sin nuevas observaciones válidas.

## 11. Dirección hacia el baño

La dirección es la del centroide de A al centroide de B, compensando el aspecto de imagen. D es la distancia entre centroides en esa métrica, no una distancia física en metros. La política conservadora requiere convexidad, orden longitudinal, alineación transversal suficiente, margen interior, frente utilizable de A y salida frontal de B visible.

**A exterior y B baño es la semántica del encargo actual**, distinta de la descripción histórica H4. No se invierten perfiles ni se modifica el calibrador. El inicio informa esta interpretación; el usuario debe comprobar que corresponde a su acceso. Ningún análisis de polígonos puede demostrar por sí solo dónde está el baño real.

## 12. Uso del borde de B

Se calcula la intersección del desplazamiento observado dentro→fuera con el contorno de B. Se exige un único borde, alejado de vértices al menos el margen; su normal y la dirección de movimiento deben apuntar dentro de un cono de 45° hacia el baño. Las observaciones posteriores deben superar el margen en la normal y en el sentido longitudinal. Las esquinas ambiguas y las salidas laterales se rechazan. No se crea, dibuja o persiste otra línea de cruce.

## 13. Gestión de FUERA

FUERA sigue significando fuera de A y B con una posición visible. No es ausencia de detección. El motor utiliza la posición y el borde cruzado para interpretar ese estado; no lo divide en regiones nuevas. Una secuencia A → FUERA → B puede progresar, mientras B → FUERA lateral no confirma nada. Un frame vacío se procesa como ausencia, nunca como salida espacial.

## 14. Oscilaciones y bordes

La pertenencia geométrica conserva la política H4, incluida prioridad A en bordes compartidos. El contador exige margen interior para acumular residencia y margen exterior para confirmar; combina 2 o más observaciones con 0.12 s por defecto. No depende exclusivamente de frames. El mismo recorrido sintético se probó a 5/10/20/30/60 FPS con un resultado consistente. Es evidencia algorítmica, no rendimiento real.

## 15. Protección de duplicados

Un episodio confirmado deja de emitir entradas. El rearme requiere volver de forma estable a A y cruzar su borde posterior hacia el exterior con dirección, margen y estabilidad. Después hace falta otro recorrido completo. Un temporizador, jitter o regresar inmediatamente a B no bastan. El contador no representa personas únicas: una persona puede generar otra entrada después de un retorno y recorrido nuevo observados.

## 16. Cambios de ID

Los IDs son temporales y sus estados están separados. Un ID nuevo no hereda A/B de otro. Se cancelan saltos incoherentes, intervalos demasiado largos y cruces de zona durante ausencias. Una pérdida breve en la misma zona puede mantener el progreso, pero reinicia evidencia temporal pendiente y no permite inferir el cruce de un borde a través de la ausencia. Perderse durante la confirmación de salida cancela.

No hay reconciliación, reconocimiento facial, embeddings guardados ni fusiones por cercanía. Un intercambio de IDs que produzca posiciones plausibles puede no detectarse; dos tracks duplicados con historias completas también pueden ocasionar error. No se promete eliminar todos los duplicados del tracker. Estas limitaciones requieren medición física, especialmente CNT-10/11/12.

## 17. Limpieza de estados

Se eliminan estados tras más de 30 s sin observar el ID. Los episodios activos expiran a los 12 s y la continuidad admite como máximo 0.50 s entre observaciones. Cada estado tiene tamaño acotado, sin historial ilimitado ni imágenes. Hay un límite conservador de 512 estados recientes; si se supera, se detiene con error antes de descartar protecciones para seguir contando. El total de sesión no se borra al limpiar estados antiguos.

## 18. Calibración persistente

Se carga `ZoneStore().load_active()` del Hito 4. El contador no solicita dibujar zonas nuevas, no escribe perfiles, no cambia el activo ni recalibra automáticamente. Un activo ausente/corrupto o geometría incompatible causa error antes de cargar IA. Cámara y aspecto se verifican contra el perfil. La copia activa sigue teniendo exactamente la semántica de persistencia del módulo original.

## 19. Elección del tracker

Nombres válidos: `botsort_reid`, `fasttracker`, `bytetrack`, `recovery`. Cada nombre se resuelve al YAML real del proyecto; el backend se valida. BoT-SORT es el inicial. Recovery pasa `tracking_confidence_override=RECOVERY_CONFIDENCE` al mismo `PersonTracker`; los demás no reciben ese override. No hay fallback silencioso a otro tracker.

## 20. Configuración que controla la selección

`config/counting.json`, campo `tracker`. El mismo archivo tiene un bloque `thresholds` con ocho valores, documentados en la guía. La selección afecta exclusivamente a `track_count`. `load_tracking_config` conserva las opciones base de persistencia/visualización; el contador sustituye la ruta solo en su copia en memoria. El usuario cambia un valor JSON y reinicia, sin editar `.py`.

## 21. Configuraciones originales

Se conservaron todos sus bytes. La confianza general permanece 0.65 y la de Recovery 0.10 solo en esa sesión. BoT-SORT mantiene `track_buffer=30`, `proximity_thresh=0.50`, `appearance_thresh=0.80`, `with_reid=true`, `model=auto`, `gmc_method=none` y el resto de su YAML. FastTracker y ByteTrack conservan todos sus valores. No se cambian YOLO26n, IoU, imagen, cámara ni CPU/GPU.

## 22. Salidas no contabilizadas

Los recorridos B → A pueden mostrarse como SALIDA_OBSERVADA. No existe acumulador OUT, evento de salida ni resta de entradas. El motor conserva exclusivamente el total de ingresos observados. Se probaron salida inicial, entrada seguida de salida y salida seguida de otra entrada legítima.

## 23. Visualización

Título HIGIENESMART, total de entradas, tracker/CPU-GPU/confianza, cámara/resolución/perfil, FPS, YOLO ms y tiempo conjunto YOLO + tracking. Se reutilizan cajas, confianza, IDs, trails, polígonos y bottom-center; se agrega el estado FSM por track. OpenCV Hershey usa ASCII: el rótulo muestra `ENTRADAS AL BANO`. Las transiciones visuales H4 no deciden el conteo. No hay contador de salidas ni archivos de resultados.

## 24. CPU/GPU

La selección y su resolución siguen en `PersonTracker` → cargador existente → `resolve_effective_device`. Se respeta la preferencia local y el fallback previo con advertencia, sin modificarla. Se probaron contratos de dispositivo y su visualización con simulaciones; no se ejecutó CUDA ni se certifica la GTX 1650 u otro hardware. No se modificaron PyTorch, FP16, TensorRT o CUDA.

## 25. Cámara

Se utiliza el índice seleccionado y `camera_session`, con liberación ante Q/Esc/X/Ctrl+C, fallos de lectura, errores del modelo o de la interfaz. Los tests comprueban estos caminos con dobles. No se abren varias cámaras ni se ejecutan selectores desde el contador. Perfil incompatible bloquea antes del modelo; un cambio de aspecto en ejecución bloquea antes de inferir el siguiente frame.

## 26. Tests unitarios nuevos

53 pruebas del motor/geometría: entrada, inverso, detenciones, retrocesos, costados, esquinas, jitter, pérdida de ID, continuidad, dos personas, eventos únicos, rearme completo, nueva sesión, limpieza, límites de memoria, timestamps/posiciones inválidos, dwell/tiempo, saltos, rotaciones, aspecto/resolución, trapecios, bordes compartidos, concavidad/ambigüedad y salida no visible. Las 9 pruebas de configuración también validan nombres, JSON, umbrales, backend, ausencia de fallback e importaciones ligeras.

Los escenarios sintéticos usan geometría real y timestamps deterministas. No se requieren videos, webcam o modelos para los tests nuevos. No se confunden sus resultados con exactitud de conteo físico.

## 27. Tests de integración

13 pruebas del comando ejecutan la FSM real con cámara, interfaz y resultados de tracker simulados. Cubren una inferencia por frame, orden inferencia→superposición, bottom-center, detecciones sin ID, cuatro selecciones, dispositivos, métricas, incompatibilidad de cámara/aspecto, cierre, errores y carga del activo sin escrituras.

Dentro de la batería de configuración se instancia el `PersonTracker` real del proyecto con modelo y diagnóstico ReID simulados; se verifican el YAML transmitido, `conf=0.10` solo para Recovery y `0.65` para los otros, dispositivo y banderas sin guardado. Esto acredita el cableado al motor común, no disponibilidad ni calidad de los backends reales.

## 28. Tests anteriores y baseline

Antes de implementar, la suite normal informó **135 tests, 3 fallos, 12 errores y 2 omisiones**. Además de dependencias ausentes, tres errores eran los imports H4 del auxiliar faltante. La batería simulada previa ejecutó **258 casos: 255 aprobados y 3 errores de importación**, con 28 tests reales excluidos.

Al final, la suite normal ejecutó **266 tests, 3 fallos, 9 errores y 2 omisiones**. No hay incidencias nuevas respecto al baseline: desaparecieron únicamente los tres imports H4 al incorporar el auxiliar. La batería simulada final ejecuta los **314 tests existentes accesibles** y **75 nuevos**, total 389; todos pasan. Se mantienen intactos los tests anteriores. Los errores de descubrimiento explican por qué los totales normales y simulados no son directamente comparables.

## 29. Compilación e importaciones

`python -m compileall src tests`: salida 0 antes y después. Importaron sin errores, en procesos nuevos, los cuatro módulos nuevos y los módulos previos de zonas, calibración, visualización, entrypoints, selectores, detector, tracker, dispositivos y configuración. `src.camera` directo permanece bloqueado por falta de `cv2`. Las importaciones nuevas no cargan NumPy, OpenCV, PyTorch, Ultralytics o cámara, ni crean configuraciones.

## 30. Pip check

Salida 0 antes y después, con `No broken requirements found`. Comprueba coherencia entre paquetes instalados, no que todos los requisitos del proyecto estén presentes. No se instaló, actualizó ni desinstaló nada.

## 31. Diagnósticos

`python -m src.diagnostics` terminó con salida 1 antes y después: pudo leer cámara índice 1, 1280×720, 60 FPS solicitados y backend auto; avisó diagnóstico incompleto por `No module named 'cv2'`. Estos son valores de configuración, no mediciones de una cámara disponible en este entorno.

## 32. Limitaciones del entorno

Linux x86_64, Python 3.12.14; intérprete `/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python`. No hay `.venv` local del proyecto. NumPy y PyYAML están disponibles; faltan OpenCV, PyTorch, Ultralytics y lap. No se descargaron pesos ni se ejecutó inferencia o GPU real. Tampoco se probó GUI Windows o webcam. Las 28 exclusiones reales se enumeran al final.

## 33. Limitaciones técnicas A/B

Se presupone un recorrido aproximadamente continuo y recto. Se rechaza geometría cóncava o ambigua de forma conservadora; las esquinas, pérdidas de continuidad, detenciones largas, intervalos grandes y movimientos que superen los umbrales pueden causar omisiones. Los puntos de caja no representan perfectamente el contacto con el suelo. No se identifica el baño real a partir del nombre de una zona. El movimiento físico de cámara puede invalidar el perfil aunque índice/aspecto coincidan. No se resuelven intercambios de ID plausibles ni duplicaciones del tracker.

Los valores iniciales no están ajustados con una muestra real. No se declara el objetivo 85–90 % alcanzado. No se evalúa calidad por coincidencia del total final: deben registrarse correctos, omitidos, falsos y duplicados por recorrido.

## 34. Documentación generada

`docs/hito5_1_conteo_entradas.md` explica significado A/B, comandos, geometría, bordes, FSM, tiempos, ocho umbrales y políticas, pérdidas/IDs, presentación, regresiones y CNT-01 a CNT-15. Este reporte completa los 40 puntos solicitados.

## 35. Manual de cambio de tracker

`docs/cambiar_tracker_hito5.md` identifica el archivo y la línea reales, los cuatro valores válidos, cómo editar con Bloc de notas, guardar, ejecutar, verificar en pantalla y volver a BoT-SORT. Explica los YAML y el override de Recovery, archivos que no deben tocarse y tratamiento de errores.

## 36. README y requirements

Ambos son idénticos al ZIP fuente. README SHA-256: `df5b1c0f151fd8414806e6b1bc12d4eb000ff45b2d265c7fdbd019029cbdb299`. Requirements SHA-256: `7e0beeb2827c3a83007226d711711fc1485ceb778acbcda236f2daf6335a57e9`. No se reconstruyó el README ni se añadió dependencia.

## 37. Privacidad

Conteo local en memoria, IDs temporales y estados acotados. No hay identidad persistente, reconocimiento facial, nombres, imágenes/video/recortes guardados, exportación de embeddings, base de datos ni envío a Django. No se genera un archivo de conteos o eventos. Se conserva el comportamiento del cargador existente y sus cachés técnicas, sin incorporar almacenamiento personal nuevo.

## 38. ZIP entregado

`capstone-vision-hito5-1-conteo-entradas.zip`, proyecto completo con los **70 archivos fuente intactos y 13 nuevos: 83 archivos**. Se empaqueta mediante lista explícita, comprueba CRC y compara cada miembro contra fuente/árbol final. No contiene `.venv`, bytecode, pesos, videos, fotografías, cachés, preferencias locales, perfiles personales ni temporales de pruebas. `config/zones/` conserva solo el `.gitignore` recibido. No hubo commit, push, rama nueva ni cambio de remoto.

## 39. Comandos exactos para probar

Desde `capstone-vision`, con el entorno existente en Windows:

```powershell
& .\.venv\Scripts\python.exe -m src.zone_calibrator
```

Revise A exterior/B baño, guarde/active si necesita ajustar y cierre. Después:

```powershell
& .\.venv\Scripts\python.exe -m src.track_count
```

Si el perfil ya corresponde a esa orientación, basta el segundo comando en cada sesión. Para elegir otro tracker:

```powershell
notepad .\config\counting.json
```

Cambie solo `tracker`, guarde y reinicie. Con el entorno activado se puede usar `python -m src.track_count`. No hace falta iniciar un agente ni un servicio. Los selectores de cámara/dispositivo siguen siendo opcionales y se usan únicamente para cambiar esas preferencias.

## 40. Pruebas físicas pendientes y problemas conocidos

**Todas las CNT-01 a CNT-15 están pendientes**, con procedimientos y resultados esperados en la guía. Incluyen entrada, salida, retrocesos, salida lateral, detención, retorno/rearme, dos personas, cruces, oclusiones, cambios de ID, perfiles, cambio de tracker y FPS. Se deben medir en la cámara y hardware del usuario.

Problemas conocidos: falta de dependencias reales de este entorno; necesidad de revisar el sentido A/B respecto a la documentación histórica; restricciones deliberadas de geometría/continuidad; y errores posibles por ID swaps plausibles. El auxiliar de pruebas ausente en el ZIP se resolvió mediante un archivo nuevo. No se implementó Hito 5.2 ni se creó un calibrador extendido.

## Tres validaciones finales independientes

Se ejecutó el arnés existente después del último cambio de código o tests, cada vez en un proceso nuevo y sin paralelizar inferencias:

```powershell
python -u tests/hito4_simulated_regression.py
```

| Ejecución | Tests únicos ejecutados | Fallos | Errores | Omisiones dentro de la batería | Tests reales excluidos | Resultado | Duración del proceso |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| 1 | 389 | 0 | 0 | 0 | 28 | OK | 2.406 s |
| 2 | 389 | 0 | 0 | 0 | 28 | OK | 2.560 s |
| 3 | 389 | 0 | 0 | 0 | 28 | OK | 2.217 s |

Directorio de ejecución: `/workspace/scratch/7148027632de/hito5_work/capstone-vision`. Se añadió como argumento la ruta de cada resumen `hito5_validation/final-regression-1.json`, `final-regression-2.json` y `final-regression-3.json`; stdout/stderr se conservaron fuera de la entrega. También se ejecutaron separadamente 62 pruebas de motor/configuración y 13 de integración, todas OK. Después de la serie final solo se redactaron documentos y se verificó el paquete.

Las exclusiones no se cuentan como aprobadas. El arnés inyecta OpenCV simulado en su proceso; no altera paquetes ni archivos originales. No hubo invocaciones duplicadas en esta versión del ZIP. El nombre histórico del arnés se conserva para no editar archivos anteriores.

## Revisión final en tres etapas

| Etapa | Evidencia | Pendiente |
| --- | --- | --- |
| Motor | FSM, dirección/bordes, retrocesos, histéresis, tiempo, rearme, limpieza y errores con geometría/timestamps reales sintéticos | Calibración de umbrales con personas reales |
| Integración | Cámara/GUI simuladas; perfil H4; motor común, YAML/override; dispositivo; una inferencia por frame; cierre | Webcam, GUI, modelos y CUDA reales |
| Regresión/entrega | Originales intactos, 75 tests nuevos, 314 contratos existentes simulados, 3 ejecuciones OK, documentos, ZIP limpio | Suite completa con dependencias reales y aceptación CNT |

## Apéndice de resultados registrados

Los listados siguientes identifican los casos que no quedaron acreditados con componentes reales.

### Suite normal: 3 fallos y 9 errores que persisten del baseline

Los cinco imports de módulos de tests y el contrato de cámara necesitan cv2; tres setUpClass de trackers reales requieren Ultralytics y su entorno. Las tres aserciones fallidas corresponden a comandos que devuelven error al faltar OpenCV. Las dos omisiones son clases de integración BoT-SORT/ReID sin runtime real.

- **ERROR**: `test_camera_selector (unittest.loader._FailedTest.test_camera_selector)`
- **ERROR**: `test_fallback_still_releases_camera_in_both_apps (test_device_selector.IntegrationTests.test_fallback_still_releases_camera_in_both_apps)`
- **ERROR**: `test_fasttracker (unittest.loader._FailedTest.test_fasttracker)`
- **ERROR**: `setUpClass (test_fasttracker_integration.FastTrackerIntegrationTests)`
- **ERROR**: `test_hito1 (unittest.loader._FailedTest.test_hito1)`
- **ERROR**: `test_hito2 (unittest.loader._FailedTest.test_hito2)`
- **ERROR**: `test_hito3 (unittest.loader._FailedTest.test_hito3)`
- **ERROR**: `setUpClass (test_hito3_integration.ByteTrackIntegrationTests)`
- **ERROR**: `setUpClass (test_recovery_integration.RecoveryByteTrackIntegrationTests)`
- **FAIL**: `test_main_never_resolves_or_loads_inference (test_device_optional.OptionalPipelineTests.test_main_never_resolves_or_loads_inference)`
- **FAIL**: `test_existing_commands_read_base_without_selecting (test_device_selector.IntegrationTests.test_existing_commands_read_base_without_selecting) (app='src.detect')`
- **FAIL**: `test_existing_commands_read_base_without_selecting (test_device_selector.IntegrationTests.test_existing_commands_read_base_without_selecting) (app='src.track')`

### 28 tests excluidos del arnés simulado

Necesitan paquetes/backend/inferencia reales o los valores oficiales del paquete instalado. No se ejecutaron como aprobados mediante mocks.

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
- `test_recovery_integration.RecoveryByteTrackIntegrationTests.test_equal_high_threshold_can_start_a_track`
- `test_recovery_integration.RecoveryByteTrackIntegrationTests.test_equal_low_threshold_is_not_in_second_association`
- `test_recovery_integration.RecoveryByteTrackIntegrationTests.test_exact_version_and_real_callback_initialize_bytetrack_without_reid`
- `test_recovery_integration.RecoveryByteTrackIntegrationTests.test_high_confidence_static_box_is_not_artificially_removed`
- `test_recovery_integration.RecoveryByteTrackIntegrationTests.test_lost_track_not_reactivated_by_low_confidence_but_high_can_match`
- `test_recovery_integration.RecoveryByteTrackIntegrationTests.test_unconfirmed_new_track_is_not_confirmed_by_low_detection`
- `test_recovery_integration.RecoveryByteTrackIntegrationTests.test_weak_detection_continues_active_id_without_new_weak_track`
- `test_recovery_integration.RecoveryByteTrackIntegrationTests.test_weak_detections_alone_never_start_tracks`
