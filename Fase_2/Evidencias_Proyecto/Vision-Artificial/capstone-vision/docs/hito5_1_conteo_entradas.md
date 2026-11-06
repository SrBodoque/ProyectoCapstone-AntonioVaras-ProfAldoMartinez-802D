# Hito 5.1 — Conteo de entradas con A/B

Este comando cuenta ingresos observados durante una sesión: **A → B → salida frontal de B hacia el baño**. No suma por aparecer en B, permanecer allí o perder un ID. No hay contador OUT, restas ni ocupación. El contador comienza en cero en cada ejecución y permanece solo en memoria.

## Revisar el significado de las zonas antes de probar

**En este encargo A es la aproximación exterior y B es la zona cercana al baño.** La documentación histórica del Hito 4 describe el significado contrario. El calibrador conserva las mismas letras y los mismos archivos; no se ha modificado ni se intercambian polígonos automáticamente. Revise visualmente su perfil: para H5.1, una persona que entra debe atravesar primero A y después B.

No hace falta recalibrar en cada ejecución. Solo ajuste el perfil si su disposición física no corresponde a ese orden o si se movió la cámara. El programa informa este significado al iniciar, pero no puede identificar por sí mismo dónde está realmente el baño.

## Ejecución en Windows

Abra PowerShell en la carpeta habitual `capstone-vision`, con el `.venv` y los modelos que ya utiliza. La entrega no incluye entornos, pesos ni preferencias personales. No recree un entorno funcional.

Si necesita seleccionar o cambiar cámara/dispositivo, ejecute voluntariamente los selectores existentes; no se ejecutan desde el contador:

```powershell
& .\.venv\Scripts\python.exe -m src.camera_selector
& .\.venv\Scripts\python.exe -m src.device_selector
```

Para crear, revisar o editar A/B:

```powershell
& .\.venv\Scripts\python.exe -m src.zone_calibrator
```

A/B seleccionan zona; clic izquierdo agrega o permite arrastrar vértices; Enter o clic derecho cierra; S guarda y activa. P permite cargar otro perfil y G activarlo después de revisarlo. Los controles completos permanecen en `docs/hito4_zonas.md`, teniendo presente el nuevo significado A exterior/B baño.

Cierre el calibrador y ejecute:

```powershell
& .\.venv\Scripts\python.exe -m src.track_count
```

Con el entorno ya activado, el comando equivalente es `python -m src.track_count`. Las siguientes ejecuciones cargan automáticamente el mismo perfil activo. Q, Esc, X o Ctrl+C cierran y liberan la cámara. Cada reapertura inicia otra sesión con cero entradas; el total anterior no se recupera ni se guarda.

Los comandos anteriores (`src.main`, `src.detect`, los trackers, `src.zone_calibrator` y `src.track_zones`) siguen independientes. Cierre un visor antes de abrir otro que use la cámara.

## Qué se observa y qué se cuenta

Se reutilizan `ZoneStore.load_active`, la geometría H4 y el punto inferior central de la caja: `((x1+x2)/2, y2)`. Las posiciones se normalizan respecto al frame efectivo. La pertenencia A/B/FUERA sigue calculándose en `ZoneProfile.classify`, con su política de bordes y prioridad A en una frontera compartida.

**FUERA es una posición visible fuera de ambos polígonos. No significa que desapareció la detección.** El espacio entre A y B puede ser FUERA, igual que el espacio posterior a B. No se crean FUERA 1/2/3, otra zona ni una línea final.

La secuencia A → B directa también es válida si el muestreo omitió el espacio intermedio: exige estabilidad en ambas zonas, cruce frontal de A y continuidad de movimiento. No se permite que un salto arbitrario complete la historia.

Las detecciones sin ID muestran su posición y zona mediante la visualización existente; no alimentan la FSM, porque no existe una trayectoria temporal que validar.

## Dirección y borde de salida

