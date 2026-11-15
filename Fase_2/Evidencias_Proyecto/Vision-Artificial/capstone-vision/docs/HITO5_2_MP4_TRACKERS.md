# Hito 5.2 — MP4, selección de tracker y conteo sobre predicciones

El flujo reutiliza PersonTracker y los backends instalados. Mantiene separados:
video original, JSON de zonas del video, configuración del tracker y resultados.
No hay barrido automático, selección del mejor tracker ni evaluación contra
eventos anotados en esta entrega.

## Preparación local

El worktree H5.2 integra main y fix/h51-dos-zonas sin modificar la rama de pruebas.
Use el Python existente; no es necesario activar, recrear ni instalar otro entorno.
Ejemplo con las rutas actuales:

~~~powershell
Set-Location 'C:\Users\juanc\Downloads\LimpIA-h52-mp4\Fase_2\Evidencias_Proyecto\Vision-Artificial\capstone-vision'
$origen = 'C:\Users\juanc\Downloads\ProyectoCapstone-AntonioVaras-ProfAldoMartinez-802D\Fase_2\Evidencias_Proyecto\Vision-Artificial\capstone-vision'
$python = Join-Path $origen '.venv\Scripts\python.exe'
$video = Join-Path $origen 'videos_testing\exploratory\prueba_02.mp4'
~~~

Los comandos leen el video y los pesos desde su ubicación existente. No los
copian, mueven ni modifican. Los resultados nuevos quedan en este worktree.
Las carpetas ignoradas no son un respaldo; conservar los originales y las
calibraciones fuera del repositorio conforme al procedimiento de respaldo.

## 1. Generar tracking nuevo

~~~powershell
& $python -B -m src.count_mp4 track --video $video --tracker bytetrack --device cuda:0 --weights-dir $origen --output results_testing
~~~

track no necesita zonas. Crea una ejecución independiente y muestra su directorio.
Para exigir CPU use --device cpu; CUDA no disponible produce error sin fallback.
Cada video obtiene una sesión nueva. No se cambia la preferencia personal.
--weights-dir admite un directorio local externo; no se duplica el peso.

| Selección CLI | Backend/YAML existentes | Pesos requeridos |
| --- | --- | --- |
| bytetrack (predeterminado) | bytetrack; config/bytetrack_capstone.yaml según tracking.json | yolo26n.pt |
| fasttrack o fasttracker | FASTTracker; config/fasttrack_capstone.yaml | yolo26n.pt |
| botsort | BoT-SORT sin ReID; config/botsort_no_reid_capstone.yaml | yolo26n.pt |
| botsort_reid | BoT-SORT/ReID; config/botsort_reid_capstone.yaml | yolo26n.pt y yolo26n-cls.pt |
| recovery | ByteTrack Recovery existente; config/bytetrack_recovery_capstone.yaml | yolo26n.pt |

Se conservan los parámetros de cada YAML. Solo Recovery utiliza su override
existente de confianza 0.10; los demás conservan la confianza general.
El alias fasttrack se registra como selección fasttracker y backend fasttrack.

BoT-SORT sin ReID utiliza la clase oficial BOTSORT con with_reid:false y sin
encoder/diagnósticos de apariencia. Su YAML es independiente y conserva los
demás parámetros del YAML ReID existente, incluido GMC none. No se modifican
los YAML de ByteTrack, FastTrack, Recovery ni BoT-SORT/ReID.
Para ambas variantes BoT-SORT, --confidence 0.25 activa explícitamente el modo
experimental de la sesión; se registra junto con la confianza efectiva y no
escribe detection.json. El modo de cámara histórico conserva su validación
ReID de confianza 0.65 por defecto. Este argumento no se aplica a los otros trackers.
Con confianza YOLO 0.25 y track_high_thresh 0.25, las detecciones por debajo de
ese umbral se filtran antes del tracker: la asociación de baja confianza no
recibe esos candidatos. Esta condición común se conserva y no se optimiza.

