# Hito 2 — Detección de personas

## Objetivo y alcance

Extender el proyecto real del Hito 1 con detección de la clase `person` en los frames de su misma webcam. YOLO detecta cajas por frame; no cuenta entradas/salidas ni mantiene identidades. El número visible es la cantidad de detecciones actuales, no ocupación ni personas únicas.

La cámara observa el acceso, según `00_contexto_vision.md`. La detección no verifica por sí misma que una persona cruce una puerta. No se incluyen tracking, ByteTrack, IDs, trayectorias, zonas, línea final, estados, IN/OUT, contador, API, Django, base de datos, alertas, calibración, entrenamiento ni atributos personales. El siguiente hito será seguimiento con IDs temporales.

## Arquitectura incremental

| Componente | Responsabilidad |
| --- | --- |
| `src/config.py` | Un lector JSON común y validadores separados de cámara/detección. |
| `src/camera.py` | Apertura, fallback, primer frame, sesión y liberación; conservado byte a byte. |
| `src/detector.py` | Importación diferida de IA, un modelo por instancia, validación de clase, inferencia y extracción de datos. |
| `src/detect.py` | Sesión de cámara existente, anotación de frame actual, métricas y cierre. |
| `src/main.py` | Preview sin IA, conservado byte a byte. |
| `src/diagnostics.py` | Información previa más configuración, versiones cargadas y disponibilidad CUDA. No descarga pesos ni ejecuta inferencia. |

`PersonDetector` devuelve `FrameDetections`: una tupla de `Detection(x1, y1, x2, y2, confidence, class_id)`, el tiempo de inferencia informado por Ultralytics y el tiempo total de la llamada de detección medido con `perf_counter`. No guarda historial de frames ni mantiene estado entre personas.

La instancia de YOLO se crea una vez al entrar a detección, dentro de `camera_session`. La misma instancia recibe cada frame OpenCV BGR mediante `predict(source=frame)`. No se usa `source=0` ni otra captura de Ultralytics. Si descarga/carga/inferencia fallan o se pulsa Ctrl+C, el contexto libera la cámara y el bloque final destruye ventanas.

## Modelo y dependencias

Checkpoint: **yolo26n.pt**, modelo oficial preentrenado en COCO. `n` significa Nano, la variante más pequeña de la familia; se utiliza como baseline ligero, no como promesa de 30 FPS. El preentrenamiento ya incluye personas: primero se evalúa en el escenario real antes de considerar entrenamiento propio en un hito futuro.

Dependencias directas fijadas: OpenCV 4.14.0.94; Ultralytics 8.4.163; torch 2.14.0; torchvision 0.29.0. Pip resuelve dependencias transitivas, que no se fijan manualmente. Esto fija las versiones directas, no es un lockfile completo de todas las transitivas. El objetivo sigue siendo Windows 10/11 x64 con Python 3.13.15 convencional.

Se comprueba al cargar que `model.names[0]` y el ID configurado sean `person`. El filtro `classes=[person_class_id]` restringe resultados; una segunda comprobación de clase/confianza protege la salida antes de dibujar. Filtrar clases no significa que la red solo calcule esa categoría ni garantiza ausencia de falsos positivos.

## Parámetros

El JSON completo y los comandos están en README. Todos los campos de `detection.json` son obligatorios; se rechazan extras y se admite BOM UTF-8. `camera.json` conserva sus cinco campos y comportamiento.

- **model:** solamente `yolo26n.pt` en este hito, almacenado en la raíz del módulo. No se admiten URLs, YAML, modelos personalizados ni otras tareas.
- **confidence_threshold:** 0.25 inicialmente, número finito entre 0 y 1. Filtra detecciones con puntuación menor. La confianza no equivale a la probabilidad calibrada de acertar ni al porcentaje global de exactitud. Se ajusta tras observar falsos positivos y omisiones.
- **iou_threshold:** 0.70 inicialmente, entre 0 y 1. IoU mide intersección/unión de cajas; la ruta estándar de esta versión utiliza NMS para suprimir cajas solapadas. No mide distancia entre personas ni activa seguimiento. YOLO26 también ofrece una ruta sin NMS, pero aquí no se solicita `nms=False`.
- **image_size:** 640 inicialmente, entero positivo. Es tamaño de entrada solicitado a la red; se conserva relación de aspecto mediante el preprocesamiento de Ultralytics y puede ajustarse al stride. Las coordenadas devueltas corresponden al frame original. No cambia los 1280×720 solicitados a la cámara.
- **device:** solo `cpu`, aunque el diagnóstico indique CUDA disponible. No se configura CUDA ni se exporta a ONNX/OpenVINO/TensorRT.
- **person_class_id:** entero no negativo, 0 para este checkpoint; cambiarlo por otra categoría detiene la carga con un mensaje claro.
- **show_confidence:** booleano; muestra `person 0.87` o solamente `person`.

## Descarga, inicio y funcionamiento local