1. Se calculan los centroides de los polígonos A y B. Antes de medir ángulos se compensa la relación ancho/alto del frame, para trabajar con una métrica proporcional a píxeles cuadrados.
2. El vector centroide A → centroide B define el sentido de ingreso. La distancia entre ellos, **D**, es la unidad espacial. D no representa metros ni una calibración del suelo.
3. El contador exige una calibración conservadora: polígonos convexos, separados u ordenados sin superposición de sus proyecciones longitudinales, y solapamiento transversal de al menos la mitad del ancho de la zona más estrecha. Sus interiores deben admitir el margen configurado.
4. Debe haber un borde frontal utilizable en A y una salida frontal de B visible dentro del frame. La normal exterior del borde debe estar a no más de 45° del sentido A → B. Se admiten varios bordes que cumplan ese criterio.
5. Para una salida concreta se intersecta el segmento entre la última posición observada dentro del polígono y la primera fuera con **su propio contorno**. Debe cruzar un único borde frontal, apartado de las esquinas al menos el margen configurado. La dirección del desplazamiento también debe estar dentro del cono de 45°.
6. Después de B se requieren posiciones FUERA que sobrepasen el borde, tanto en su normal exterior como longitudinalmente, al menos el margen. El desplazamiento desde la posición interior de referencia debe seguir siendo coherente con el sentido de ingreso.

No se almacena ni se dibuja una línea independiente. El punto de intersección y la normal son evidencia temporal del borde del polígono que ya existe.

La revisión geométrica bloquea el arranque con un mensaje cuando no puede inferirse una orientación adecuada. H4 admite polígonos cóncavos; esta primera versión del contador los rechaza deliberadamente. Una geometría válida en el calibrador no acredita automáticamente un acceso adecuado para conteo.

Un giro pronunciado, perspectiva extrema o zonas mal alineadas puede impedir confirmar entradas. La aplicación tampoco puede detectar que el baño real está en otro sentido pese a que A/B parezcan geométricamente válidas. Revise el encuadre y mida el comportamiento; no se promete precisión física.

## Máquina de estados por ID

| Estado mostrado | Interpretación y avance |
| --- | --- |
| SIN_RECORRIDO | Espera observaciones estables en A. Si aparece primero en B, no hereda un origen en A. |
| INICIO_EN_A | Hay evidencia estable dentro de A; todavía no hay entrada. |
| AVANZANDO_A_B | Se observó salida frontal de A, avanzando hacia B; puede atravesar FUERA. |
| EN_B | Se alcanzó B con estabilidad después de A; no se cuenta por quedarse allí. |
| CONFIRMANDO_SALIDA_B | Se cruzó un borde frontal de B y se comprueban distancia y estabilidad temporal fuera. |
| ENTRADA_CONFIRMADA | Emitió una entrada una sola vez para ese episodio. |
| CANCELADO | Retroceso, salida lateral/ambigua, salto, falta de continuidad o expiración. |
| SALIDA_OBSERVADA | Se observó sentido B → A, o regreso a A después de una entrada. No emite un evento OUT. |

Un evento `EntryEvent` contiene número de entrada de la sesión, ID temporal, episodio y timestamp. Solo se devuelve en el frame de confirmación. El motor no acumula una lista de eventos ni la escribe en disco.

Los estados confirmado/cancelado/salida requieren **rearme espacial**: volver a A de forma estable y cruzar su borde posterior hacia el exterior, con margen y estabilidad. Después deben observarse nuevamente A, B y la salida frontal de B. Esperar un número fijo de segundos o volver inmediatamente a B no rearma el episodio. Una entrada, salida completa y nueva entrada puede sumar dos; el total nunca se resta.

## Umbrales iniciales

`config/counting.json` contiene el tracker y estos ocho parámetros. Son valores iniciales sujetos a pruebas físicas, no parámetros ya optimizados. Mantenga los ocho nombres y JSON válido. Los detalles del tracker están en `docs/cambiar_tracker_hito5.md`.

| Parámetro | Inicial | Interpretación |
| --- | ---: | --- |
| `zone_dwell_seconds` | 0.12 | Tiempo mínimo de observaciones coherentes dentro de A/B y en el retorno a A. |
| `exit_dwell_seconds` | 0.12 | Tiempo mínimo con margen fuera de B o fuera de A durante el rearme. |
| `min_observations` | 2 | Mínimo de observaciones para cada evidencia estable, además del tiempo. |
| `position_margin` | 0.04 | 4 % de D; interior de zona, distancia tras el borde y separación respecto de vértices. |
| `max_gap_seconds` | 0.50 | Intervalo máximo para conservar continuidad. |
| `episode_timeout_seconds` | 12.0 | Duración máxima desde el inicio estable en A para completar la entrada. |
| `state_ttl_seconds` | 30.0 | Elimina un estado cuando el ID lleva más de este tiempo sin verse. |
| `max_speed_per_second` | 4.0 | Desplazamiento máximo de 4 D/s, más un margen de tolerancia por observación. |

