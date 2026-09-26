# Hito 3 — Seguimiento temporal con ByteTrack

## Objetivo y arquitectura

El Hito 3 agrega seguimiento multiobjeto local sobre el proyecto de los Hitos 1 y 2. La webcam se gestiona exclusivamente mediante `camera_session`; YOLO26n localiza personas por frame y el ByteTrack integrado en Ultralytics asocia cajas entre frames. El visor muestra cajas, confianza, IDs temporales y una trayectoria corta. Se usa CPU.

| Comando | Función |
| --- | --- |
| `python -m src.main` | Preview H1 sin YOLO, ByteTrack ni pesos. |
| `python -m src.detect` | Detección H2 por frame, sin IDs persistentes. |
| `python -m src.track` | Detección y tracking H3, una sola llamada `model.track()` por frame. |

`PersonTracker` carga una vez el modelo usando `load_person_model`, compartido con `PersonDetector`; ambos reutilizan la validación del checkpoint y de la clase person. La geometría `Detection` se extiende con `Track.track_id`. No se llama a `PersonDetector.detect()` desde H3 ni se ejecuta `predict()` antes de `track()`. Ultralytics realiza internamente la inferencia y asociación en esa única llamada. Los imports de los tres puntos de entrada no cargan IA ni abren cámaras.

`src/track.py` administra el bucle, la sesión de cámara existente y el dibujo. `src/tracker.py` no abre webcam ni ventanas. `FrameTracks` devuelve tracks, cajas sin ID cuando la API las devuelve, tiempo YOLO y tiempo total de procesamiento; no guarda resultados gráficos.

## Configuraciones separadas

| Archivo | Responsabilidad |
| --- | --- |
| `config/camera.json` | Índice, resolución, FPS solicitados y backend. Conservado. |
| `config/detection.json` | Modelo, filtros de inferencia, tamaño y CPU. Conservado. |
| `config/tracking.json` | Persistencia y visualización de nuestro seguimiento. |
| `config/bytetrack_capstone.yaml` | Asociación interna del ByteTrack integrado. |

Las rutas de configuración se resuelven desde la raíz del proyecto, no desde el directorio actual. `tracker_config` se guarda relativo, con `/`, debe existir, estar dentro del proyecto y terminar en `.yaml` o `.yml`. No se aceptan rutas absolutas Windows/Linux ni rutas que escapen del proyecto. Los cambios se cargan al reiniciar, no en vivo.

```json
{
  "tracker_config": "config/bytetrack_capstone.yaml",
  "persist": true,
  "show_track_id": true,
  "show_trail": true,
  "trail_length": 30
}
```

Los cinco campos son obligatorios; campos extra se rechazan. Los tres indicadores requieren booleanos JSON reales. `persist` debe mantenerse en `true`: este punto de entrada procesa una secuencia continua y rechaza `false` con mensaje explicativo. Esto impide reinicios involuntarios del tracker por frame. `show_track_id` y `show_trail` pueden desactivarse. `trail_length` admite enteros 1–300; no acepta booleanos, cero ni valores enormes.

```yaml
tracker_type: bytetrack
track_high_thresh: 0.25
track_low_thresh: 0.10
new_track_thresh: 0.25
track_buffer: 30
match_thresh: 0.80
fuse_score: true
```

Se cotejaron estos ocho campos con el YAML y el código instalados de Ultralytics **8.4.163**. No requiere campos adicionales para ByteTrack. No se selecciona BoT-SORT por defecto ni se habilita ReID.

| Parámetro | Significado práctico |
| --- | --- |
| `tracker_type` | Selecciona explícitamente `bytetrack`. |
| `track_high_thresh` | Separa las detecciones usadas en la primera asociación. |
| `track_low_thresh` | Límite inferior de detecciones débiles utilizables en la segunda asociación. |
| `new_track_thresh` | Puntuación mínima adicional para iniciar un track con una detección no asociada; no garantiza confirmación inmediata. |
| `track_buffer` | Frames procesados que un track perdido puede conservarse. En 8.4.163 se usa directamente, sin escalar por FPS solicitado a la cámara. |
| `match_thresh` | Umbral de coste de la primera asociación; no es confianza del detector ni porcentaje de exactitud. |
| `fuse_score` | Combina confianza de detección con la similitud geométrica al construir el coste de asociación. |

Se validan tipos, valores finitos en [0, 1], `track_low_thresh < track_high_thresh`, buffer entero 1–3000 y `fuse_score` booleano. Los valores entregados permanecen en el baseline solicitado, sin optimización.

