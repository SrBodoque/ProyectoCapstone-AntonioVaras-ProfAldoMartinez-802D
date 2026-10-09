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

## 2. Crear entorno virtual

Desde la carpeta `capstone-vision`:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Verificar:

```powershell
python --version
```

---

## 3. Instalar dependencias

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
```

---

## 4. CPU y soporte opcional NVIDIA CUDA

La instalación normal con `python -m pip install -r requirements.txt` y `python -m pip check` es suficiente para ejecutar detección y tracking en CPU. **No es obligatorio instalar wheels CUDA ni ejecutar `python -m src.device_selector`.** Sin preferencia local se usa `device: cpu` de `config/detection.json`. Si tu entorno actual ya funciona, no lo recrees. Para asegurar explícitamente los wheels CPU-only en un entorno nuevo, puedes instalar primero:

```powershell
python -m pip install torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
python -m pip check
```

Para utilizar opcionalmente una GPU NVIDIA compatible, el procedimiento reportado como validado por el equipo con RTX 5060 y driver 610.88 utiliza los wheels oficiales `cu132` (la GTX 1650 sigue pendiente de prueba física):

```powershell
python -m pip uninstall torch torchvision -y
python -m pip install torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cu132
python -m pip check
python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.device_count())"
```

Ejecuta este bloque solo si necesitas cambiar la instalación de PyTorch: si ya tienes `2.14.0+cu132` / `0.29.0+cu132` funcionando, omítelo. Los sufijos `+cpu` y `+cu132` son variantes de las versiones base; diagnostics no los rechaza. Consulta las [instrucciones oficiales de PyTorch](https://pytorch.org/get-started/locally/) para compatibilidad del equipo. No hace falta instalar Toolkit/cuDNN manualmente para esta mejora.

Instalar soporte CUDA y elegir el dispositivo son pasos distintos. Solo después de comprobar que `import torch` funciona, CUDA está disponible y hay GPUs, ejecuta `python -m src.device_selector` y elige la GPU. El selector no instala paquetes ni modifica el entorno Python.

Si `import torch` falla con `WinError 4551` o Windows bloquea `torch.dll` mediante App Control / Smart App Control, ese build no es utilizable mientras esté bloqueado. Puedes continuar con el build CPU explícito si su import funciona; no es necesario desactivar la seguridad de Windows desde el proyecto.

---

# Ejecución

El proyecto mantiene distintos puntos de entrada para poder probar cada capa de forma independiente.

### Configurar o cambiar la cámara

```powershell
python -m src.camera_selector
```

Ejecuta este comando en la primera configuración del equipo o cuando quieras cambiar de cámara. Prueba los índices 0 a 4 y permite elegir solo entre los que entregan frames. Muestra el tamaño real del frame, el backend y los FPS informados por el controlador (no medidos).

La selección se guarda como `camera_index` en `config/camera.json`, conservando resolución, FPS y backend. Después, `src.main`, `src.detect` y `src.track` usan ese índice sin preguntar, incluso en nuevas ejecuciones. Para cambiarlo, vuelve a ejecutar el selector. `q` cancela; si no hay cámaras disponibles, finaliza con error sin modificar la configuración. Si la cámara elegida deja de estar disponible, los ejecutables mantienen su error seguro; no eligen otra cámara automáticamente.

El índice depende del equipo. Como `camera.json` está versionado, revisa el diff antes de subir cambios para no publicar accidentalmente tu selección local. Cierra los visores antes de ejecutar el selector; durante el escaneo pueden aparecer avisos de OpenCV por índices o backends no disponibles.

Detalles de implementación, pruebas y validación física: [Selección de cámara](docs/seleccion_camara.md).

### Configurar o cambiar CPU/CUDA (opcional)

```powershell
python -m src.device_selector
```

Con PyTorch funcional, CPU siempre aparece como opción. Se ofrecen GPUs únicamente si PyTorch informa CUDA disponible; cada opción muestra su índice y nombre. Una GPU elegida debe superar una operación mínima con tensor antes de guardarse. Una instalación PyTorch CPU-only ofrece solo CPU, aunque el computador tenga una GPU NVIDIA física.

El selector guarda `cpu` o `cuda:N` únicamente en `config/device.local.json`, sin modificar `config/detection.json` ni la cámara. Esta preferencia local persiste entre procesos: `src.detect` y `src.track` la utilizan sin preguntar. Si no existe, ambos usan CPU sin menú, warning ni crear el archivo. `src.main` continúa siendo preview de cámara independiente. Para cambiar de dispositivo, ejecuta nuevamente el selector; `q` cancela.

Si la GPU local deja de ser utilizable o el índice no existe, se muestra un warning y se usa **CPU solo para esa ejecución**, conservando la preferencia GPU. Un archivo local inválido se ignora con warning y se usa la configuración base; no se reescribe. `diagnostics` distingue base, preferencia local, dispositivo efectivo y fallback, sin guardar ni pedir entrada. Los índices CUDA son los visibles para PyTorch en ese entorno, incluyendo posibles restricciones de `CUDA_VISIBLE_DEVICES`.

`detection.json` está versionado con CPU como base portable. `device.local.json` está ignorado por Git y debe excluirse de los ZIP de entrega. Detalles, evidencia y pruebas físicas: [Selección CPU/CUDA](docs/seleccion_dispositivo.md). El baseline histórico Hito 2 fue CPU; CUDA es una mejora posterior opcional.

### Webcam

```powershell
python -m src.main
```

### Detección de personas

```powershell
python -m src.detect
```

### Tracking ByteTrack estable

```powershell
python -m src.track
```

### Tracking FastTracker experimental

```powershell
python -m src.track_fast
```

Alternativa para comparar estabilidad de IDs ante cruces y oclusiones, conservando YOLO26n, confianza 0.65, cámara y dispositivo. ByteTrack sigue siendo el baseline; todavía no se elige un ganador. Procedimiento y tabla pendiente: [Comparación de trackers](docs/04_comparacion_trackers.md).

### Diagnóstico

```powershell
python -m src.diagnostics
```

Para diagnosticar cámaras disponibles sin seleccionar ni guardar configuración:

```powershell
python -m src.diagnostics --scan
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

```powershell
python -m compileall src tests
python -m unittest discover -s tests -v
python -m pip check
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
