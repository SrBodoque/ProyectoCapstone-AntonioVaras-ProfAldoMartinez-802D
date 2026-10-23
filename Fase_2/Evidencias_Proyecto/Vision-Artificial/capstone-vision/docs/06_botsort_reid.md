# BoT-SORT + ReID — experimento de apariencia temporal

Estado: integración de código y pruebas simuladas completadas; **inferencia real y
pruebas físicas pendientes**. Esta entrega no demuestra mejoras de IDs ni FPS.
El entorno de desarrollo carece de OpenCV, Ultralytics, PyTorch, torchvision y lap.

Desde `capstone-vision`, con el entorno que ya funciona activo:

```powershell
python -m src.track_botsort_reid
```

Reutiliza cámara, dispositivo/fallback, YOLO26n, clase 0, confianza **0.65**, IoU 0.7,
imgsz 640, persistencia, trails de 30 puntos, colores, métricas y cierres del loop
existente. No selecciona ni guarda preferencias. ByteTrack sigue siendo el modo
predeterminado; Recovery conserva exclusivamente su override 0.10.

## Configuración y verificación real

`config/botsort_reid_capstone.yaml` contiene los valores solicitados, sin tuning:

```yaml
tracker_type: botsort
track_high_thresh: 0.25
track_low_thresh: 0.10
new_track_thresh: 0.25
track_buffer: 30
match_thresh: 0.80
fuse_score: true
gmc_method: none
proximity_thresh: 0.50
appearance_thresh: 0.80
with_reid: true
model: auto
```

El nuevo modo exige Ultralytics **8.4.163**, sin instalar ni actualizar paquetes.
`auto` deja que la biblioteca elija características del detector o el extractor
oficial adicional. Para el cabezal end-to-end de YOLO26n se espera
`yolo26n-cls.pt`: es un **clasificador usado para extraer apariencia**, no un modelo
especializado en reidentificación de personas. El valor efectivo solo se anuncia
cuando se observa la instancia inicializada; no se da por confirmado aquí.

El primer inicio puede descargar los pesos oficiales mediante Ultralytics. Si
falta el modelo o falla la descarga/inicialización, se informa el error y termina
la sesión. Los pesos no forman parte de este ZIP.

La consola distingue tres evidencias, obtenidas durante la ejecución:

1. Instancia oficial BOTSORT, encoder invocable, modelo efectivo y dispositivo
   comprobados. Todavía no confirma extracción sobre detecciones.
2. Características `curr_feat`/`smooth_feat` válidas, finitas y no nulas por cada
   detección recibida; cantidad contrastada antes del tracking.
3. Características entregadas a `get_dists` oficial con tracks y detecciones,
   distancias válidas: mensaje **“ReID activo verificado”**. Esto no implica que
   apariencia haya decidido el emparejamiento ni que el ID resultante sea correcto.

La comprobación usa callbacks y observa `init_track`/`get_dists` únicamente en la
instancia de esta sesión. Delega a los métodos originales; no copia el algoritmo,
no cambia costes, no vuelve a ejecutar el detector y no modifica archivos/clases
de Ultralytics. No imprime ni conserva copias de vectores. Una ausencia de personas
no es un fallo. Si hay detecciones pero falta extracción, o hay tracks y detecciones
pero no se observa asociación, el programa se detiene con un error claro.

El detector y el predictor del clasificador deben usar el dispositivo efectivo
resuelto por el proyecto. Una discrepancia produce un error, sin cambiar la
preferencia local. La ruta nativa exige el hook del detector. La compatibilidad
con las APIs exactas 8.4.163 debe completarse en el entorno instalado del usuario.
Las páginas oficiales consultadas representan `main`; los enlaces a la etiqueta
8.4.163 no fueron accesibles en este entorno.

## Privacidad y recursos

La cámara observa el acceso, nunca el interior. No se incorporan reconocimiento
facial, nombres, perfiles, búsqueda entre cámaras ni identidad entre ejecuciones.
Frames, recortes internos y apariencia se procesan localmente en memoria, sin
exportarlos. No se guardan fotos, videos, recortes ni embeddings. Se conservan las
opciones existentes contra telemetría, guardado y autoinstalación.

El tracker mantiene estado temporal en sus listas internas; su retención depende
del algoritmo, `track_buffer` y sus reglas de retirada. No se promete borrar cada
vector a un número exacto de segundos. El diagnóstico no añade un historial de
apariencia. Al terminar el proceso se liberan modelos y estado; la cámara y las
ventanas se liberan con los mecanismos existentes, también ante errores y Ctrl+C.

El usuario ya validó CUDA y ByteTrack en GTX 1650 de 4 GB, con aproximadamente
18–24 FPS. Esa observación previa no es una medida de este modo. El clasificador
adicional aumenta trabajo y puede aumentar VRAM; el coste crece con las personas
observadas. No se promete mantener 20 FPS ni se habilita FP16/TensorRT.

## Comprobaciones sin webcam

```powershell
python -m compileall src tests
python -m pip check
python -m unittest discover -s tests -v
python -m src.diagnostics
python -c "import src.track, src.track_fast, src.track_recovery, src.track_botsort_reid"
python -m unittest discover -s tests -p "test_botsort_reid*.py" -v
```