Se comprueban archivos locales, dependencias, versión compatible y presencia del
backend. Un fallo no provoca instalación, descarga, cambio de tracker ni uso de
CPU como sustituto de CUDA. Durante la carga/inferencia se bloquean conexiones
de red y escrituras/eliminaciones sobre los pesos y el MP4 de entrada.
Para ReID, la ruta de trabajo del proceso se cambia temporalmente al directorio
de pesos locales y se restaura al terminar; los YAML y resultados usan rutas
resueltas. No se modifica Ultralytics ni se implementa otro motor.

Cambiar tracker o sus parámetros requiere ejecutar track o process de nuevo.
Se crea otro run_id, aunque el video sea el mismo. No se sobrescriben resultados.
La selección de cada comando es explícita; no se elige una ejecución reciente
de manera automática.

## 2. Calibrar A exterior / B puerta en el MP4

La calibración usa un frame fijo y el editor H4 existente, sin cámara, modelos
ni inferencia. --frame selecciona un índice desde cero (predeterminado 0).

~~~powershell
& $python -B -m src.calibrate_mp4_zones --video $video --frame 0 --output results_testing/prueba_02.zones.json --reviewer "Juan"
~~~

Con la ventana enfocada: A/B seleccionan zona; clic izquierdo agrega o arrastra
vértices; Enter/clic derecho cierra el contorno; U quita el último vértice y R
redibuja la zona seleccionada. Pulse S, indique el nombre y Enter para guardar.
Después cierre con q/Escape. El editor conserva sus controles H4 de confirmación
de cambios; el frame del MP4 permanece fijo. Para otro instante reinicie con
otro --frame y una salida nueva.

Revise físicamente que A sea exterior y B corresponda a la puerta. El punto que
clasifica el contador es el centro inferior de la caja. El JSON exportado incluye
polígonos, resolución, frame de referencia, responsable, orientación y SHA-256
del MP4 y del perfil. No contiene tracker, GPU ni parámetros de inferencia.

No se escriben perfiles activos de cámara. Los archivos de trabajo del editor
se crean en results_testing/calibration/<run_id>/profiles/. El JSON final se
crea exclusivamente; si ya existe, se exige otro nombre (por ejemplo v2).
Cerrar sin guardar no inventa ni exporta zonas. No se almacenan fotogramas.

El JSON H5.2 tiene kind=limpia_video_zones. Un perfil H4 de cámara no se interpreta
silenciosamente como perfil de este video. No se aceptan perfiles de otro hash
o dimensión ni orientaciones invertidas/sin confirmación.

## 3. Contar tracking guardado, sin repetir inferencia

Seleccione la carpeta concreta de un caso o de un lote compatible que imprimió
track. La primera ejecución real de prueba_02 ya disponible en este worktree es:

~~~powershell
$tracking = 'results_testing/20261107T015817632553Z-e85970a202c94f62a93fc3158c2c44be'
& $python -B -m src.count_mp4 count --video $video --zones results_testing/prueba_02.zones.json --predictions $tracking --output results_testing
~~~

En otro clon o después de un tracking nuevo, sustituya $tracking por la ruta
real disponible. Clonar Git no recupera esos resultados locales.

count no instancia un tracker ni importa PyTorch/OpenCV; tampoco necesita GPU o pesos ReID.
Usa los IDs y cajas registrados. El dispositivo mostrado como origen pertenece
al tracking anterior; la fase de conteo usa CPU sin inferencia.
Cambiar solo zonas o umbrales permite generar otro conteo sobre esas mismas
predicciones. Cada conteo tiene su propio directorio y hashes.

--count-config selecciona el JSON de umbrales del contador (predeterminado
config/counting.json). Se usa su bloque thresholds; su campo tracker pertenece
al comando de cámara y no sustituye al tracker solicitado por CLI o al registrado
en las predicciones. No se modifica ese archivo al seleccionar otro backend.

