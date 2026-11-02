# LimpIA — Auditoría de datasets, Etapa 2A

Auditoría local del 2026-11-01 (America/Santiago). Rama comprobada: `feature/pruebas-automatizadas`.

## Resultado y alcance

Se implementaron dos módulos independientes y pruebas; se decodificaron los 11.454 fotogramas de los siete MP4. No se ejecutó inferencia, tuning ni métricas. Ninguna secuencia se certifica READY; `eligible_sequence_ids=[]`. La preparación técnica está implementada; la habilitación para evaluación sigue pendiente de revisión documentada.

## Inventario real

| Secuencia | Resolución MP4 | FPS informados | Frames decodificados | Duración nominal (s) | Estado |
|---|---:|---:|---:|---:|---|
| MOT17-02 | 960 × 540 | 30 | 600 | 20.00000 | NEEDS_VERIFICATION |
| MOT17-04 | 960 × 540 | 30 | 1050 | 35.00000 | NEEDS_VERIFICATION |
| PETS09-S2L1 | 768 × 576 | 7 | 795 | 113.57143 | NEEDS_VERIFICATION |
| OxfordTownCentre | 1920 × 1080 | 25.003333 | 7502 | 300.04000 | NEEDS_VERIFICATION |
| CAVIAR-EnterExitCrossingPaths1cor | 384 × 288 | 25 | 383 | 15.32000 | NEEDS_VERIFICATION |
| CAVIAR-OneLeaveShopReenter1cor | 384 × 288 | 25 | 390 | 15.60000 | NEEDS_VERIFICATION |
| prueba_01 | 1280 × 720 | 24 | 734 | 30.58333 | EXPLORATORY |

Todas las duraciones son frames/FPS informados, no una certificación de PTS. Los siete MP4 terminan con EOF consistente con su cantidad declarada. El manifiesto registra tiempos primero/último y fallback; el contenedor Oxford informa aproximadamente 25,00333289 FPS, no exactamente 25.

Ubicaciones relativas a `capstone-vision/videos_testing/`: seis académicos en `dev/`, `prueba_01.mp4` en `exploratory/`. `validation/` no contiene archivos. La ausencia de un archivo de carpeta no acredita la existencia física de una carpeta vacía; el comando informa archivos, no inventa grabaciones de validación.

### SHA-256 de cada MP4

- `dev/MOT17-02.mp4` — 14780307 bytes: `d560bc50e1942d5c7335c937c8ac513aa87bb41ea51ae21fa02f661151d5a066`.
- `dev/MOT17-04.mp4` — 14745062 bytes: `ab0d2fc03bce5e112abe9a173de7a2d70b39875c0af3eca49d6160c6e317e495`.
- `dev/PETS09-S2L1.mp4` — 21357352 bytes: `e03a8d3ae953c640a2eb26bdeff8502111e8c5ac11e529f4dc67931dd548557e`.
- `dev/TownCentreXVID.mp4` — 86033276 bytes: `988263dd7aa8dd52f03f052d13c81d57239c6d0ef3478e9c17a10ef3d0fa41f2`.
- `dev/CAVIAR-EnterExitCrossingPaths1cor.mp4` — 1747971 bytes: `8a24f775da0f6e20b32a35df88d6f826ecc3f4b7cd24c16e8ef60260caa60ba6`.
- `dev/CAVIAR-OneLeaveShopReenter1cor.mp4` — 1716600 bytes: `456d654d679a92a1a4150f129cc2edbbb051f0c94e3fd5f62fed0af572aac4bd`.
- `exploratory/prueba_01.mp4` — 3524934 bytes: `a76ee127f7f45b48b93c1e68a9ef607c1c8463d4c8ae7994c0a3df75246185fd`.