Ultralytics descarga automáticamente el checkpoint oficial si falta; no se implementó otro descargador. Instalación y primera descarga requieren conexión. Una vez presentes las dependencias y pesos, la inferencia es local. Los pesos `*.pt` no se versionan ni se incluyen en la entrega.

La importación de PyTorch, carga de pesos y primera inferencia pueden tardar más. La consola informa carga e inicialización. Los FPS empiezan a medirse después de completar la primera inferencia; la lectura inicial de cámara sucede antes de esa carga y no representa rendimiento sostenido.

Se desactivan `YOLO_AUTOINSTALL`, sondeos de conectividad con `YOLO_OFFLINE` y sincronización/telemetría (`sync=False`). En la versión fijada, la descarga explícita de un checkpoint oficial ausente sigue funcionando con estos ajustes. `.ultralytics/` guarda solo ajustes técnicos aislados de este proyecto y está ignorado por Git. La dependencia transitiva `ultralytics-platform` puede estar instalada; no se usa la plataforma, cuenta ni API key.

## Métricas

| Dato | Qué mide |
| --- | --- |
| Resolución | `frame.shape`, tamaño real recibido. |
| FPS del controlador | Valor reportado por OpenCV en consola, no medición del sensor. |
| FPS pipeline | Intervalos entre finalizaciones de inferencia; incluye dibujo, espera de GUI y siguiente lectura/inferencia. Promedio de ventanas de al menos un segundo, excluyendo inicialización. |
| Inferencia ms | `Results.speed['inference']` del frame actual; N/D si no está disponible. Excluye captura/GUI y no es toda la llamada. |
| `processing_ms` | Tiempo de la llamada completa al detector, incluyendo pre/postprocesamiento. Se expone en el resultado; el primero se registra en consola. |

No se mide por separado FPS físico de captura ni latencia de extremo a extremo de DroidCam/Wi-Fi. La resolución de salida no acredita calidad de detección. No se exige una tasa arbitraria de FPS: medir en cada CPU durante al menos 60 segundos.

## Cierre y errores

`q`, ESC, X de ventana y Ctrl+C cierran y liberan recursos. Un fallo de lectura termina con mensaje, sin reconexión automática, igual que Hito 1. Los errores de modelo/dependencias se explican en español con el detalle original. `src.detect` devuelve 0 ante cierre normal y 1 ante error.

`diagnostics` mantiene información/escaneo de cámara aunque la IA falte o falle, informa cada dependencia y devuelve 1 si la comprobación IA queda incompleta. La falta de webcam durante un escaneo no acredita fallo de dependencias. `src.main` sigue siendo ejecutable sin importar las bibliotecas de IA.

## Privacidad y límites

Frames y anotaciones permanecen en memoria. La inferencia configura explícitamente `save=False`, `save_txt=False`, `save_conf=False`, `save_crop=False`, `show=False` y `visualize=False`; nuestra GUI OpenCV presenta la imagen. No se invocan funciones de exportación de resultados, grabación, audio ni reconocimiento/atributos personales. No se retransmite el stream desde este módulo. DroidCam continúa siendo el origen de cámara por Wi-Fi ya existente.

Los tests usan dobles y JSON temporales. La prueba real automatizada usa frames sintéticos y, cuando está disponible, la imagen de ejemplo incluida con Ultralytics; no demuestra funcionamiento con personas frente a la webcam. Personas lejanas, ocultas, oscuridad, desenfoque, perspectiva y oclusiones pueden causar errores. Un falso `person` sigue siendo posible incluso al filtrar por clase. Sin tracker las cajas no tienen identidad persistente.

## Criterios de aceptación

Conservar las 16 pruebas del Hito 1; aprobar configuración/detección/recursos de Hito 2; instalar versiones fijadas sin conflictos; cargar el checkpoint una sola vez; mostrar solo `person`; medir rendimiento; no guardar imágenes/videos/labels; cerrar y reabrir correctamente. Completar en cada equipo las pruebas físicas A–Q agregadas en `resultados_pruebas.md` antes de aprobar Hito 2. Registrar fallos y resultados reales sin exigir perfección en oclusiones/orientaciones.

## Fuentes oficiales y terceros

- [Ultralytics YOLO26](https://docs.ultralytics.com/models/yolo26/): modelo y variantes.
- [Predict](https://docs.ultralytics.com/modes/predict/): frames, filtros y resultados.
- [COCO](https://docs.ultralytics.com/datasets/detect/coco/): clases preentrenadas.
- [Ultralytics 8.4.163](https://pypi.org/project/ultralytics/8.4.163/).
- [PyTorch 2.14.0](https://pypi.org/project/torch/2.14.0/) y [torchvision 0.29.0](https://pypi.org/project/torchvision/0.29.0/).
- [Licenciamiento de Ultralytics](https://www.ultralytics.com/license).

Ultralytics se usa como dependencia externa del prototipo académico. Se conserva la licencia existente del repositorio y no se agrega LICENSE. Un despliegue comercial futuro requerirá revisar las condiciones vigentes; esta entrega no decide ese licenciamiento.
