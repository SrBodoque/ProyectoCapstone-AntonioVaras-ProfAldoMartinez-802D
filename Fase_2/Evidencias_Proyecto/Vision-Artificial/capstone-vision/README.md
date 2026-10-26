# capstone-vision

Módulo de visión artificial de **HigieneSmart**, proyecto CAPSTONE de Ingeniería en Informática — Duoc UC.

El objetivo es detectar el flujo real de personas en el acceso a servicios higiénicos para generar eventos de **entrada (IN)** y **salida (OUT)**. Estos eventos permitirán que el sistema de gestión de limpieza tome decisiones basadas en demanda real y no únicamente en horarios fijos.

El sistema está diseñado bajo principios de privacidad:

- no utiliza reconocimiento facial;
- no identifica personas;
- no guarda video ni fotografías automáticamente;
- los IDs utilizados por el tracker son temporales;
- el procesamiento se realiza localmente.

---

## Estado actual

| Hito | Funcionalidad                     | Estado       |
| ---- | --------------------------------- | ------------ |
| 1    | Webcam + OpenCV                   | ✅           |
| 2    | Detección de personas con YOLO26n | ✅           |
| 3    | Tracking temporal con ByteTrack   | ✅           |
| 4    | Zona B + Zona A + línea final     | ⏳ Siguiente |
| 5    | Máquina de estados IN/OUT         | ⏳           |
| 6    | Robustez del conteo               | ⏳           |
| 7    | Pruebas formales                  | ⏳           |
| 8    | Portabilidad entre ubicaciones    | ⏳           |
| 9    | Piloto en Duoc UC                 | ⏳           |
| 10   | Integración con Django            | ⏳           |

Pipeline actual:

```text
Webcam
   ↓
OpenCV
   ↓
YOLO26n
   ↓
Persona
   ↓
ByteTrack
   ↓
track_id temporal
```

Pipeline objetivo:

```text
Webcam
   ↓
YOLO + ByteTrack
   ↓
Zona B
   ↓
Zona A
   ↓
Línea final
   ↓
Máquina de estados
   ↓
IN / OUT
   ↓
Django
```

---

## Tecnologías

- Python 3.13.15
- OpenCV
- Ultralytics
- YOLO26n
- PyTorch
- ByteTrack integrado mediante Ultralytics

Las versiones exactas utilizadas se encuentran en:

```text
requirements.txt
```

---

# Instalación

## 1. Verificar Python

```powershell
py -3.13 --version
```

Esperado:

```text
Python 3.13.15
```

Si no está instalado, puedes consultar las versiones disponibles mediante:

```powershell
winget show --id Python.Python.3.13 --versions
```

Si aparece `3.13.15`:

```powershell
winget install --id Python.Python.3.13 --version 3.13.15 -e --scope user
```

También puede utilizarse el instalador oficial de Python para Windows x64.

---

cd .\Fase_2\Evidencias_Proyecto\Vision-Artificial\capstone-vision

## 2. Entorno Python local

Utilizar Python **3.13.15 x64** y un `.venv` independiente dentro de `capstone-vision`.
No reutilizar ni modificar el entorno de OneDrive. Si `.venv` ya existe y funciona,
no recrearlo. Solo para preparar un entorno nuevo, con autorización:

```powershell
if (Test-Path -LiteralPath .venv) { throw '.venv ya existe; no sobrescribir.' }
py -3.13 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Falló la creación de .venv.' }
& .\.venv\Scripts\python.exe --version
```

Los comandos de esta guía usan directamente ese intérprete; **no requieren activar
`Activate.ps1`**. `.venv/` está excluido de Git. Instalar paquetes únicamente mediante
`.venv\Scripts\python.exe -m pip`, nunca sobre el Python global.

## 3. Dependencias y CUDA en RTX 5060