El manifiesto contiene además los hashes de ZIP, XML, TOP, calibración, MPG y TAR locales (17 archivos de entrada válidos en total). La descarga `.part` se enumera aparte, sin abrirse ni borrarse. Dos auditorías completas con el código final produjeron archivos JSON idénticos byte por byte. SHA-256 del manifiesto: `2c39c80a1fcf93ad418a41652842729d0c8f40ce2cd988e8a249e61c27d955c3`. Cada pasada comparó hashes antes/después; también coinciden con el inventario capturado antes de implementar.

## Hallazgos y compatibilidad

### MOT17-02 y MOT17-04

Los MP4 están a 960 × 540, mientras que ambos seqinfo indican 1920 × 1080. Candidata de escala: (0,5; 0,5), sin corrección de crop supuesta. La revisión visual del asistente de inicio/mitad/final es coherente con esa escala, sin un desplazamiento grueso evidente; no certifica un offset exacto de un frame ni reemplaza revisión humana. Índices inspeccionados: 0/300/599 y 0/525/1049, respectivamente.

El ZIP contiene DPM/FRCNN/SDP. Se leyeron y verificaron los CRC de los miembros GT y seqinfo usados; los tres GT de cada secuencia son idénticos en bytes/hash. Se selecciona DPM como localizador canónico, no como fuente de predicciones. Las tres variantes constituyen un solo grupo de grabación y no deben contarse como tres videos independientes. No se extrae ni puntúa `det/det.txt`.

MOT17-02: 30.003 filas válidas, 83 IDs de todas las clases, 18.581 filas de peatón activas. MOT17-04: 108.005 filas válidas, 141 IDs de todas las clases, 47.557 filas de peatón activas. No confundir IDs totales con el número de peatones evaluados. Ambos tienen filas en todos los frames esperados (600 y 1.050) y cero duplicados (frame,ID).

GT de nueve columnas: frame, ID, left, top, width, height, mark, class, visibility. Frame/coordenadas MOT desde 1; el lector transforma frame y left/top restando 1 y convierte XYWH a XYXY. Conserva mark, clase y visibilidad. Cajas fuera de imagen (982 y 21.492 filas de todas las clases) no se clasifican como corruptas automáticamente: pueden ser cajas amodales. No se recortan ni filtran destructivamente. `ignored` conserva mark=0; que una clase no sea peatón no la convierte automáticamente en región que deba suprimir falsas detecciones. La política oficial de distractores debe implementarse separadamente en 2B.

Pendiente: confirmar procedencia de conversiones, registrar alineación temporal más precisa, validar escala/crop, acordar geometría amodal y exclusiones. Estado NEEDS_VERIFICATION.

### PETS09-S2L1 / MOT15

MP4 y seqinfo coinciden en 768 × 576, 7 FPS y 795 frames. Hay 4.650 filas válidas, 19 IDs, 4.476 filas activas y 174 mark=0. Todos los frames tienen filas, sin pares duplicados. Revisión visual del asistente en índices 0/397/794: cajas coherentes con la escena, sin desplazamiento grueso aparente. No acredita procedencia ni offset exacto.

Formato MOT15 de DIEZ columnas: las tres últimas son coordenadas mundiales XYZ; NO son clase ni visibilidad. Se preservan en raw; clase fuente y visibilidad permanecen null. La etiqueta semántica person se deriva explícitamente del protocolo del dataset, no de una columna inventada.

Pendiente: revisión temporal y exclusiones/mark=0 documentadas. Estado NEEDS_VERIFICATION.

### Oxford Town Centre

El MP4 se decodifica hasta 7.502 frames, aproximadamente 300,04 s. El TOP local tiene 47.747 líneas: 47.746 de doce columnas válidas bajo la interpretación candidata, y la última (línea 47.747) sólo tiene once columnas. Texto final: `139,3090,1,1,1517.209,182.327,1536.430,203.045,1491.499,172.528,1555.734`. Falta el último valor. No se rellena, repara ni ignora silenciosamente.

Las filas completas cubren índices fuente 0–3089; hay 157 IDs distintos en ese prefijo válido. Los índices 3090–7501 del video carecen de filas válidas (4.412 frames), y la línea incompleta demuestra que hay al menos información truncada al comienzo de ese tramo. No se puede inferir que el resto sea una escena vacía o una exclusión académica deliberada. No se habilita el clip completo ni se crea un recorte.