La estabilidad exige simultáneamente tiempo y observaciones; no asume 30 FPS. El adaptador usa `time.monotonic()`, y los tests proporcionan timestamps explícitos. Se verificó el mismo recorrido sintético muestreado a 5, 10, 20, 30 y 60 FPS; no es una medición de rendimiento real. Con intervalos superiores a `max_gap_seconds`, esta configuración cancela continuidad y puede omitir entradas.

Un retroceso longitudinal superior a **dos márgenes respecto del máximo avance observado** cancela el recorrido, incluso si se acumula mediante pequeños pasos. Una salida lateral o inversa de A/B también cancela. Las posiciones cercanas al borde no acumulan evidencia de residencia interior. Volver a B durante una confirmación anula la evidencia de salida; una oscilación breve no genera múltiples eventos.

Las políticas geométricas de 45°, alineación transversal del 50 %, convexidad y un máximo de 512 estados recientes son límites conservadores de esta versión, no otros parámetros de ajuste por habitación. Si se supera el límite de estados, se detiene con error sin borrar protecciones de episodios para continuar contando.

Validación: números positivos y finitos; observaciones enteras de 2 a 10; margen entre 0.005 y 0.2; tiempos de estabilidad y gap menores que el timeout; timeout menor que TTL. Los cambios se leen al iniciar; cierre y vuelva a ejecutar.

## Pérdidas, IDs y casos incompletos

- Una desaparición nunca confirma una entrada. Un frame vacío sigue notificándose al motor.
- Una ausencia breve puede conservar el recorrido si el mismo ID reaparece en la misma zona, dentro del tiempo y desplazamiento admitidos. Se reinicia la evidencia temporal pendiente. El cruce de un borde no se infiere a través de una ausencia.
- Si vuelve directamente fuera de B después de perderse dentro, no se acredita una salida observada. Si se pierde durante la confirmación, se cancela esa confirmación.
- Un ID nuevo empieza con historia propia. No recibe el recorrido de otro ID, no se fusionan tracks por cercanía y no se exporta ReID.
- Los saltos de posición y los intervalos excesivos cancelan. Los estados antiguos se limpian por tiempo; cada estado conserva unos pocos valores, no una trayectoria ilimitada.
- Timestamps no finitos, repetidos o hacia atrás; IDs inválidos/duplicados; o posiciones no finitas/fuera del frame producen un error controlado antes de modificar el contador de ese frame. La aplicación libera la cámara.

**No se garantiza eliminar todos los errores de un intercambio de IDs geométricamente plausible.** Tampoco se puede distinguir automáticamente dos tracks duplicados de dos personas reales solo con estos datos. Esta versión evita heredar historia entre IDs y cuenta cada episodio una vez, pero prefiere omitir recorridos incompletos a inventar identidades. CNT-10 a CNT-12 deben medir estas limitaciones.

## Presentación, cámara y GPU

La ventana muestra título, entradas acumuladas, tracker, confianza efectiva, dispositivo, cámara, resolución, perfil, FPS, inferencia YOLO y tiempo conjunto YOLO + tracking. Este último conserva la métrica del motor existente; no es un tiempo aislado de asociación ni incluye toda la presentación. Se conservan cajas, confianza, IDs, trails, polígonos, bottom-center y etiquetas H4, agregando el estado de la FSM. Las transiciones `obs:` heredadas del Hito 4 son solo visuales; no controlan el contador.

OpenCV Hershey muestra texto ASCII: en pantalla se lee `ENTRADAS AL BANO`. No se añade otra biblioteca gráfica para la Ñ. No hay contador de salidas.

Se reutiliza la apertura/liberación de cámara existente. Índice o aspecto incompatibles con el perfil bloquean antes de cargar el tracker; el aspecto también se verifica en cada frame. El mismo índice no garantiza la misma cámara física. Si la mueve, cambia zoom o recorta el encuadre, revise/recalibre.

La resolución CPU/GPU continúa en el motor original. Se conserva la preferencia local y su fallback existente con advertencia cuando corresponde; no se fuerza CUDA ni se añade otro selector de dispositivo. Un error o backend de tracker inválido no provoca fallback a otro tracker. El modelo se instancia una vez y se ejecuta una sola inferencia por frame, antes de pintar las superposiciones.

## Validación automatizada reproducible

