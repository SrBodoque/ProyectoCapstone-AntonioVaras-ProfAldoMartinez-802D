# LimpIA — Etapa 2A.1: revisión visual y aprobación reproducible

Entrega local: 2026-11-02, America/Santiago. Rama: `feature/pruebas-automatizadas`.
No se implementan métricas ni inferencia. No se repite la auditoría completa de 2A.

## Estado de los tres candidatos

| Secuencia | Estado real | Escala candidata | Traslación candidata | Offset aprobado | Intervalo propuesto si se aprueba offset 0 |
|---|---|---|---|---|---|
| PETS09-S2L1 | NEEDS_VERIFICATION | 1,0 × 1,0 | 0 × 0 px | Ninguno | índices video 0–794 |
| MOT17-02 | NEEDS_VERIFICATION | 0,5 × 0,5 | 0 × 0 px | Ninguno | índices video 0–599 |
| MOT17-04 | NEEDS_VERIFICATION | 0,5 × 0,5 | 0 × 0 px | Ninguno | índices video 0–1049 |

No hay aprobaciones reales ni casos READY. `eligible_sequence_ids=[]` en el estado
derivado. Las decisiones de aprobación de las pruebas usan exclusivamente videos
sintéticos, nombres de revisor que lo indican y temporales propios eliminados por
la fixture; no aprueban material académico.

Las láminas inspeccionadas por el asistente apoyan la correspondencia general y las
escalas propuestas. No proporcionan evidencia suficiente para certificar offset
exacto, ausencia de todo crop/desplazamiento residual, todas las oclusiones o precisión
subpíxel. Las cajas corporales pueden ser amodales. Se requiere la revisión humana
de las muestras y los límites antes de elegir un offset y un intervalo.

Oxford, CAVIAR y prueba_01 no se habilitan en esta extensión. Sus archivos, el
manifiesto 2A y los módulos anteriores permanecen intactos.

## Evidencias concretas

El ZIP de entrega contiene `review_final/` con un paquete por secuencia. Usar estos
paquetes finales; las carpetas de preparación intermedia no son la entrega.

Cada paquete contiene:

- `review.html`: página autónoma, sin peticiones de red ni servidor, con imágenes
  originales seleccionadas embebidas, cajas GT, IDs, transformaciones y cinco offsets.
- `contact_sheet.jpg`: comparación estática de los cinco offsets sobre el mismo
  fotograma; las coordenadas de datos permanecen en píxeles del MP4 aunque la lámina
  pueda redimensionarse para mostrarla.
- `review.json`: contexto verificable y hashes de HTML/lámina, sin aprobación.
- `decision.pending.json`: plantilla PENDING con revisor/fecha vacíos, offset null
  y confirmaciones falsas. No es un archivo aprobable tal como se entrega.

| Secuencia | Muestras video, índice desde cero | Candidatos GT por muestra |
|---|---|---|
| PETS09-S2L1 | 0,1,2,198,352,353,354,355,356,397,596,669,670,671,672,673,792,793,794 | -2,-1,0,+1,+2 |
| MOT17-02 | 0,1,2,3,4,75,76,77,78,79,150,300,450,597,598,599 | -2,-1,0,+1,+2 |
| MOT17-04 | 0,1,2,262,401,402,403,404,405,525,787,970,971,972,973,974,1047,1048,1049 | -2,-1,0,+1,+2 |

Son 54 imágenes seleccionadas y 270 combinaciones imagen/offset, incluidas las
combinaciones fuera de dominio en los bordes. No se califican esas combinaciones
como GT vacío. Se decodificó secuencialmente desde el inicio hasta el mayor índice
solicitado, reutilizando `VideoSource`; no se usan búsquedas por segundos ni seeks
aproximados. Sólo las muestras seleccionadas se guardan en las evidencias.

La selección incluye inicio, cuartiles, mitad, final y vecindades ±2 de dos instantes
separados con solapamiento geométrico alto entre cajas de peatones activos. Son
candidatos a revisar, no oclusiones certificadas ni detecciones automáticas. En
MOT17-02 un candidato está muy cerca del inicio; revisar también 75–79 y usar
`--frames` para añadir cruces que el revisor considere relevantes.