TOP es un esquema candidato de ID, frame, headValid/bodyValid, headXYXY y bodyXYXY. Se retienen ambas validez y cajas de cabeza en raw. Los flags de validez no son fracciones de visibilidad. Quedan pendientes la convención exacta de origen de píxel y el protocolo de cajas corporales; no asumir equivalencia con cajas YOLO. El archivo `.ci` se abrió y se inventariaron sus campos, pero calibración no equivale a GT ni resuelve el truncamiento. El acceso a la antigua página técnica de los autores no permitió confirmar el esquema completo en esta sesión. La publicación primaria acredita GT de cabezas; la normalización de cuerpo sigue siendo candidata.

Hay un par de frames decodificados consecutivos idénticos en Oxford. No se eliminan ni renumeran. Estado NEEDS_VERIFICATION; recuperar/verificar el GT completo requeriría autorización separada de descarga o el suministro de una copia íntegra.

### CAVIAR (dos conversiones)

XML con frame e ID desde 0; se conservan IDs originales (incluido 0). Sólo se leen objectlist/object: grouplist/group no se duplica como personas. La caja usa xc,yc,w,h; se calcula xyxy como centro ± semiextensión, conservando valores fuente. Los roles walker observados permiten una etiqueta person derivada explícita. Appearance es categórico (por ejemplo occluded); no se convierte en visibilidad 0/1. `visibility=null` e `ignored=null` significan ausentes/política pendiente. La convención fina de origen de píxel queda sin certificar.

CrossingPaths: 383 frames explícitos 0–382, 1.385 filas, 5 IDs, sin frames XML faltantes ni listas vacías. Reenter: 390 frames explícitos 0–389, 408 filas, 2 IDs; listas explícitamente vacías en 0–103. Esos 104 frames no son huecos del XML, aunque la política de objetos estáticos impide interpretarlos automáticamente como ausencia de toda persona visible. No hay duplicados (frame,ID) ni cajas no positivas.

Los TAR contienen exactamente 383/390 JPEG numerados desde 0000. Se decodificó y comparó cada MP4 con el JPEG del mismo índice, sin extraer archivos. Error absoluto medio en canales de 8 bits: 4,69405 y 4,67394; máximo del error medio por frame: 5,09525 y 4,97501. En sondeos de inicio/cuartiles/final, el offset 0 da menor error medio que los candidatos ±1/±2. Esto apoya la correspondencia de la conversión; no prueba unicidad temporal de todos los frames ni exhaustividad de las etiquetas.

Los MPG fuente también se decodificaron: 383 y 390 frames, respectivamente. Sus metadatos OpenCV reportan sólo 4 frames, de modo que VideoSource los marca incomplete por exceso sobre el conteo declarado. Es una inconsistencia de metadatos, no prueba suficiente de corrupción visual. Se observaron 4 y 1 pares adyacentes idénticos en MPG, frente a cero en MP4; por ello no se declara que cada MP4 sea una conversión temporal idéntica al MPG sólo por coincidir su conteo. La referencia JPEG ofrece la comparación más pertinente a las anotaciones.

La fuente primaria CAVIAR advierte duplicados/missing frames en la digitalización y que algunas personas estáticas no se etiquetan. No se eliminan frames para corregirlo. Pendiente: política de target/ignorados, origen de coordenadas, revisión de oclusiones y evidencia de aprobación. Estado NEEDS_VERIFICATION para ambos.

### prueba_01

734 frames, hash idéntico al adjunto analizado previamente. Se mantiene EXPLORATORY sin depender de predicciones históricas, anotaciones preliminares ni resultados del tracker. Nunca se selecciona para métricas en esta etapa.

## Significado de estados