## Confianza YOLO y umbrales ByteTrack: limitación explícita del baseline

**El ZIP recibido contiene `confidence_threshold: 0.65`. Se conserva exactamente**, aunque el encargo menciona 0.50 como posibilidad y notas antiguas hablan de otros valores. H2 y H3 pasan el valor real de `detection.json` como `conf` a Ultralytics. No hay umbral alternativo oculto.

El filtro YOLO sucede **antes** de la asociación: con `conf=0.65`, las detecciones inferiores ya no llegan a ByteTrack. Por tanto, en este baseline no se aprovecha su segunda asociación con cajas de baja confianza, delimitada por 0.10–0.25. ByteTrack sigue asociando las detecciones restantes y conserva estado temporal. La aplicación y el diagnóstico advierten esta limitación. No se afirma que el baseline evalúe toda la capacidad de recuperación de ByteTrack.

Se decidió mantener comparabilidad con H2 y evitar cambiar silenciosamente el detector. No se igualaron los umbrales internos a 0.65. Un experimento posterior con menor `conf` debe registrarse como configuración diferente, evaluar falsos positivos y sensibilidad, y no confundirse con estos resultados. Los tests del motor con cajas sintéticas de confianza 0.20 comprueban esa segunda asociación por separado; no prueban que el pipeline actual entregue esas cajas.

## IDs, confirmación, oclusiones y falsos positivos

`ID 7` significa «trayectoria temporal 7 en esta ejecución». No identifica una persona real, usuario, empleado o estudiante. Al reiniciar pueden reutilizarse números; al desaparecer y volver puede aparecer un ID diferente. No hay identidad persistente entre ejecuciones.

`persist=True` informa que los frames pertenecen a una misma secuencia. Ultralytics conserva la instancia del tracker. Los frames sin detecciones también actualizan su estado y edad. En 8.4.163 los tracks nuevos pueden requerir confirmación después del primer frame. Si `Results` no tiene IDs, se dibujan sus cajas como `person | sin ID`; nunca se inventan IDs. Cuando la API retorna tracks confirmados, puede omitir detecciones no confirmadas: «cajas sin ID» no es un censo de todas las propuestas crudas de YOLO.

`Tracks activos` cuenta únicamente los tracks devueltos para el frame actual; excluye perdidos retenidos. No representa personas únicas, ocupación ni entradas/salidas. Un cruce o una oclusión pueden intercambiar IDs (ID switch), fragmentar una trayectoria o impedir recuperar un ID. No se exige cero cambios en todos los escenarios.

El buffer de 30 se mide en frames procesados, no segundos: a 20 FPS equivale orientativamente a 1.5 s de procesamiento, sin garantía de recuperar la trayectoria. La recuperación depende también de asociación, movimiento y calidad de detección. El programa no convierte el buffer usando los 30 FPS solicitados a la cámara.

Una esquina de cama o mochila mal clasificada como person puede recibir ID y mantenerlo. Eso no demuestra que ByteTrack esté clasificando mal: recibe las detecciones de YOLO. No se introducen reglas por posición, inmovilidad, proporción, objeto o perspectiva. Una persona quieta es una detección legítima. Se deben caracterizar los falsos positivos conocidos, no ocultarlos.

## Historial y recursos

Cada trail usa `deque(maxlen=trail_length)` con centros geométricos enteros; no guarda imágenes. Los historiales sobreviven ausencias breves y se eliminan cuando pasan más de `track_buffer + 1` frames desde la última observación. Ese frame de gracia acompaña el orden de asociación y retirada del motor. Solo se dibujan trails de tracks presentes. Desactivar `show_trail` evita crear el historial.

Esta memoria de dibujo no decide IDs ni reemplaza ByteTrack. Una prueba de 10 000 IDs sucesivos verifica que con buffer 30 no se acumulan más de 32 historiales y que luego se vacían. El motor instalado limita también su lista de removidos a 1000 entradas. Esto no sustituye observar la memoria del proceso durante varios minutos en el equipo del usuario.

La cámara se libera mediante `camera_session` y las ventanas se destruyen en `finally`, incluso ante error de carga, inferencia, UI, lectura, Ctrl+C o apertura fallida. Se admiten q, ESC y cierre de ventana. Ante desconexión se termina con explicación; no hay reconexión automática.

## Dependencias y ejecución

