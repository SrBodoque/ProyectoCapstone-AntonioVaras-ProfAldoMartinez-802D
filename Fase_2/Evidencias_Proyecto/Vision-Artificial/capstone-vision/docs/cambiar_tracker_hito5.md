# Cambiar el tracker de Hito 5.1 sin editar Python

La selección afecta **solo a `python -m src.track_count`**. Los comandos históricos y `src.track_zones` conservan su configuración y comportamiento. La FSM es la misma para las cuatro alternativas.

## Archivo y valores válidos

Edite únicamente el valor `tracker` en **`config/counting.json`**. Deje el bloque `thresholds` intacto si solo quiere comparar trackers.

| Valor exacto | Nombre mostrado | YAML existente reutilizado | Confianza efectiva YOLO |
| --- | --- | --- | --- |
| `botsort_reid` | BoT-SORT + ReID | `config/botsort_reid_capstone.yaml` | General de `detection.json`: 0.65 en el ZIP |
| `fasttracker` | FastTracker | `config/fasttrack_capstone.yaml` | General: 0.65 |
| `bytetrack` | ByteTrack | El YAML señalado por `config/tracking.json`: actualmente `config/bytetrack_capstone.yaml` | General: 0.65 |
| `recovery` | ByteTrack Recovery (Experimental) | `config/bytetrack_recovery_capstone.yaml` | Override existente: 0.10, exclusivo de Recovery |

BoT-SORT + ReID es el valor entregado por defecto. No escriba `fasttrack` en este campo: el valor de selección es `fasttracker`, aunque el backend interno del YAML se llame `fasttrack`.

## Procedimiento exacto

1. Cierre `track_count` con Q/Esc antes de cambiar la selección.
2. En PowerShell, ubicado en `capstone-vision`, abra el archivo:

   ```powershell
   notepad .\config\counting.json
   ```

3. Para pasar a FastTracker, cambie solamente:

   ```json
   "tracker": "botsort_reid",
   ```

   por:

   ```json
   "tracker": "fasttracker",
   ```

   Estos son fragmentos de la línea que debe editar: no reemplace todo el archivo por una sola línea. Conserve las llaves, comas y el bloque completo `thresholds`.

4. Guarde con Ctrl+S y cierre el editor.
5. Ejecute con el entorno existente:

   ```powershell
   & .\.venv\Scripts\python.exe -m src.track_count
   ```

6. Compruebe que la pantalla indica **Tracker: FastTracker** y el dispositivo efectivo esperado. El log inicial identifica también el tracker y el YAML mediante el motor existente.
7. Para volver a BoT-SORT, cierre el visor, restaure `"tracker": "botsort_reid",`, guarde y vuelva a ejecutar. Para ByteTrack o Recovery use el valor exacto de la tabla.

Cada reinicio comienza una sesión con cero entradas. Cambiar de tracker no borra ni activa perfiles de zonas, ni cambia cámara o CPU/GPU. No hay cambio de tracker en caliente.

## Qué se reutiliza y por qué hay un archivo nuevo

El proyecto ya contiene un cargador de YAML (`load_tracker_config`), un resolutor de rutas (`resolve_tracker_path`) y `PersonTracker`, capaz de ejecutar los backends integrados. También contiene entrypoints con las rutas específicas y el override de Recovery.

`config/tracking.json` es una configuración compartida: cambiarla afectaría los comandos anteriores y por sí sola no expresa el override 0.10 de Recovery. Por eso `config/counting.json` contiene únicamente la elección exclusiva del contador y sus umbrales. No se creó otro selector interactivo ni nuevos YAML. El adaptador usa los cargadores y constantes existentes, conserva las opciones visuales/persistencia de la configuración base y valida que el YAML corresponda al backend solicitado.

## Configuraciones preservadas

- BoT-SORT: `with_reid=true`, `model=auto`, `gmc_method=none`, `proximity_thresh=0.50`, `appearance_thresh=0.80` y los demás valores actuales del YAML.
- FastTracker: todos los parámetros de movimiento/oclusión y asociación de su YAML.
- ByteTrack: YAML y confianza del baseline actual.
- Recovery: YAML con umbrales alto/nuevo 0.65 y bajo 0.10, más la confianza efectiva YOLO 0.10 tomada de su entrypoint; no se propaga a los otros modos.

No modifique `src/*.py`, `config/detection.json`, `config/tracking.json`, los YAML, `config/camera.json`, `config/device.local.json`, los perfiles de `config/zones/`, `requirements.txt` ni README para elegir el tracker. Para cámara y dispositivo existen sus selectores; para zonas, el calibrador.

## Si aparece un error

| Mensaje o situación | Acción |
| --- | --- |
| JSON inválido, campos ausentes o nombre desconocido | Revise comillas dobles, comas y el valor exacto de la tabla. Conserve los ocho umbrales. |
| YAML ausente o backend incompatible | Compruebe que copió el proyecto completo. No renombre YAML ni sustituya archivos de otro tracker. |
| Baseline apunta a Recovery | Revise la configuración base con el equipo; no se aplica Recovery sin su override. |
| No existe un perfil activo | Ejecute `src.zone_calibrator`, guarde y active A/B. |
| Geometría ambigua o salida B no visible | Revise orientación A exterior/B baño, convexidad, alineación y espacio visible posterior a B. |
| Índice de cámara o aspecto incompatible | Revise la cámara seleccionada y recalibre si corresponde. |
| Dependencias, pesos o tracker no disponibles | Revise el entorno existente y el mensaje concreto. El contador no cambia silenciosamente a otro tracker ni instala paquetes. |
| GPU no disponible | El motor conserva el comportamiento previo de resolución/fallback con aviso. Compruebe en pantalla el dispositivo realmente usado. |

La confianza y el YAML se verificaron con el motor común y un modelo simulado. La disponibilidad y eficacia de cada tracker en el equipo real se deben comprobar físicamente. Elegir un nombre en la configuración no acredita precisión.