Para generar tracking y conteo en una sola operación, con zonas ya confirmadas:

~~~powershell
& $python -B -m src.count_mp4 process --video $video --zones results_testing/prueba_02.zones.json --tracker bytetrack --device cuda:0 --weights-dir $origen --output results_testing
~~~

process valida zonas/umbrales antes de inferir y después reutiliza su tracking
para contar. No realiza dos inferencias por frame. No ofrece comparación
automática con anotaciones ni optimización.

## 4. Visualizar cajas, zonas, diagnósticos y conteos

Use la carpeta concreta de conteo que imprimió count o process:

~~~powershell
$conteo = 'results_testing/counting/<run_id_impreso_por_count>'
& $python -B -m src.view_count_results --video $video --count-results $conteo
~~~

Sustituya el marcador por la ruta real; no es la carpeta del tracking.
El visor reutiliza el reproductor offline existente: espacio pausa/reanuda,
n o punto avanza un frame mientras está pausado, q/Escape o cerrar termina.
No crea archivos, no ejecuta IA ni vuelve a contar. Cajas, IDs, confianza y
trayectorias provienen del tracking guardado; zonas y eventos del conteo seleccionado.
IN/OUT son acumulados hasta el frame mostrado. Pausar o redibujar no los suma.
El panel muestra hasta cuatro diagnósticos por ID, con el frame de su última
actualización; el registro completo está en diagnostics.jsonl. Muestra los
motivos originales de confirmación, espera, pérdida de ID y reinicio, diferenciando
fuera de zonas de fuera de imagen. Las zonas se aplican al centro inferior de
la caja; las trayectorias visuales heredadas dibujan sus centros.

Se verifican hashes de video, zonas y predicciones, estado completed y
coherencia entre eventos y resumen antes de abrir la ventana. Al cerrar se
comprueba que los recursos no cambiaron. --zones y --predictions permiten
reubicar esos recursos manteniendo sus hashes; no recalibran ni reinfieren.
El visualizador no certifica la precisión de tracking ni la identidad de personas.

### Aceptación humana pendiente con prueba_02.mp4

1. Calibre el frame adecuado con A exterior y B junto a la puerta. No seleccione
   zonas para forzar un resultado esperado. Guarde el JSON independiente.
2. Ejecute count usando el tracking ByteTrack ya generado y abra el nuevo visor.
3. Pause y avance los cruces. Compare el punto inferior de cada caja, su ID,
   la permanencia mínima configurada, el diagnóstico y el frame del evento.
4. Verifique A estable -> B estable: un IN; B estable -> A estable: un OUT.
   Un acercamiento sin destino estable, una aparición aislada o permanecer en
   una zona no deben generar eventos. A -> B -> A debe producir IN y OUT;
   un reingreso posterior A -> B debe producir otro IN.
5. Revise recorridos rápidos/lentos, dos personas consecutivas, cruces entre
   personas y pérdidas temporales de ID, cuando existan en el material. Si el
   video no contiene un escenario, déjelo pendiente y pruébelo luego en cámara
   o con otro MP4 y su propio perfil.
6. Registre por separado fallos del contador con ID continuo y errores de
   tracking (IDs cambiados o intercambiados, cajas ausentes). No atribuya la
   continuidad entre IDs diferentes al contador. Si recorridos completos con
   IDs estables siguen produciendo cero eventos, no acepte el hito: conserve
   el run, su JSON y los frames/motivos para diagnóstico.

No se ejecutó esta aceptación humana durante la implementación. La primera
inferencia real disponible solo acredita procesamiento ByteTrack/CUDA; falta
calibrar, ejecutar el conteo y revisar el video con el equipo.

## Matriz explícita con varios MP4 y perfiles