- READY: datos, correspondencia y política aprobados con evidencia; no utilizado en esta entrega.
- NEEDS_ADAPTER: fuente/correspondencia verificadas, resta transformación; reservado para cuando se resuelvan las dudas de interpretación. Tener un lector no basta para asignarlo.
- NEEDS_VERIFICATION: dudas de integridad, sincronía o protocolo; los seis académicos actuales.
- NOT_EVALUABLE: falta video/GT suficiente o no hay filas utilizables; contemplado en archivos faltantes y probado con fixtures. No se afirma que un dataset con un prefijo válido sea irrecuperable.
- EXPLORATORY: uso visual/manual, sin elegibilidad objetiva; prueba_01.

El comando NO promociona automáticamente a READY. Esto es deliberado: una auditoría estructural no acredita por sí sola correspondencia visual ni política de evaluación. No hay opción de forzar READY. `evaluation_cases` exige estado READY, bandera explícita y verificaciones temporal/de política; además excluye prueba_01 y exploratory. La lista eligible_sequence_ids actual está vacía. En 2B habrá que vincular aprobación/evidencia a hashes concretos, no editar una bandera a ciegas.

## Contrato interno y compatibilidad con predicciones

Las predicciones v1 existentes en predictions.jsonl usan frame_index desde cero y cajas x1/y1/x2/y2 en píxeles del video, junto con confidence/class_id y track_id en los tracks; detections y untracked_detections son listas distintas. La clase person de YOLO es 0; la clase peatón de MOT17 es 1. Nunca se comparan numéricamente las clases sin un mapeo semántico explícito. VideoResults guarda dataclasses sin normalizarlas a MOT. El visualizador y el informe sólo leen resultados; el nuevo comando no depende de esos módulos ni cambia sus contratos.

Los lectores de auditoría retornan Annotation con source_frame, frame_index cero-basado, object_id fuente como cadena, bbox_xyxy, source_class, class_label semántica, visibility, ignored, raw y transformations. La secuencia/dataset/grupo original vive en su envolvente del manifiesto. La identidad futura debe ser la tupla (dataset, original_sequence, object_id), no un número global ni el ID del tracker.

Campos ausentes se mantienen null. Cada transformación queda identificada: frame/origen MOT -1, XYWH→XYXY, centro→esquinas y clase derivada. `scale_annotation` aplica una escala explícita candidata y conserva raw; la auditoría no exporta un GT escalado aprobado. No se interpola, completa ni mezcla con detecciones. El manifiesto guarda estadísticas y ejemplos, no todas las filas normalizadas ni un sustituto de los GT originales.

## Implementación, archivos y conservación

- Nuevos: src/dataset_annotations.py (lectores/estadísticas), src/dataset_audit.py (inventario/CLI), tests/test_dataset_audit.py (23 pruebas).
- Nuevos de documentación: docs/DATASET_AUDIT_2A.md y docs/dataset_audit_2a_manifest.json.
- Modificado: README.md, sólo una sección añadida de uso.
- Módulos de cámara, detectores, trackers, procesamiento, visualización y selectores CPU/GPU intactos. Configuración de confianza 0.65, YAML y entorno intactos.

Se guardaron hashes de los archivos funcionales existentes antes de implementar y se compararon al cierre (excluyendo únicamente el README autorizado). El inventario hash de datasets previo a la implementación coincide con los dos inventarios del código final. No se movió, renombró, borró ni sobrescribió ningún dataset/anotación/resultado histórico. No se abrió el .part. Las imágenes de revisión son derivados temporales fuera del árbol de datasets, no una nueva fuente de GT; no se incluyen en Git.

## Comandos reproducibles

Desde Fase_2/Evidencias_Proyecto/Vision-Artificial/capstone-vision, PowerShell:

```powershell
& .\.venv\Scripts\python.exe -B -m src.dataset_audit --output logs/dataset_audit_2a_01.json
& .\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_dataset_audit.py -v
& .\.venv\Scripts\python.exe -m pip check
```