## Índices y transformaciones

Regla temporal única: `gt_index = video_index + offset`. El número original MOT es
`source_frame = gt_index + 1`. Nunca se renumeran los videos, ni las personas, ni las
filas fuente. Por ejemplo, video índice 100 con offset +2 consulta frame fuente 103;
con offset -2 consulta frame fuente 99.

Con N frames, el dominio común es `[max(0,-offset), min(N-1,N-1-offset)]`, inclusivo.
Un offset +2 excluye los dos últimos frames; un offset -2 excluye los dos primeros.
El registro rechaza intervalos que excedan ese dominio. Un intervalo menor requiere
también revisión y anotación explícita de ambos límites originales.

Convención espacial preservada en raw: MOT left/top desde 1 y XYWH. Primero se
resta 1 a left/top, después se convierte a XYXY y se aplica escala y traslación:

`x0=(left-1)*sx+dx; y0=(top-1)*sy+dy; x1=x0+width*sx; y1=y0+height*sy`.

PETS: resolución GT/video 768×576, escala 1. MOT17: GT 1920×1080 y video 960×540,
escala 0,5. La candidata no añade crop ni traslación. Las cajas negativas o fuera
de imagen se mantienen como datos: sólo el lienzo de dibujo las recorta. El
visualizador HTML distingue ese recorte gráfico de una transformación del dataset.

Se puede generar otra candidata con `--transform archivo_nuevo.json`, usando el
esquema completo `context.spatial_transform` del review.json. Si se cambia escala,
traslación o política, es necesaria evidencia nueva y revisión nueva. La decisión
no puede cambiar la transformación de un paquete ya generado. No se ofrece una
bandera para saltar estas verificaciones.

DPM/FRCNN/SDP se leen y deben compartir exactamente GT y metadatos con lo auditado;
se conserva DPM como localizador canónico del GT. No se leen detecciones DPM como
verdad terreno ni se crean tres grabaciones independientes.

## Política académica propuesta

MOT17: el objetivo es clase 1 con mark distinto de cero. Las clases 2,7,8,12 se
mantienen como distractores; mark=0 excluye una fila GT del objetivo. Otras clases
no se convierten en máscaras universales. El futuro preprocesamiento debe asociar
predicciones y GT uno a uno antes de retirar asignaciones a distractores, con IoU
0,5 según el perfil consultado. No hay regiones de multitud inventadas. Esta etapa
sólo clasifica y muestra esas categorías, sin ejecutar matching de predicciones.

PETS/MOT15: no hay columna de clase ni visibilidad; XYZ se conserva como tal. Se
puntuarían filas con mark distinto de cero bajo el protocolo de peatones, sin el
preprocesamiento de distractores de MOT17. Valores ausentes siguen siendo null.

No se impone umbral de visibilidad, área mínima ni clipping de cajas para evaluar.
El futuro evaluador debe mantener el perfil aprobado. La política está versionada
y su contenido se vincula a cada revisión y aprobación.