Los tests nuevos separan 43 casos con dobles de prueba de 10 casos de integración
real. Estos últimos requieren las dependencias originales. Siete ejercitan el
motor con cajas/características sintéticas; tres requieren los dos pesos oficiales
locales en la raíz y la muestra pública `bus.jpg` incluida por Ultralytics. No
exigen webcam ni GPU y no descargan imágenes personales. La prueba de inferencia
comprueba dos frames con detecciones reales y observa la función real
`embedding_distance`, sin sustituir su cálculo. Ausencias se muestran como
`skipped`; revisar los motivos, no interpretar un `OK (skipped=...)` como validación
completa. El comando interactivo sí admite la descarga oficial normal de pesos.

En esta entrega pasan 43 tests nuevos simulados y 212 regresiones mediante un
arnés externo que simula OpenCV. La suite normal falla por dependencias ausentes
antes y después: no se presenta como aprobada. Informe completo en
`REPORTE_BOTSORT_REID_EXPERIMENTAL.md`.

## Comparación física pendiente

Ejecutar un visor a la vez, sin mover cámara ni cambiar iluminación, dispositivo,
confianza o resolución entre ByteTrack y BoT-SORT:

```powershell
python -m src.track
python -m src.track_botsort_reid
# Referencias adicionales, en procesos separados:
python -m src.track_fast
python -m src.track_recovery
```

Esperar la inicialización y los mensajes de extracción/asociación antes de medir.
Repetir BOT-04 a BOT-10 y BOT-13 al menos tres veces por tracker. Registrar por
repetición IDs antes/después, cambios e intercambios, mismo ID tras oclusión,
FPS, ms YOLO, ms totales, cajas sin ID, tracks falsos y detecciones perdidas.
Registrar también dispositivo, personas visibles y VRAM si se puede observar.
La diferencia de tiempo entre modos incluye el algoritmo y el diagnóstico,
además de ReID: no atribuir toda la diferencia exclusivamente al extractor.

| Caso | Escenario / observación principal | Resultado |
| --- | --- | --- |
| BOT-01 | Una persona caminando; continuidad de ID | Pendiente |
| BOT-02 | Una persona detenida; continuidad | Pendiente |
| BOT-03 | Dos personas separadas; IDs sin intercambio | Pendiente |
| BOT-04 | Cruce rápido; IDs antes y después | Pendiente |
| BOT-05 | Cruce lento; IDs antes y después | Pendiente |
| BOT-06 | Una persona detrás de otra; continuidad | Pendiente |
| BOT-07 | Oclusión parcial prolongada | Pendiente |
| BOT-08 | Oclusión completa breve; recuperación de ID | Pendiente |
| BOT-09 | Oclusión completa prolongada; límites | Pendiente |
| BOT-10 | Ropa similar; asociaciones equivocadas | Pendiente |
| BOT-11 | Salir y volver; sin exigir identidad indefinida | Pendiente |
| BOT-12 | Falsos positivos conocidos; tracks falsos | Pendiente |
| BOT-13 | Tres o más personas; cruces múltiples | Pendiente |
| BOT-14 | GTX 1650; FPS y coste/VRAM | Pendiente |
| BOT-15 | ByteTrack con movimientos equivalentes | Pendiente |

Plantilla por repetición (solo observaciones, sin imágenes ni vectores):

| Caso / repetición | Modo / dispositivo | IDs antes → después | FPS / ms YOLO / ms total | Sin ID / falsos / perdidas | Observaciones |
| --- | --- | --- | --- | --- | --- |
| Pendiente | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |

ReID no crea detecciones ausentes. `conf=0.65` sigue filtrando observaciones débiles
antes de la asociación. Las oclusiones completas, la proximidad espacial, ropa
parecida, iluminación y ángulos pueden impedir o confundir asociaciones. Aumentar
retención puede producir errores y no se ha hecho. Mantener IDs no demuestra
precisión IN/OUT: zonas, FSM y conteo siguen fuera de este experimento.

## Fuentes oficiales y alcance de la consulta

- [Tracking](https://docs.ultralytics.com/modes/track/).
- [Callbacks de tracking](https://docs.ultralytics.com/reference/trackers/track/).
- [BoT-SORT](https://docs.ultralytics.com/reference/trackers/bot_sort/).
- [Extractor ReID](https://docs.ultralytics.com/reference/trackers/utils/reid/).
- [GMC](https://docs.ultralytics.com/reference/trackers/utils/gmc/).
- [track.py 8.4.163](https://github.com/ultralytics/ultralytics/blob/v8.4.163/ultralytics/trackers/track.py),
  [bot_sort.py 8.4.163](https://github.com/ultralytics/ultralytics/blob/v8.4.163/ultralytics/trackers/bot_sort.py),
  [botsort.yaml 8.4.163](https://github.com/ultralytics/ultralytics/blob/v8.4.163/ultralytics/cfg/trackers/botsort.yaml):
  consulta bloqueada; no se afirma haber inspeccionado estos archivos exactos.