Usar un nombre nuevo para cada informe. El destino debe quedar fuera de videos_testing y no existir; se rechazan sobrescrituras y salidas dentro de inputs. --datasets admite otra base local; por defecto se toma videos_testing relativa al módulo, no al cwd. El código de salida 0 indica informe generado, no existencia de casos READY. No hay instalación automática ni acceso a red.

Para repetir exactamente las validaciones ampliadas, el paquete de evidencia contiene validate_stage2a.py. Con esa carpeta como directorio actual:

```powershell
$visionRoot = 'C:\Users\juanc\Downloads\ProyectoCapstone-AntonioVaras-ProfAldoMartinez-802D\Fase_2\Evidencias_Proyecto\Vision-Artificial\capstone-vision'
& "$visionRoot\.venv\Scripts\python.exe" -B .\validate_stage2a.py $visionRoot .\nueva_validacion_1.log
& "$visionRoot\.venv\Scripts\python.exe" -B .\validate_stage2a.py $visionRoot .\nueva_validacion_2.log
& "$visionRoot\.venv\Scripts\python.exe" -B .\validate_stage2a.py $visionRoot .\nueva_validacion_3.log
```

## Validaciones ejecutadas realmente

Entorno: Windows local, Python 3.13 del .venv existente, OpenCV 4.14.0; CPU para decodificación y pruebas sintéticas. No hay medición de rendimiento ni validación GPU/cámara real. pip check: No broken requirements found.

| Proceso independiente | Casos nuevos | Regresión seleccionada | Fallos/errores | Omisiones en selección |
|---|---:|---:|---:|---:|
| final_validation_1 | 23/23 | 383/383 | 0/0 | 0 |
| final_validation_2 | 23/23 | 383/383 | 0/0 | 0 |
| final_validation_3 | 23/23 | 383/383 | 0/0 | 0 |

Los 383 son ejecuciones de casos seleccionadas, con repeticiones previstas por test_video_regression; no se afirma que sean 383 pruebas únicas. Cubren los contratos existentes y las Etapas 1/1.5 con mocks y lectura real de MP4 sintético. Los nuevos casos cubren ZIP sin extracción, IDs/frames, columnas MOT15/17, TOP truncado, XML corrupto, grupos/frames vacíos, duplicados, datos faltantes, geometría, rechazo de salida dentro de inputs/sobrescritura, determinismo, exclusión exploratoria, conservación, detección de mutación y decodificación real/liberación.

Exclusiones explícitas de las tres pasadas: test_botsort_reid_integration.py, test_fasttracker_integration.py, test_hito3_integration.py, test_mp4_inference_integration.py y test_recovery_integration.py. Incluyen motores reales, carga de Ultralytics o inferencia: no se ejecutaron y no se cuentan como aprobados. El proceso de pruebas no importó ultralytics. No se afirma regresión integral de hardware ni aceptación visual del sistema.

Incidencias previas a las tres validaciones finales: el primer baseline de 89 casos bajo permisos restringidos produjo 28 errores de creación de temporales; repetido con acceso a su carpeta de logs, pasó 89/89. Una primera regresión ampliada pasó 23/23 nuevos pero falló 1/383 antiguos porque el lanzador estaba en el directorio de entrega y un subproceso no encontraba src. Se corrigió el cwd del lanzador, sin editar ni debilitar la prueba existente, y después pasaron las tres series completas. Las incidencias no se ocultan ni se atribuyen a cambios funcionales del producto.

No se ejecutó la suite íntegra con inferencia. Tampoco se calcularon IDF1/HOTA/MOTA, precisión de detección ni conteo. La decodificación satisfactoria no certifica alineación de personas, exhaustividad del GT o PTS originales.

## Propuesta técnica — Etapa 2B (no implementada)