Configuración validada: PyTorch **2.14.0+cu132**, torchvision **0.29.0+cu132**,
Ultralytics **8.4.163**, OpenCV **4.14.0.94**, lap **0.5.12**, NumPy **2.5.2** y
PyYAML **6.0.3**. Las dos últimas son dependencias transitivas; `requirements.txt`
fija las cinco dependencias directas, pero no es un lock completo de transitivas.

Solo al instalar en un `.venv` nuevo y con autorización, ejecutar una línea a la vez:

```powershell
& .\.venv\Scripts\python.exe -m pip install --only-binary=:all: --index-url https://download.pytorch.org/whl/cu132 "torch==2.14.0+cu132" "torchvision==0.29.0+cu132"
& .\.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple -r requirements.txt "torch==2.14.0+cu132" "torchvision==0.29.0+cu132"
& .\.venv\Scripts\python.exe -m pip check
```

Detenerse si cualquier comando falla; no sustituir versiones ni intentar otra
combinación automáticamente. Los sufijos explícitos `+cu132` preservan la variante
CUDA al instalar el resto de requisitos. No instalar Toolkit/cuDNN aparte para
este procedimiento con wheels oficiales. Consultar la [instalación oficial de
PyTorch](https://pytorch.org/get-started/locally/) para otro hardware.

RTX 5060 y driver **610.88** validados con runtime CUDA **13.2**, arquitectura
`sm_120`, multiplicación matricial CUDA y NMS CUDA de torchvision. Comprobación
rápida, sin modelos ni cambios de preferencias:

```powershell
& .\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.version.cuda); assert torch.cuda.is_available(); print(torch.cuda.get_device_name(0)); x=torch.ones((32,32),device='cuda:0'); assert (x@x).sum().item()==32768; torch.cuda.synchronize()"
```

La disponibilidad de GPU se comprueba con PyTorch, no solo con `nvidia-smi`.
Un error de importación/DLL o CUDA no disponible debe diagnosticarse; no cambiar
paquetes, políticas de Windows ni dispositivo silenciosamente. La GTX 1650 no
queda validada por estas pruebas.

## 4. Dispositivo y pesos locales

La instalación anterior permite solicitar `cpu` o `cuda:0`. Para videos se exige
`--device` explícito; no se utiliza el selector persistente. Para los ejecutables
de cámara sigue disponible `src.device_selector`, descrito a continuación.

Detección y tracking MP4 requieren **`yolo26n.pt`** en la raíz. El checkpoint oficial
se prepara por separado y únicamente con autorización desde:
[Ultralytics/YOLO26 en Hugging Face](https://huggingface.co/Ultralytics/YOLO26/resolve/main/yolo26n.pt).
No sobrescribir un archivo existente. El ejecutable MP4 no descarga pesos ni instala
paquetes. No ejecutar el selector de dispositivo para preparar el entorno.

---

# Ejecución

El proyecto mantiene distintos puntos de entrada para poder probar cada capa de forma independiente.

### Configurar o cambiar la cámara

```powershell
& .\.venv\Scripts\python.exe -m src.camera_selector
```

Ejecuta este comando en la primera configuración del equipo o cuando quieras cambiar de cámara. Prueba los índices 0 a 4 y permite elegir solo entre los que entregan frames. Muestra el tamaño real del frame, el backend y los FPS informados por el controlador (no medidos).

La selección se guarda como `camera_index` en `config/camera.json`, conservando resolución, FPS y backend. Después, `src.main`, `src.detect` y `src.track` usan ese índice sin preguntar, incluso en nuevas ejecuciones. Para cambiarlo, vuelve a ejecutar el selector. `q` cancela; si no hay cámaras disponibles, finaliza con error sin modificar la configuración. Si la cámara elegida deja de estar disponible, los ejecutables mantienen su error seguro; no eligen otra cámara automáticamente.

El índice depende del equipo. Como `camera.json` está versionado, revisa el diff antes de subir cambios para no publicar accidentalmente tu selección local. Cierra los visores antes de ejecutar el selector; durante el escaneo pueden aparecer avisos de OpenCV por índices o backends no disponibles.

Detalles de implementación, pruebas y validación física: [Selección de cámara](docs/seleccion_camara.md).

### Configurar o cambiar CPU/CUDA (opcional)

```powershell
& .\.venv\Scripts\python.exe -m src.device_selector
```

Con PyTorch funcional, CPU siempre aparece como opción. Se ofrecen GPUs únicamente si PyTorch informa CUDA disponible; cada opción muestra su índice y nombre. Una GPU elegida debe superar una operación mínima con tensor antes de guardarse. Una instalación PyTorch CPU-only ofrece solo CPU, aunque el computador tenga una GPU NVIDIA física.

El selector guarda `cpu` o `cuda:N` únicamente en `config/device.local.json`, sin modificar `config/detection.json` ni la cámara. Esta preferencia local persiste entre procesos: `src.detect` y `src.track` la utilizan sin preguntar. Si no existe, ambos usan CPU sin menú, warning ni crear el archivo. `src.main` continúa siendo preview de cámara independiente. Para cambiar de dispositivo, ejecuta nuevamente el selector; `q` cancela.

Si la GPU local deja de ser utilizable o el índice no existe, se muestra un warning y se usa **CPU solo para esa ejecución**, conservando la preferencia GPU. Un archivo local inválido se ignora con warning y se usa la configuración base; no se reescribe. `diagnostics` distingue base, preferencia local, dispositivo efectivo y fallback, sin guardar ni pedir entrada. Los índices CUDA son los visibles para PyTorch en ese entorno, incluyendo posibles restricciones de `CUDA_VISIBLE_DEVICES`.

`detection.json` está versionado con CPU como base portable. `device.local.json` está ignorado por Git y debe excluirse de los ZIP de entrega. Detalles, evidencia y pruebas físicas: [Selección CPU/CUDA](docs/seleccion_dispositivo.md). El baseline histórico Hito 2 fue CPU; CUDA es una mejora posterior opcional.

### Webcam

```powershell
& .\.venv\Scripts\python.exe -m src.main
```

### Detección de personas

```powershell
& .\.venv\Scripts\python.exe -m src.detect
```

### Tracking ByteTrack estable

```powershell
& .\.venv\Scripts\python.exe -m src.track
```

### Tracking FastTracker experimental

```powershell
& .\.venv\Scripts\python.exe -m src.track_fast
```

Alternativa para comparar estabilidad de IDs ante cruces y oclusiones, conservando YOLO26n, confianza 0.65, cámara y dispositivo. ByteTrack sigue siendo el baseline; todavía no se elige un ganador. Procedimiento y tabla pendiente: [Comparación de trackers](docs/04_comparacion_trackers.md).

### Tracking ByteTrack Recovery experimental

```powershell
& .\.venv\Scripts\python.exe -m src.track_recovery
```

Recovery utiliza umbrales separados: candidatos YOLO desde 0.10 para intentar mantener tracks existentes, con confianza alta 0.65 para iniciar nuevos tracks. La detección general, ByteTrack original y FastTracker conservan confianza 0.65. Procedimiento y pruebas pendientes: [ByteTrack Recovery](docs/05_bytetrack_recovery.md).

### Tracking BoT-SORT + ReID experimental

```powershell
& .\.venv\Scripts\python.exe -m src.track_botsort_reid
```

Experimento con ReID temporal por apariencia, confianza **0.65** y la cámara y dispositivo ya seleccionados. Puede requerir el modelo oficial adicional `yolo26n-cls.pt`; comprueba el encoder, las características y su paso a la asociación durante la ejecución. Eficacia y rendimiento pendientes de pruebas físicas: [BoT-SORT + ReID](docs/06_botsort_reid.md).

### Diagnóstico

```powershell
& .\.venv\Scripts\python.exe -m src.diagnostics
```

Para diagnosticar cámaras disponibles sin seleccionar ni guardar configuración:

```powershell
& .\.venv\Scripts\python.exe -m src.diagnostics --scan
```

Cerrar las ventanas con:

```text
q
```

o:

```text
ESC
```

---

# Pruebas automáticas

## Procesamiento MP4 local — Etapa 1

El ejecutable independiente `src.process_videos` procesa MP4 sin cámara ni ventanas.
`src.main`, `src.detect`, `src.track` y los selectores conservan su funcionamiento.
Requiere el entorno local con las dependencias ya instaladas y `yolo26n.pt` no vacío
en la raíz de `capstone-vision`. No instala paquetes ni descarga pesos. Si faltan,
finaliza con error y deja la validación pendiente.

Desde `capstone-vision`, con el intérprete del entorno existente:

```powershell
& .\.venv\Scripts\python.exe -m src.process_videos --video videos_testing/dev/prueba_01.mp4 --mode tracking --device cuda:0
& .\.venv\Scripts\python.exe -m src.process_videos --directory videos_testing/dev --mode tracking --device cuda:0
& .\.venv\Scripts\python.exe -m src.process_videos --video videos_testing/dev/prueba_01.mp4 --mode detection --device cpu
```

Se debe seleccionar exactamente `--video` o `--directory`, un modo y un dispositivo.
La selección CPU/CUDA es explícita, prevalece sobre la preferencia personal y no la
modifica. CUDA no disponible causa error, sin fallback. Los comandos anteriores
utilizan exclusivamente el `.venv` local; no es necesario activarlo ni recurrir
a otro entorno. Las rutas de entrada son ejemplos: seleccionar un MP4 local existente.

Organización local sugerida, excluida de Git:

```text
videos_testing/
  dev/          # videos para desarrollo
  validation/   # grabaciones independientes reservadas
results_testing/
  <run_id>/
    run.json
    summary.json
    <case_id>/
      metadata.json
      predictions.jsonl
      timings.csv
```

La carpeta se enumera sin recursión, con orden estable y extensión MP4 sin
distinguir mayúsculas. No se admiten URLs ni rutas UNC. Cada video tiene una sesión
nueva, se procesa frame a frame sin saltos ni pausas de reproducción y se libera
antes del siguiente. Los IDs solo tienen significado dentro de esa sesión.
En esta etapa no hay selector de perfiles: tracking utiliza ByteTrack baseline,
con los parámetros actuales, sin tuning ni cambio de algoritmos.

Cada ejecución crea un directorio exclusivo (fecha UTC y UUID); nunca reutiliza
resultados anteriores. `--output RUTA` cambia el directorio raíz de resultados.
Los resultados fuera de `results_testing/` deben mantenerse fuera de Git.

| Archivo | Contenido |
| --- | --- |
| `run.json` | ID y estado del lote, opciones, casos, hashes, configuración y versiones. |
| `summary.json` | Estado global, resultado por caso, errores y casos no procesados. |
| `metadata.json` | Por video: dispositivo solicitado/efectivo, modelo y hash, perfil y parámetros, backend, dimensiones, FPS informado, frames, tiempos iniciales y motivo de terminación. |
| `predictions.jsonl` | Una fila por frame, también vacío: índice desde cero, tiempo y origen del tiempo, cajas en píxeles originales, confianza, clase e ID cuando existe. |
| `timings.csv` | Una fila por frame: `frame_index`, `timestamp_ms`, `timestamp_source`, `read_ms`, `processing_ms`, `inference_ms` y `model_processing_ms`; valores ausentes quedan vacíos. |

En predicciones, `tracks` contiene cajas con ID, `detections` las del modo detección
y `untracked_detections` las del modo tracking sin ID. Todos los formatos incluyen o
se vinculan al esquema v1. Los IDs de caso tienen ordinal de selección y prefijo de
hash; no son identidades globales entre selecciones distintas. No se guardan imágenes,
videos anotados ni vectores de apariencia. Los archivos de ejecuciones fallidas o
interrumpidas son parciales y deben interpretarse junto con sus estados.

Los tiempos externos incluyen sincronización CUDA cuando corresponde. Se registran
por separado lectura, procesamiento, inferencia interna, carga y primera inferencia;
no se elimina el primer frame ni se calienta el tracker con frames adicionales.
El tiempo de video proviene de OpenCV o de índice/FPS informado, indicando el origen;
puede ser desconocido. Para video de FPS variable, índice/FPS es solo una estimación.

Estados: `completed` (fin consistente con el número informado de frames), `failed`
(error o fin anticipado), `incomplete` (metadatos insuficientes/inconsistentes) e
`interrupted` (Ctrl+C). OpenCV no distingue universalmente EOF de error de decodificación:
`completed` no certifica integridad absoluta del MP4. Un video fallido no impide
intentar los restantes; Ctrl+C detiene el lote conservando parciales. Fallos globales
de pesos/configuración/dispositivo impiden comenzar inferencias. Código de salida:
0 completo, 1 error/incompleto, 130 interrupción.

### Verificación de Etapa 1

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_video*.py" -v
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

La primera batería incluye casos unitarios, decodificación real de MP4 sintéticos,
inferencia simulada y una selección explícita de regresiones existentes. No equivale
a inferencia YOLO ni a la suite completa. La selección reutiliza ResourceTests de
Hito 1, escaneo/selección de cámara, DetectionResourceTests de Hito 2, DeviceTests del
selector CPU/CUDA y DetectorTests de Hito 2 excepto `test_model_path_independent_of_cwd`.
La exclusión de ese caso en la batería corta proviene del problema histórico de
ACL de temporales del sandbox; la suite completa sí lo incluye y permite verificarlo
fuera del sandbox. La batería corta no sustituye la regresión completa. No se
modificaron pruebas existentes para ocultar resultados.

Los nuevos fixtures crean y eliminan temporales exclusivos bajo `logs/video_test_temp/`,
sin cambiar ACL, para evitar el problema de `TemporaryDirectory(mode=0o700)` con tokens
Windows restringidos. No modifican el comportamiento de las pruebas existentes.

Integración YOLO real, separada y sin descargas, con recursos locales:

```powershell
$env:LIMPIA_TEST_MP4 = (Resolve-Path videos_testing/dev/prueba_01.mp4).Path
$env:LIMPIA_TEST_DEVICE = "cuda:0"  # usar cpu para validar explícitamente en CPU
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_mp4_inference_integration.py -v
```

Si faltan dependencias, pesos o la variable del MP4, la integración se registra como
omitida y pendiente, nunca aprobada. Antes de declarar validada la tarea, ejecutar
tres veces en procesos independientes la batería relevante después del último
cambio, además de cubrir escenarios distintos y las regresiones disponibles.

Esta etapa no implementa comparación, baseline promovido/inmutable, optimización,
métricas MOT, conteo IN/OUT ni integración Django. Las predicciones guardadas permiten
evaluación posterior sin repetir inferencias para métricas derivables de esas salidas.

### Estado verificado de Etapa 1

- Tres validaciones independientes conservadas de **89/89** pruebas específicas,
  sin fallos, errores ni omisiones; no se han modificado módulos funcionales después.
- `prueba_01.mp4`: **734/734** frames, estado `completed`, dispositivo efectivo
  `cuda:0` en RTX 5060. Se comprobaron índices, filas CSV/JSONL y hashes. Hay **588**
  frames con tracks y **5** con detecciones sin ID; no equivalen a personas contadas.
- Integración real de detección y tracking MP4 en CUDA: **1 prueba aprobada**, con
  ambos modos ejecutados sobre el archivo local, sin descargas ni omisiones.
- Regresión general: **373** casos descubiertos; `unittest` registra **370** pruebas,
  cero fallos, cero errores y **una omisión de clase**: las tres pruebas de inferencia
  BoT-SORT + ReID requieren `yolo26n-cls.pt`. No se descargó ese modelo ni se declara
  aprobada esa integración. La regresión general no se presenta como íntegramente aprobada.
- Cámara y selectores conservan contratos verificados con pruebas disponibles;
  esta comprobación no sustituye una nueva aceptación física de cámara.
- Sin anotaciones de referencia, no se certifican precisión, continuidad correcta de
  IDs ni conteo de personas. La terminación del MP4 conserva la limitación de EOF
  descrita arriba. BoT-SORT + ReID y evaluación cuantitativa siguen pendientes.

## Suite existente

```powershell
& .\.venv\Scripts\python.exe -m compileall src tests
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
& .\.venv\Scripts\python.exe -m pip check
```

Las pruebas físicas y sus resultados se registran en:

```text
docs/resultados_pruebas.md
```

---

# Configuración

La configuración está separada del código:

```text
config/
├── camera.json
├── detection.json
├── tracking.json
└── bytetrack_capstone.yaml
```

### `camera.json`

Configuración de webcam:

- índice;
- resolución;
- FPS;
- backend OpenCV.

### `detection.json`

Configuración de YOLO:

- modelo;
- confidence threshold;
- IoU;
- dispositivo;
- clase `person`.

### `tracking.json`

Configuración de tracking:

- ByteTrack;
- persistencia;
- visualización de IDs;
- trails.

### `bytetrack_capstone.yaml`

Parámetros internos de ByteTrack.

---

# Tracking

Los IDs mostrados por ByteTrack son **temporales**.

Por ejemplo:

```text
ID 7
```

no significa que el sistema haya identificado a una persona específica ni que hayan pasado siete personas.

Representa solamente una trayectoria temporal durante la ejecución.

Si una persona sale del campo de visión y vuelve posteriormente, puede recibir un ID diferente.

Esto es comportamiento esperado.

---

# Falsos positivos

Durante las pruebas se observaron algunos falsos positivos dependientes del entorno y del ángulo de cámara.

Por ejemplo, determinadas perspectivas de objetos pueden ser clasificadas temporalmente como `person`.

El sistema final no contará una persona solamente porque YOLO genere una detección.

Para producir un evento válido será necesario cumplir una trayectoria:

```text
Zona B
   ↓
Zona A
   ↓
Cruce de línea
   ↓
IN
```

o la secuencia inversa para `OUT`.

Esto permite añadir validación espacial y temporal sobre las detecciones de YOLO.

---

# Privacidad

El módulo no utiliza:

- reconocimiento facial;
- identificación personal;
- análisis de edad;
- análisis de género;
- audio;
- grabación automática;
- almacenamiento automático de imágenes;
- ReID biométrico;
- procesamiento cloud.

La visión artificial se utiliza exclusivamente para determinar trayectorias temporales necesarias para generar eventos IN/OUT.

---

# Estructura general

```text
capstone-vision/
├── config/
├── docs/
├── src/
├── tests/
├── .gitignore
├── README.md
└── requirements.txt
```

Documentación detallada:

```text
docs/
├── 00_contexto_vision.md
├── 01_entorno_y_webcam.md
├── 02_deteccion_personas.md
├── 03_tracking_bytetrack.md
├── resultados_pruebas.md
└── validacion_tecnica.md
```

Los siguientes hitos continuarán esta estructura.

---

# Próximo paso

## Hito 4 — Calibración espacial

El siguiente objetivo será definir gráficamente:

```text
              INTERIOR

══════════ LÍNEA FINAL ══════════

               ZONA A

               ZONA B

              EXTERIOR
```

Cada `track_id` podrá determinar:

```text
ID 4 → Zona B
ID 4 → Zona A
ID 4 → Cruce de línea
```

Todavía no se generarán eventos `IN/OUT`.

La máquina de estados será implementada en el siguiente hito.

---

## Proyecto CAPSTONE

**HigieneSmart** busca utilizar datos de uso real para apoyar la gestión de limpieza de servicios higiénicos, reduciendo la dependencia de frecuencias fijas y permitiendo una gestión basada en demanda.