Se conservan OpenCV 4.14.0.94, Ultralytics 8.4.163, torch 2.14.0 y torchvision 0.29.0. Se agrega **lap==0.5.12** porque `ultralytics.trackers.utils.matching` lo importa y requiere `lap>=0.5.12`, pero no se instala con el requirements previo. Es el solver de asignación usado por Ultralytics, no un paquete ByteTrack externo. Se verificó su wheel Windows CPython 3.13 x64. PyYAML ya llega transitivamente con Ultralytics. No se clona ni copia ningún tracker de terceros.

No hacen falta instalaciones fuera de `requirements.txt`. La autoinstalación permanece desactivada. Activar el entorno existente desde PowerShell, en la carpeta que contiene `src`:

```powershell
.\.venv\Scripts\Activate.ps1
python --version
python -m pip install -r requirements.txt
python -m pip check
python -m compileall src tests
python -m unittest discover -s tests -v
python -m src.diagnostics
python -m src.main
python -m src.detect
python -m src.track
```

Cerrar cada visor antes del siguiente. Si no puedes activar, sustituye `python` por `.\.venv\Scripts\python.exe`. No recrees un entorno funcional. Si no existe, confirma primero Python 3.13.15 x64 y créalo con `py -3.13 -m venv .venv`.

El ZIP no contiene pesos. El primer inicio los descarga con la función existente de Ultralytics si faltan; si conservas tu `yolo26n.pt`, se reutiliza. Una vez instaladas dependencias y pesos, el procesamiento no requiere Internet.

## Métricas y privacidad

| Métrica | Alcance |
| --- | --- |
| FPS pipeline | Intervalos entre finalizaciones del bucle; incluye dibujo, GUI y siguiente lectura/procesamiento. Excluye inicialización; «midiendo» hasta el primer intervalo completo. |
| Inferencia YOLO | `Results.speed['inference']`, cuando existe y es válido. No incluye todo ByteTrack ni la captura. |
| YOLO + tracking | Tiempo de `PersonTracker.track`, incluyendo preprocesamiento, inferencia, asociación y extracción de datos. No es tiempo exclusivo de ByteTrack ni latencia cámara-pantalla. |
| Tracks activos / cajas sin ID | Resultados actuales expuestos por Ultralytics; no conteo operacional. |

Comparar H3 con los 20–24 FPS y 27–31 ms H2 informados por el usuario solo después de medir en el mismo PC, escena y configuración. No se exige 30 FPS ni se optimiza prematuramente. Los tiempos sintéticos del servidor no son FPS físicos de webcam.

Procesamiento local, frames en memoria, `save`, `save_txt`, `save_conf`, `save_crop`, `show` y `visualize` desactivados en Ultralytics. Solo OpenCV muestra la imagen. Sin grabación, capturas automáticas, audio, cloud, caras, identificación, ReID ni embeddings biométricos. Se conservan ajustes locales de privacidad de H2; los pesos y ajustes técnicos no son imágenes almacenadas.

## Validación y límites

La suite conserva íntegros los 48 tests anteriores, agrega pruebas de configuración, extracción de IDs, persistencia, una llamada por frame, historial, métricas, opciones visuales y liberación de recursos. También ejecuta el ByteTrack real con cajas sintéticas, sin pesos ni descargas. La prueba de YOLO real sobre una imagen de ejemplo se registra separadamente en `validacion_tecnica.md`; no se ejecuta ni descarga modelos en cada test unitario.

Las pruebas físicas A–AB están preparadas en `resultados_pruebas.md`, todas pendientes para H3: Windows, webcam, personas reales, cama/mochila, oclusiones, cruces, memoria, rendimiento y cierres. No se declara aceptación física del Hito 3 con tests automáticos.

Fuera de alcance: zonas A/B, línea, calibración operacional, estados, IN/OUT, conteo, ocupación, API/Django/base de datos/alertas, reconocimiento, entrenamiento, exportaciones y aceleradores. El siguiente hito será calibración espacial; no se implementa aquí.

## Referencias técnicas

La compatibilidad se verificó principalmente contra los archivos **instalados de la versión 8.4.163**: `cfg/trackers/bytetrack.yaml`, `trackers/track.py`, `trackers/byte_tracker.py`, `trackers/utils/matching.py` y `trackers/utils/stracks.py`.

- [Documentación oficial de tracking](https://docs.ultralytics.com/modes/track/).
- [Distribución exacta Ultralytics 8.4.163](https://pypi.org/project/ultralytics/8.4.163/).
- [Referencia oficial ByteTrack](https://docs.ultralytics.com/reference/trackers/byte_tracker/).

Las páginas generales pueden describir versiones posteriores; el código instalado fue la autoridad para esta entrega.