La implementación no depende de nombres de grabaciones. Cada --case recibe
un MP4 local y su JSON explícito, con validación de hash, orientación y resolución
antes de inferir. Los perfiles no se inventan, reinterpretan ni modifican.
Ejemplo con los tres recursos actualmente verificados:

~~~powershell
& $python -B -m src.compare_mp4_trackers `
  --case "$origen/videos_testing/exploratory/prueba_01.mp4" results_testing/prueba_01.zones.v2.json `
  --case "$origen/videos_testing/exploratory/prueba_02.mp4" results_testing/prueba_02.zones.json `
  --case "$origen/videos_testing/exploratory/prueba_03.mp4" results_testing/prueba_03.zones.json `
  --tracker botsort --tracker botsort_reid --weights-dir $origen --output results_testing
~~~

Use --tracker botsort para ejecutar solo la variante sin apariencia. Se exige
YOLO26n, cuda:0 y confianza experimental 0.25 para esta comparación concreta;
los comandos track/process individuales siguen permitiendo CPU. Cada par y
variante crea tracking y conteo nuevos. La ausencia de pesos no provoca fallback
ni descarga: se registra pending y se continúa con las combinaciones disponibles.
Un código de salida 1 indica que alguna combinación quedó pendiente o falló;
130 indica interrupción. No se interpreta una matriz incompleta como aprobada.

La salida queda en results_testing/comparisons/<run_id>/:
comparison.json conserva entradas/hashes, métricas, configuración efectiva,
pesos y eventos; comparison.csv resume la matriz; comparison.md es el informe
legible. runs/ contiene los resultados independientes de tracking y conteo.
Se registran frames, frames con tracks, cajas sin ID y frames afectados,
tiempo del tracking, tiempo del conteo, tiempo total y FPS de procesamiento.
El tiempo de tracking incluye carga del modelo y E/S; el total añade preparación
del runtime y conteo. No son una medida de precisión ni FPS de cámara.

Validación real disponible del 12 de noviembre de 2026:
results_testing/comparisons/20261112T060111716332Z-1a9584c5131249a0be4edbfba82af699/.
BoT-SORT sin ReID completó 734/734, 690/690 y 2349/2349 frames con RTX 5060,
cuda:0 y confianza 0.25; produjo respectivamente IN/OUT 4/2, 2/1 y 7/15.
Las tres variantes ReID quedaron pendientes por falta de yolo26n-cls.pt local.
Se verificó que el lector del visualizador acepta los tres conteos; no se abrió
su GUI ni se certificó precisión, identidad o correspondencia con eventos reales.
No se selecciona ganador. La evaluación requiere anotaciones y aceptación visual.

Para visualizar cualquier combinación completa, seleccione counting_directory
del informe y use el mismo comando de src.view_count_results descrito arriba.
También puede reutilizar ese tracking con count y otro perfil confirmado del
mismo video, creando un conteo independiente sin volver a inferir.

## Resultados y procedencia

El tracking mantiene los formatos v1 existentes: run.json, summary.json y,
por caso, metadata.json, predictions.jsonl y timings.csv. Añade procedencia
compatible: selección/backend efectivo, YAML y parámetros, configuraciones y
hashes, directorio/pesos locales verificados, pesos realmente usados, versiones
y dispositivo efectivo. No se modifican los parámetros de YOLO o ByteTrack.

Cada conteo crea results_testing/counting/<run_id>/:

| Archivo | Contenido |
| --- | --- |
| run.json | Hashes de MP4, JSON de zonas, perfil, umbrales, metadatos/predicciones; configuración/modelo/pesos del tracking y dispositivo de origen; reloj utilizado. |
| events.jsonl | Una fila por confirmación: IN/OUT, ID, episodio, timestamp en segundos y frame_index desde cero. |
| diagnostics.jsonl | Cambios de estado y motivos de espera/reinicio, con frame, timestamp e ID. |
| summary.json | Estado, frames, IN, OUT, eventos y frames con puntos inválidos. accuracy_validated permanece false. |

