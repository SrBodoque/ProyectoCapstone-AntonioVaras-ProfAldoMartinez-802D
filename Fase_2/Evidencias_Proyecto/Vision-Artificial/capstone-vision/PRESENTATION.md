# LimpIA — visualizador de presentación

> Actualización vigente: [PRESENTATION_PERFORMANCE.md](PRESENTATION_PERFORMANCE.md). Sustituye el panel lateral, el renderizado PPM y la política de captura descritos en esta guía histórica; incluye las tres validaciones reales de fluidez de MP4 y cámara.

Implementación independiente en `feature/visualizador-presentacion`, worktree
`C:\Users\juanc\Downloads\LimpIA-visualizador-presentacion`, partiendo exactamente
de `abeb34484ba54e3538692b810eb6a21fd4ac4522`. Sin commits ni publicaciones.

## Ejecución local

PowerShell; utilizar el entorno existente, sin instalar ni copiar modelos:

```powershell
$original = 'C:\Users\juanc\Downloads\ProyectoCapstone-AntonioVaras-ProfAldoMartinez-802D\Fase_2\Evidencias_Proyecto\Vision-Artificial\capstone-vision'
$python = Join-Path $original '.venv\Scripts\python.exe'
Set-Location 'C:\Users\juanc\Downloads\LimpIA-visualizador-presentacion\Fase_2\Evidencias_Proyecto\Vision-Artificial\capstone-vision'

& $python -B -m src.view_presentation `
  --source video `
  --video "$original\videos_testing\nuevo_angulo\video_03_1p3x.mp4" `
  --zones config/baselines/sala_v4.json `
  --tracker bytetrack --device cuda:0 --weights-dir "$original"
```

Presionar **Iniciar**. Pausar/reanudar conserva IDs y tiempo del archivo;
Detener libera la fuente; volver a Iniciar crea tracker y contador nuevos en cero.
Cerrar espera la liberación del trabajador sin bloquear el bucle gráfico.
Omitir `--video` abre el selector de MP4 al iniciar.
La selección de fuente se hace al lanzar la CLI; ambos orígenes usan la misma ventana.
No hay búsqueda temporal ni saltos de frames durante el procesamiento.
Si inferencia resulta más lenta que el video, la reproducción se ralentiza para
procesar todos los frames; `--unpaced` permite procesamiento offline sin esperas.

Cámara integrada, USB o DroidCam expuesta como dispositivo OpenCV:

```powershell
# Primero calibrar en la posición definitiva, con A exterior y B puerta.
& $python -B -m src.zone_calibrator
# Guardar un perfil NUEVO (por ejemplo sala_camera_720); nunca sobrescribir sala_v4.

& $python -B -m src.view_presentation `
  --source camera --camera-index 0 --camera-backend msmf `
  --zones config/zones/sala_camera_720.json --confirm-camera-zones `
  --tracker bytetrack --device cuda:0 --weights-dir "$original"
```

`sala_camera_720.json` es el nombre propuesto para una calibración que debe realizar
la persona responsable; no se crea ni se afirma que ese perfil exista actualmente.
El calibrador existente utiliza `config/camera.json`; comprobar el índice/resolución
antes de calibrar. El visualizador no escribe preferencias personales.
Las dimensiones reales deben coincidir EXACTAMENTE con la referencia del perfil;
se comprueba cada frame. También se reutiliza `ZoneProfile.check_camera` para el índice.
`--confirm-camera-zones` es la declaración explícita del operador de que el
encuadre y la orientación son correctos; no demuestra automáticamente equivalencia
entre una webcam y la grabación de sala. No usarla sin inspeccionar la calibración.

Sin `--camera-index` se reutilizan `scan_cameras` y `choose_camera` (índices 0–4),
sin guardar el índice. `--camera-backend` permite `auto` u otro backend soportado;
en Windows el predeterminado es MSMF. Las fuentes de red/RTSP no forman parte del
contrato existente de captura por índice y no se incorporan aquí.

Dispositivo: `--device cpu` o `--device cuda:0`. Si se omite, se reutilizan el
inventario y selector existentes una vez, sin persistir preferencias. No se acepta
fallback a CPU si se solicitó GPU. Tracker: `--tracker bytetrack` (predeterminado)
o `--tracker botsort` (BoT-SORT sin ReID, configuración existente).
No se cambian confianza 0.65, IoU 0.7, tamaño de inferencia 640 ni umbrales A/B.

Reproducción opcional de tracking completo:

```powershell
& $python -B -m src.view_presentation `
  --source video --video "$original\videos_testing\nuevo_angulo\video_03.mp4" `
  --zones config/baselines/sala_v4.json `
  --predictions 'RUTA_A_CASO_O_LOTE_DE_TRACKING' --tracker bytetrack
```

No requiere pesos ni GPU. Reutiliza `select_case`, `validate_case` y `_timeline`;
valida hash del MP4, integridad del perfil, dimensiones, continuidad y completitud
de predicciones y tracker. Los eventos se confirman progresivamente por el mismo
contador sobre tracks guardados. El tracker indicado debe coincidir con los metadatos.
No acepta resultados parciales ni inventa predicciones ausentes.