1. Resolver primero MOT17 escala/registro y protocolo de exclusiones; PETS es el candidato más simple por coincidencia de resolución/FPS y MOT15. Revisar registros inicio/mitad/final y eventos rápidos, comparando offsets ±1/±2. Registrar revisor, metodología, versión/hash de video y GT, intervalo permitido y decisión. No habilitar casos por simple coincidencia de conteos.
2. Conservar un registro de aprobación independiente ligado a esos hashes y al perfil de normalización; el futuro evaluador validará ese registro y el manifiesto. Preparar un adaptador de selección, sin modificar el procesamiento existente. Verificar hashes otra vez al evaluar.
3. Implementar adaptadores GT/predicciones hacia un contrato común cero-basado y en coordenadas del MP4. Normalizar clases semánticas, escalas, mark, distractores, regiones ignoradas y frames fuera de dominio. Mantener bbox original para comparar geometría amodal; no aplicar clipping indiscriminado. No reinterpretar null como visible/activo.
4. Leer predictions.jsonl y metadata.json sin repetir inferencia. Validar schema, modo detection/tracking, integridad/completitud de frames, cajas, IDs, hashes y correspondencia. IDs desconocidos/detecciones sin ID necesitan una regla explícita: no fabricarlos ni descartar errores de tracking silenciosamente.
5. Evaluar detección con matching uno a uno y umbral IoU declarado; tracking con implementación validada de métricas y pruebas con casos de identidad conocidos. Si se propone TrackEval, revisar su disponibilidad y pedir autorización antes de instalar o descargar dependencias. Mantener perfiles MOT15, MOT17 y CAVIAR separados cuando el protocolo difiera.
6. Mantener Oxford bloqueado hasta recuperar/verificar la integridad y el dominio temporal. Un eventual prefijo debe conservar índices y exclusiones, aprobarse como caso derivado y compartir recording_group con el original. No reparar usando YOLO.
7. Separar dev/validation por grabación original: variantes MOT17 y conversiones/recortes no pueden cruzar splits. Incorporar grabaciones independientes reales del equipo en validation cuando existan; no optimizar en esa reserva. Mantener prueba_01 como EXPLORATORY.
8. Entregar informes de métricas con cobertura, exclusiones y versión de protocolo; sólo luego proponer experimentos de configuración. No se autoriza ni implementa tuning, zonas A/B, conteo o integración adicional en esta entrega.

## Git y revisión pendiente

Estado inicial limpio; rama correcta. Estado final comprobado: sólo README.md modificado y cinco archivos nuevos enumerados arriba. Se inspeccionaron el diff, el diff preparado (vacío) y los archivos nuevos; git diff --check pasó. Los 54 archivos funcionales existentes controlados por hashes permanecen idénticos y el README conserva todos sus bytes anteriores, con una sección añadida. Git sólo advierte la normalización LF/CRLF del README al próximo uso; no hay errores de whitespace. No se hizo add, commit, push, merge ni cambio de rama. Propuesta de commit, después de revisión humana: `feat(vision): add read-only dataset audit and conservative manifest`. No continuar a 2B sin revisión del equipo.

## Fuentes primarias consultadas

- [MOTChallenge, publicación de los autores](https://link.springer.com/article/10.1007/s11263-020-01393-0): formatos/protocolos y diferencias entre ediciones.
- [TrackEval, documentación oficial](https://github.com/JonathonLuiten/TrackEval/blob/master/docs/MOTChallenge-Official/Readme.md): estructura de secuencias; distinguir resultados de diez columnas de GT MOT17 de nueve.
- [CAVIAR, página de los autores](https://homepages.inf.ed.ac.uk/rbf/CAVIARDATA1/): emparejamiento de archivos, XML, imágenes, objetos estáticos y duplicación de frames de adquisición.
- [Oxford, publicación de Benfold y Reid](https://robots.ox.ac.uk/ActiveVision/Publications/benfold_reid_cvpr2011/benfold_reid_cvpr2011.html): naturaleza del GT de cabezas. La antigua página de formato no fue accesible; la interpretación TOP permanece provisional.

Las mediciones, hashes y problemas de esta entrega provienen de los archivos locales, no de números históricos ni de metadatos de páginas de descarga.