Fuente primaria consultada: [implementación oficial de TrackEval para MOT](https://github.com/JonathonLuiten/TrackEval/blob/master/trackeval/datasets/mot_challenge_2d_box.py).
No se instaló ni se ejecutó TrackEval. La equivalencia del futuro evaluador con
ese preprocesamiento deberá probarse en 2B, sin ampliación de alcance ahora.

En las evidencias: verde=peatón activo; naranja=peatón mark=0; cian=distractor;
gris=otra clase. En HTML, mark=0 usa trazo discontinuo incluso cuando la clase es
distractor u otra. La tabla conserva clase, mark, visibilidad, coordenadas fuente
y coordenadas transformadas. Otras clases se pueden mostrar por separado para que
sus cajas grandes no oculten las personas.

## Cómo abrir y usar el visualizador

Desde `capstone-vision`, PowerShell, con el entorno existente:

```powershell
& .\.venv\Scripts\python.exe -B -m src.view_ground_truth --manifest docs/dataset_audit_2a_manifest.json --sequence PETS09-S2L1
```

Sustituir `--sequence` por MOT17-02 o MOT17-04 para los demás casos. El visualizador
nativo abre el MP4 con cajas GT; no guarda imágenes al navegar. Controles:

| Tecla | Acción |
|---|---|
| n / p | Muestra seleccionada siguiente / anterior |
| . / , | Fotograma exacto siguiente / anterior |
| a / d | Offset anterior / siguiente entre -2 y +2 |
| o | Mostrar/ocultar otras clases |
| q / Escape / cerrar ventana | Salir y liberar recursos |

Para comenzar en otro offset y añadir instantes concretos:

```powershell
& .\.venv\Scripts\python.exe -B -m src.view_ground_truth --manifest docs/dataset_audit_2a_manifest.json --sequence PETS09-S2L1 --offset -1 --frames 352,353,354,355,356
```

La navegación adicional se decodifica secuencialmente y limita su caché; puede ser
más lenta al retroceder que un seek aproximado. No es un reproductor de tiempo real
ni prueba de rendimiento. No modifica la captura de cámara de la aplicación.

Para una copia nueva de evidencias (el destino no debe existir):

```powershell
& .\.venv\Scripts\python.exe -B -m src.view_ground_truth --manifest docs/dataset_audit_2a_manifest.json --sequence PETS09-S2L1 --export logs/review_2a1_PETS_01
```

El HTML se abre localmente como un archivo normal. No necesita servidor. Permite
alternar las cinco cajas candidatas, revisar sus datos y preparar una decisión.
El formulario requiere cargar el review.json del mismo paquete para calcular su
SHA-256 localmente; si el navegador no dispone de esa función, completar una copia
nueva de decision.pending.json con un editor. No cambiar el review.json.

## Qué debe aprobar una persona y cómo registrarlo

1. Revisar todas las muestras y comparar los cinco offsets, incluidos los avisos
   de fuera de dominio. Confirmar por el video nativo los casos ambiguos.
2. Comprobar alineación, IDs, oclusiones y entradas/salidas, además de escala,
   posible crop y desplazamiento residual. La herramienta no decide el ganador.
3. Elegir offset e intervalo y revisar sus dos límites. Si esos límites no están
   en el paquete, inspeccionarlos con el visualizador y anotarlos como índices
   adicionales revisados; no marcar un frame que no se haya visto.
4. Revisar la política de clases/exclusiones. Mantener las diferencias MOT15/MOT17.
5. Registrar revisor real, fecha YYYY-MM-DD, conclusión y dudas. Confirmar de forma
   expresa los seis aspectos listados. En HTML marcar cada muestra tras revisar sus
   cinco candidatos y descargar `decision.reviewed.json`. También se puede preparar
   ese archivo manualmente a partir de la plantilla sin cambiar ningún original.

La plantilla incluye todos los campos exigidos. El comando rechaza PENDING,
confirmaciones ausentes, revisor/fecha/notas vacíos, muestras sin registrar,
intervalos incompatibles, política diferente y transformaciones no revisadas.
No se ha rellenado ni ejecutado esta aprobación sobre datasets reales.

Después de autorización/revisión humana, suponiendo el paquete de evidencias
copiado sin cambios a una carpeta nueva `review_2a1` dentro de capstone-vision:

```powershell
& .\.venv\Scripts\python.exe -B -m src.dataset_approval --manifest docs/dataset_audit_2a_manifest.json approve --review review_2a1/PETS09-S2L1/review.json --decision review_2a1/PETS09-S2L1/decision.reviewed.json --output logs/PETS09-S2L1_approval_01.json
```

Cambiar secuencia y rutas para MOT17. No reutilizar el nombre de un archivo de
aprobación anterior: se exige salida nueva. Este registro no escribe sobre video,
ZIP, anotación, manifiesto o evidencia. Una aprobación local atribuye la decisión
al revisor declarado; no autentica su identidad ni proporciona firma digital.

## Qué valida el registro y cómo obtener READY

El registro incluye ID de secuencia/grupo, hash del MP4, hash del ZIP fuente y del
miembro GT elegido, transformaciones, offset, política, intervalo, muestras
revisadas, evidencia, revisor y fecha. También vincula el contenido de los módulos
de lectura/revisión y la plantilla HTML: una modificación de código que altere
interpretación o dibujo invalida la revisión aunque no cambie el video.

Antes de registrar y al consumir se verifican los inputs contra los hashes
auditados, los miembros y metadatos GT, la política y los hashes de las evidencias.
Si cambia el video, ZIP, GT elegido, transformación, offset solicitado, protocolo,
HTML/lámina o contexto, la validación falla. Un cambio de bytes del código, incluso
por normalización de finales de línea, exige regenerar/revisar evidencia. Conservar
las versiones exactas revisadas.

Para derivar un manifiesto portable sólo con aprobaciones validadas:

```powershell
& .\.venv\Scripts\python.exe -B -m src.dataset_approval --manifest docs/dataset_audit_2a_manifest.json status --binding logs/PETS09-S2L1_approval_01.json review_2a1/PETS09-S2L1/review.json --output logs/datasets_verified_01.json
```

Se pueden repetir pares `--binding APROBACION REVIEW` para otros casos. No se
aceptan dos decisiones para la misma secuencia. Sin bindings, el estado no habilita
ningún caso. Editar READY en el manifiesto original no sirve: se restablece el
estado de los tres candidatos y se deriva exclusivamente de los registros válidos.
El manifiesto original nunca se modifica.

El futuro sistema 2B debe llamar a
`src.dataset_approval.verified_manifest(manifest_path, datasets_root, bindings)` en
cada selección y comprobar la configuración solicitada con `validate_approval`
(`expected_transform`, `expected_offset`, `expected_policy`). No confiar en un
JSON guardado que diga READY ni en un único booleano. El selector antiguo de 2A
puede leer un resultado recién validado, pero por sí solo no comprueba el registro.
El manifiesto derivado declara el intervalo/configuración aprobados; la futura
evaluación deberá aplicarlos sin renumerar los índices originales.

## Portabilidad

La lectura siempre resuelve video y ZIP a partir de sus rutas relativas y del
directorio explícito de datasets. Se ignora el dataset_root absoluto heredado de
2A. Por defecto se usa videos_testing junto al proyecto; para otro equipo:

```powershell
& .\.venv\Scripts\python.exe -B -m src.view_ground_truth --manifest docs/dataset_audit_2a_manifest.json --datasets D:/LimpIA/datasets --sequence PETS09-S2L1
```

El manifiesto derivado usa `dataset_root: "."` y declara que ese punto significa
la raíz de datasets suministrada por el consumidor, no el directorio del JSON.
Los paquetes de evidencia son autónomos; review.json localiza HTML/lámina con
rutas relativas a su propia carpeta. Aprobaciones y decisiones no contienen rutas
absolutas personales. Cambiar sólo la ubicación no invalida hashes. Las pruebas
incluyen una copia idéntica de inputs a otra raíz. Se rechazan rutas absolutas,
traversal y enlaces en las rutas de datos. No se modifica la política de rutas de
los módulos anteriores.

## Archivos y conservación

Sólo se crearon archivos nuevos en el proyecto:

- `src/dataset_review.py`: contratos, contexto/hash, clases, transformaciones,
  selección geométrica y decodificación exacta de muestras.
- `src/view_ground_truth.py`: visualizador nativo y exportación de evidencia.
- `src/ground_truth_review.html`: interfaz de revisión offline.
- `src/dataset_approval.py`: decisión, aprobación, revalidación y estado derivado.
- `tests/ground_truth_test_support.py`, `tests/test_ground_truth_review.py`,
  `tests/test_dataset_approval.py`: fixtures y pruebas nuevas.
- `docs/DATASET_VERIFICATION_2A1.md` y `docs/dataset_review_pending_2a1.json`.

Se conservaron idénticos por hash los 72 archivos previos controlados, incluidos
los módulos de 2A y su manifiesto, README, instrucciones, configuración y pruebas.
Los 17 archivos de entrada inventariados mantienen sus hashes. La descarga .part
no se abrió ni borró. No se movieron, renombraron ni sobrescribieron originales.
No se modificaron detector, tracker, cámara, selección CPU/GPU ni baseline 0.65.
No se tocaron pesos ni se instalaron dependencias. Los tests sólo escriben sus
temporales propios; las evidencias de entrega quedan fuera de videos_testing.

## Validación ejecutada y límites

Baseline: 23/23 pruebas de Etapa 2A. Nuevas: 14 de revisión/transformación y 17 de
aprobación. La regresión incluye esas 23 anteriores y los 383 casos seleccionados
de la etapa anterior, con sus repeticiones intencionales de test_video_regression.

| Proceso final independiente | Nuevas | Regresión seleccionada | Fallos | Errores | Omisiones dentro de selección |
|---|---:|---:|---:|---:|---:|
| validation_1 | 31 | 406 | 0 | 0 | 0 |
| validation_2 | 31 | 406 | 0 | 0 | 0 |
| validation_3 | 31 | 406 | 0 | 0 | 0 |

Los casos incluyen signos/límites de offsets, origen MOT y escala, extents amodales,
categorías de exclusión, frames seleccionados, lectura secuencial, salida nueva,
rechazo de escape de rutas, contextos relocados, GUI simulada/liberación, hashes de
video/ZIP/evidencias, configuración, política, registro explícito, cambio de código
y rechazo de estados READY editados a mano. Las pruebas no debilitan las existentes.

Como en 2A, se excluyeron deliberadamente los módulos de integración real:
test_botsort_reid_integration.py, test_fasttracker_integration.py,
test_hito3_integration.py, test_mp4_inference_integration.py y
test_recovery_integration.py. No se presentan como aprobados ni como omisiones
que acrediten hardware. Ningún proceso de la selección importó ultralytics.
`pip check` pasó sin dependencias rotas. CPU local, entorno existente; no se valida
GPU, webcam, inferencia ni reproducción de tiempo real.

El motor de dibujo y los JPEG se comprobaron sobre las secuencias reales; se
inspeccionaron sus láminas. Las pruebas de navegación de GUI usan controles
simulados, no una sesión física aprobada. La sintaxis de JavaScript pasó con Node.
La prueba interactiva en navegador no pudo completarse: Computer Use terminó al no
poder determinar la URL del navegador con suficiente confianza. Se detuvieron las
acciones UI y no se intentó eludirlo. El HTML queda pendiente de aceptación visual
interactiva por ustedes; no se afirma que su formulario haya sido probado en un
navegador real. Completar decision.pending.json con un editor es una alternativa
prevista, igualmente validada por el comando local.

Para ejecutar las pruebas nuevas desde capstone-vision:

```powershell
& .\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_ground_truth_review.py -v
& .\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_dataset_approval.py -v
```

La entrega incluye `validate_stage2a1.py` y los logs/JSON de tres procesos. Para
reproducir exactamente la selección ampliada, desde la carpeta del script:

```powershell
& RUTA_AL_PROYECTO/.venv/Scripts/python.exe -B ./validate_stage2a1.py RUTA_AL_PROYECTO ./nueva_validacion_1.log
```

Repetir con nombres 2 y 3 en procesos nuevos; el script fija el cwd al proyecto
para respetar las expectativas de los tests existentes. Se rechaza sobrescribir
logs. No se ha realizado una prueba de aceptación humana ni una certificación
de ground truth automática.

## Git y siguiente paso

Se preserva el estado previo de 2A, todavía con README modificado y archivos sin
seguimiento. Los nuevos archivos de esta extensión se informan aparte; no se
incluyeron como propios cambios anteriores ni se hizo add/commit/push/merge/cambio
de rama. Inspeccionar diff, diff preparado y archivos nuevos antes de cualquier
commit. Propuesta después de revisión: `feat(vision): add GT review and hash-bound dataset approvals`.

La herramienta está preparada para la revisión. Lo pendiente es la decisión humana
de cada secuencia y la aceptación interactiva de la interfaz. No se continúa a
Etapa 2B hasta que el equipo revise y autorice esa siguiente etapa.