Los detalles técnicos se registran en stderr; opcionalmente usar
`--log-file logs/mi-sesion-nueva.log`. El archivo debe ser nuevo: apertura exclusiva.
No se guardan imágenes, video, predicciones ni eventos automáticamente.
La captura de pantalla solicitada se considera un artefacto de revisión aparte.

## Arquitectura y auditoría

| Archivo nuevo | Responsabilidad |
| --- | --- |
| `src/presentation_sources.py` | Contrato iterable de `FramePacket`, adaptación de `VideoSource` y `camera_session`, perfil y validación espacial |
| `src/presentation_processing.py` | Adaptador único `CountAdapter`, `PersonTracker.track()` o predicciones guardadas, `TransitionCounter` |
| `src/presentation_session.py` | Estado estructurado, trabajador secuencial, pausa cooperativa, errores, buzón de capacidad uno |
| `src/view_presentation.py` | CLI, selección de fuentes/dispositivo, ventana Tk, renderizado compartido |
| `tests/test_presentation.py` | 23 pruebas nuevas, fuentes simuladas, MP4 sintético real y Tk real |
| `tests/validate_presentation_local.py` | Validación opt-in con inferencia real y reporte nuevo |
| `PRESENTATION.md` | Guía, decisiones, evidencia y limitaciones |

Único archivo existente editado: README, mediante enlace a esta guía.
Los módulos funcionales y configuraciones existentes no se editan.

Auditoría: `count_mp4` usa `video_runner` para guardar tracking y `count_replay`
para contar después; ese comando no admite cámaras directamente. `VideoSource`
proporciona índices, timestamps, FPS y EOF conservador. `camera_session` conserva
el primer frame y garantiza release, utilizando los backends de `camera.py`.
`main` es un preview de cámara. `PersonTracker.track()` incluye YOLO y asociación:
no se llama también a `PersonDetector.detect()`. Una instancia por sesión conserva
IDs mediante `persist=True`; una nueva sesión no reutiliza esa instancia.
`prepare_runtime` y `tracker_runtime` resuelven pesos locales, dispositivo y YAML;
BoT-SORT requiere el opt-in existente `experimental_botsort=True` para desactivar ReID.
El `config/counting.json` selecciona otro tracker para su CLI histórica; aquí se
reutilizan exclusivamente sus umbrales y se respeta el tracker de esta nueva CLI.

El punto de conteo es bottom-center normalizado, idéntico a `count_replay`.
`TransitionCounter` determina pertenencia A/B, estabilidad temporal y eventos;
solo esos eventos actualizan el último evento y los contadores. No hay ocupación
porque se desconoce el número inicial de personas. El visualizador técnico
`view_count_results` reproduce conteos guardados y se conserva íntegramente.
`calibrate_mp4_zones` exporta perfiles vinculados al hash del archivo; se reutiliza
su formato, sin reinterpretar polígonos ni recalcularlos.

Tkinter 8.6 ya está disponible con Python 3.13.15 en este equipo. No hay dependencia
nueva, Pillow ni framework web. `PhotoImage` recibe PPM RGB desde OpenCV. Canvas
con región estable y letterbox, panel fijo de 310 px a la derecha, ventana inicial
1280×780, maximizable. Colores moderados, cifras destacadas y metadatos secundarios.
La UI consulta el último estado cada 33 ms; nunca ejecuta YOLO. Se descartan
actualizaciones visuales intermedias, conservando los totales y último evento.
No se descartan deliberadamente frames leídos por el trabajador de procesamiento.
La cámara/controlador puede almacenar o perder frames antes de `read()`; no existe
garantía de adquisición completa del sensor cuando inferencia es más lenta.

Los FPS mostrados son la tasa de la última operación de procesamiento (incluye
tracking y conteo), no FPS del sensor ni media sostenida. `delivery_fps` en el estado
mide entrega secuencial; no se presenta como FPS de captura. No se afirma una tasa
de renderizado medida. El tiempo MP4 procede del archivo; cámara utiliza reloj
monotónico de entrega, sin reloj de hardware disponible por la API actual.

## Evidencia local, 13 de noviembre de 2026

Entorno existente: Python 3.13.15, OpenCV 4.14.0, RTX 5060, CUDA disponible.
No se reinstalaron paquetes ni se descargaron pesos.

Baseline previo: 585 pruebas, éxito, 3 omisiones. El primer intento con sandbox
falló por permisos de temporales fuera del workspace original y se repitió con
acceso al worktree; no se trató como fallo funcional del baseline.

Las pruebas nuevas cubren MP4 válido/inexistente/corrupto, cámaras simuladas y
no disponibles, selectores sin persistencia, hashes y dimensiones, contador A/B
sin duplicados, IDs/cifras reiniciados, estabilidad de layout 9/10/99/100,
pausa/reanudación, stop/cierre, errores con UI activa, ByteTrack/BoT-SORT sin ReID,
replay sin YOLO y procesamiento de todos los frames con buzón acotado.

Validación real independiente del MP4 acelerado, sin predicciones preexistentes:

- `video_03.mp4`, **5.732 frames**, perfil sala_v4, YOLO26n, conf. 0.65, imgsz 640.
- ByteTrack, solicitado y efectivo **cuda:0**, nueva inferencia local.
- **21 entradas y 20 salidas**, estado Finalizado, sin error.
- **117,35 s; 48,85 frames/s** en sesión offline sin espera, incluyendo apertura
  y carga. No corresponde a reproducción con ventana ni a FPS de cámara.
- Hash del video: `2c172090c5ca856079bf98d4772f0dce803ab038e27521e522cff876c4b44155`.
- Video y zonas sin cambios al terminar. Reporte: `logs/presentation-real-mp4-cuda.json`.
- Este resultado acredita esta grabación; no es una afirmación de precisión general.

Reproducir la aceptación (el reporte debe tener nombre nuevo):

```powershell
& $python -B tests/validate_presentation_local.py `
  --source video --video "$original\videos_testing\nuevo_angulo\video_03.mp4" `
  --zones config/baselines/sala_v4.json --tracker bytetrack `
  --device cuda:0 --weights-dir "$original" --unpaced `
  --report logs/aceptacion-nueva.json
```

Cámara física: índice 0, backend **MSMF**, 10 frames reales a **1280×720**,
liberación comprobada. El driver informa 60 FPS; no es medición sostenida.
Reporte: `logs/presentation-physical-camera-probe.json`.
**Conteo físico de cámara pendiente**: encuadre no confirmado y perfil de sala
1920×1080 incompatible con la captura observada. No se inventó una calibración.
Las pruebas de cámara con detección/tracking/conteo completos emplean dobles de
inferencia y fuente simulada; no acreditan precisión física.

## Regresión reproducible y límites

```powershell
& $python -B -m unittest discover -s tests -v
# Repetir en tres procesos independientes después de cualquier cambio funcional.
& $python -B -m unittest discover -s tests -p test_presentation.py -v
```

Los resultados de las tres ejecuciones finales se registran en
`logs/presentation-final-v3-suite-1.txt`, `-2.txt`, `-3.txt` y
`logs/presentation-final-v3-suites.json`. Incluyen detección, tracking, motor A/B,
MP4, selectores y nueva interfaz. Los resultados individuales se detallan al
final de esta guía.

Omisiones esperables de la suite heredada en este worktree sin pesos copiados:
inferencia real ReID (pesos detector/clasificador ausentes en su raíz), integración
histórica de inferencia MP4 (peso ausente en esa raíz) y creación de symlinks sin
privilegio Windows. La validación real nueva usa pesos externos configurables y
acredita ByteTrack sobre el MP4 indicado; no acredita ReID, ni sustituye la prueba
heredada de detección sola. No se copian pesos para ocultar esas omisiones.

Cierre cooperativo: cámara, modelo y contextos pertenecen al trabajador; se espera
su salida antes de destruir la ventana. Una llamada nativa al driver que no retorna
no puede cancelarse de forma segura desde Python; la UI permanece operativa pero
el cierre espera al driver. No se prometen timeouts que OpenCV/MSMF no garantiza.
Validaciones Windows 10/11 adicionales y proyector físico quedan pendientes.
No hay fallback silencioso ni ajuste automático de detector para ganar FPS.

No hacer commit/push hasta revisión y autorización. Baseline, main, worktrees H5.1,
H5.2 y pruebas automatizadas, videos/modelos y visualizador técnico protegidos.

### Resultados finales de regresión

Tres procesos independientes después del último cambio funcional:

| Ejecución | Resultado | Duración unittest | Omisiones |
| --- | --- | --- | --- |
| 1 | 608 pruebas, sin fallos ni errores | 13,175 s | 3 heredadas |
| 2 | 608 pruebas, sin fallos ni errores | 13,785 s | 3 heredadas |
| 3 | 608 pruebas, sin fallos ni errores | 13,295 s | 3 heredadas |

23 pruebas nuevas por ejecución; las 585 restantes pertenecen a la regresión
existente. Las omisiones se describen arriba y no se cuentan como validaciones
aprobadas. El mensaje `ERROR: No se pudo visualizar el conteo...` dentro de los
logs es salida esperada de un caso negativo heredado; los tres procesos terminaron
con exit code 0 y `OK (skipped=3)`.

La ventana real de la nueva CLI se abrió para revisión manual, sin iniciar una
segunda inferencia. Las pruebas Tk comprobaron renderizado PPM, layout y manejo
de errores. No se obtuvo captura de pantalla: Computer Use falló con
`FrameArrived timed out` y, al recuperar la ventana y reintentar,
`window capture timed out`. Por ello no se afirma una inspección visual humana ni
se adjunta una imagen ficticia. La ventana permanece lista para pulsar Iniciar.

Comprobación final del entorno: `python -B -m pip check` → `No broken requirements found.`. `git diff --check` sin errores; área preparada vacía. Solo README existente modificado (7 líneas añadidas) y siete archivos nuevos. La serie v3 es la última, después del ajuste de espera de reproducción y corrección de mensajes; las series anteriores se conservaron sin sobrescribirlas.