```powershell
& .\.venv\Scripts\python.exe -m compileall src tests
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_count*.py" -v
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_track_count.py" -v
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
& .\.venv\Scripts\python.exe -m src.diagnostics
& .\.venv\Scripts\python.exe -c "import src.count_geometry; import src.count_engine; import src.counting_config; import src.track_count"
```

Se añadieron 75 pruebas: 53 del motor/geometría, 9 de configuración/selección y 13 de integración del comando. La integración ejecuta el motor común y la FSM con dobles de inferencia/cámara/GUI. No demuestra precisión con personas reales ni funcionamiento CUDA.

El ZIP recibido no incluía `tests/video_test_support.py`, aunque tres archivos de tests H4 lo importaban. Se agregó únicamente el auxiliar de temporales requerido, sin editar las pruebas ni recuperar módulos MP4 ausentes. Los temporales quedan bajo `logs/test_temp/`, ignorado por las reglas originales y excluido de la entrega.

El arnés H4 existente se conserva y descubre también los nuevos tests:

```powershell
& .\.venv\Scripts\python.exe tests/hito4_simulated_regression.py
```

En esta versión ejecuta 389 tests únicos con OpenCV simulado: 314 existentes y 75 nuevos; excluye 28 tests que requieren componentes reales. Las tres ejecuciones finales pasaron. No reemplaza la suite normal. La suite normal de este entorno sigue bloqueada parcialmente por dependencias ausentes; el reporte detalla fallos y exclusiones. No instale ni cambie paquetes solo para repetir la batería simulada.

## Pruebas físicas pendientes

La cámara debe observar solo el acceso, nunca el interior del baño. Para cada prueba registre perfil, posición de cámara, resolución, tracker, dispositivo efectivo, umbrales y resultado. Mantenga las mismas condiciones al comparar trackers.

| Caso | Prueba y resultado esperado | Estado |
| --- | --- | --- |
| CNT-01 | A → B → salida frontal B: una entrada. | Pendiente |
| CNT-02 | B → A → exterior: cero entradas adicionales. | Pendiente |
| CNT-03 | Llega a A y retrocede: cero. | Pendiente |
| CNT-04 | Llega a B y retrocede: cero. | Pendiente |
| CNT-05 | Sale por un costado de B: cero sin salida frontal coherente. | Pendiente |
| CNT-06 | Permanece detenido en A/B: cero repeticiones; observar expiración. | Pendiente |
| CNT-07 | Entrada seguida de salida: el total conserva una. | Pendiente |
| CNT-08 | Entrada, retorno completo por A al exterior y nueva entrada: dos si ambos recorridos son válidos. | Pendiente |
| CNT-09 | Dos personas ingresan consecutivamente: dos entradas. | Pendiente |
| CNT-10 | Dos personas se cruzan: registrar aciertos, omisiones y duplicados. | Pendiente |
| CNT-11 | Oclusión: documentar qué recorrido se completa y cuál queda incompleto. | Pendiente |
| CNT-12 | Cambio/intercambio de ID: registrar el comportamiento real, sin inferir identidad. | Pendiente |
| CNT-13 | Habitación y pasillo: revisar geometría y orientación sin editar Python. | Pendiente |
| CNT-14 | Cambiar BoT-SORT por FastTracker y volver: comprobar backend y contador. | Pendiente |
| CNT-15 | Comparar FPS con track_zones en la misma escena, dispositivo y resolución. | Pendiente |

Para CNT-15 estabilice el inicio y observe al menos 60 segundos por modo, ejecutados secuencialmente. No interprete un FPS sintético como rendimiento de webcam/GPU.

Para evaluar precisión, anote cada ingreso real y empareje su confirmación: correcto, omitido, falso o duplicado. Registre las salidas y los movimientos laterales como controles negativos. Un total final correcto puede ocultar omisiones compensadas por falsos positivos. Si separa duplicados, inclúyalos una sola vez dentro de los falsos positivos totales al calcular precisión. Cobertura = ingresos correctos / ingresos reales; precisión = ingresos correctos / confirmaciones totales. Si un denominador es cero, indique no evaluable. El objetivo 85–90 % no está demostrado por esta entrega.

## Límite del hito

No hay persistencia de conteos, base de datos, Django, ocupación, identificación personal, imágenes guardadas ni exportación de embeddings. No se implementan `zone_calibrator_extended`, `track_count_extended`, cinco regiones ni selector básico/extendido. H5.2 podrá aportar geometría auxiliar explícita; esta implementación se limita a A/B/FUERA y a sus bordes existentes.
