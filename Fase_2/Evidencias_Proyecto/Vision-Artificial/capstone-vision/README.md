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

# Ejecución

El proyecto mantiene distintos puntos de entrada para poder probar cada capa de forma independiente.

### Webcam

```powershell
python -m src.main
```

### Detección de personas

```powershell
python -m src.detect
```

### Tracking ByteTrack

```powershell
python -m src.track
```

### Diagnóstico

```powershell
python -m src.diagnostics
```

Para buscar cámaras disponibles:

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