Las predicciones deben corresponder al hash del MP4, estar completas, ser de
tracking y contener todos los índices sin duplicados. Filas ausentes no se
convierten en detecciones vacías ni se rellenan con cajas de otros frames.
Se tolera el orden diferente de filas porque se indexan por frame_index.
Datos corruptos o cajas descartadas por el lector impiden acreditar el conteo.

El reloj usa timestamp_ms creciente del video/predicciones. Si no es válido,
se utiliza una única escala frame_index/FPS, registrada explícitamente. Esta
alternativa puede ser aproximada en videos de FPS variable; no sustituye una
verificación temporal antes de comparar eventos anotados. Sin ninguno de esos
relojes válidos, se detiene. No se usa el tiempo de procesamiento del computador.

Una interrupción conserva parciales con estado interrupted; un error produce
failed. Solo completed indica terminación del procesamiento, no precisión física.
Los IDs son temporales y no representan personas únicas entre ejecuciones.

## Validación y pendientes

Primera prueba real: prueba_02.mp4, ByteTrack + yolo26n.pt, RTX 5060 cuda:0,
690/690 frames, completed. En esa primera ejecución faltaba la calibración.
Posteriormente se proporcionaron los tres perfiles y se ejecutó tracking y conteo
real BoT-SORT sin ReID según la matriz anterior. No se inventaron zonas.
La aceptación visual de los nuevos conteos, FastTrack y BoT-SORT/ReID siguen
pendientes. El clasificador ReID no está disponible y no se descargó.

Las pruebas automatizadas usan archivos temporales propios, lectura/dibujo de
OpenCV y modelos/GUI simulados donde se indica. No equivalen a aceptación visual.
Tres validaciones finales independientes: 328/328 cada una, sin fallos, errores
ni omisiones (55 H5.2, 89 MP4, 38 visualizador, 63 contador/configuración y
83 contratos históricos de BoT-SORT/ReID, FastTrack y Recovery).
Regresión general: 588 descubiertas, 585 registradas por unittest, cero fallos
y errores. Quedan cinco casos sin acreditar: tres de la clase ReID sin pesos
locales en el worktree, una integración MP4 heredada que exige pesos en su raíz,
y una comprobación de enlaces simbólicos sin permisos Windows. Son tres entradas
de omisión; no se consideran aprobadas. La prueba real ByteTrack externa de
690 frames se informa por separado y no sustituye esas pruebas omitidas.
Los tests históricos usan un fixture explícito 0.65, aislado del tuning local
de detection.json. Sus expectativas no se debilitaron. Las pruebas nuevas
verifican por separado la confianza experimental 0.25, nombres/rutas arbitrarios,
matrices con varios videos, integridad, errores, interrupción y reutilización en
el visualizador. La inferencia ReID se simula donde faltan recursos y no se
declara validada en GPU.
La aceptación humana de precisión e identidades de los nuevos conteos sigue pendiente.
Conserve los registros MOT17-04 existentes: no son aprobación de conteo de baños.

~~~powershell
& $python -B -m unittest discover -s tests -p 'test_h52*.py' -v
& $python -B -m unittest discover -s tests -p 'test_video*.py' -v
& $python -B -m unittest discover -s tests -p 'test_stage15*.py' -v
& $python -B -m unittest discover -s tests -p 'test_count*.py' -v
& $python -B -m unittest discover -s tests -p 'test_track_count.py' -v
& $python -B -m unittest discover -s tests -p 'test_botsort_reid.py' -v
& $python -B -m unittest discover -s tests -p 'test_fasttracker.py' -v
& $python -B -m unittest discover -s tests -p 'test_recovery.py' -v
& $python -B -m unittest discover -s tests -p 'test*.py' -v
~~~

Ejecutar tres procesos independientes de la batería relevante después del último
cambio funcional. Las omisiones se informan como pendientes.
