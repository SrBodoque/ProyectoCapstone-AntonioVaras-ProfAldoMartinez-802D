# Selector persistente de cámara

Implementación incremental del 29-09-2026 sobre `capstone-vision(1).rar` adjunto.
Esta mejora configura la cámara del equipo; no implementa otro hito.

## Uso

Desde `capstone-vision`, con el entorno activado y los visores cerrados:

```powershell
python -m src.camera_selector
```

El selector prueba índices 0 a 4 con el backend, resolución y FPS de
`config/camera.json`. Lista únicamente los que entregaron un primer frame válido.
Muestra dimensiones del frame, backend utilizado y FPS informados por el
controlador; estos últimos no son una medición de rendimiento.

Introduce uno de los índices listados. Texto, índices negativos o no disponibles
provocan una nueva solicitud. `q` cancela sin guardar. Sin cámaras disponibles,
termina con código 1, sin preguntar ni cambiar el archivo. EOF termina con código
1; Ctrl+C interrumpe con código 130. Un error de configuración o escritura se
informa sin traceback innecesario.

Las cámaras ya están liberadas cuando aparece la pregunta. El selector no abre
un visor ni conserva imágenes; solo guarda el índice elegido.

Después, ejecuta cualquiera de los comandos habituales:

```powershell
python -m src.main
python -m src.detect
python -m src.track
```

Ejecuta uno por vez y cierra su ventana antes del siguiente. Cada proceso lee el
mismo archivo, por lo que recuerda la selección sin preguntas ni escaneo nuevo.
Si ese dispositivo no está disponible, se conserva el error seguro existente.
El fallback de backend para `auto` sigue probando el mismo índice; no selecciona
otra cámara. Para cambiar el índice, vuelve a ejecutar el selector.

`python -m src.diagnostics --scan` continúa siendo diagnóstico técnico: no pide
una elección ni guarda configuración. Los avisos nativos de OpenCV al probar
índices inexistentes o backends incompatibles pueden aparecer también durante
el selector. No se ocultan globalmente; no convierten esos intentos en cámaras
disponibles.

## Alcance y archivos

Se inspeccionaron código, configuraciones, pruebas, README, reportes y documentos
del adjunto antes de editar. Baseline del adjunto: 90 pruebas aprobadas.

Archivos creados:

- `src/camera_selector.py`
- `tests/test_camera_selector.py`
- `docs/seleccion_camara.md` (este reporte)

Archivo modificado:

- `README.md`: uso del selector, persistencia, diferencia frente a diagnóstico y
  advertencia de configuración por equipo.

Todos los módulos originales permanecen **idénticos byte a byte**:

- `src/__init__.py`
- `src/config.py`
- `src/camera.py`
- `src/main.py`
- `src/detect.py`
- `src/detector.py`
- `src/track.py`
- `src/tracker.py`
- `src/diagnostics.py`

También se conservan byte a byte los cuatro archivos de pruebas originales,
todos los archivos de configuración, `requirements.txt`, reportes y documentos
previos, `.gitignore` y los ajustes de VS Code. No se agrega `input()` ni selección
a los ejecutables existentes. No hay cambios en YOLO, ByteTrack o sus umbrales.

El `camera.json` entregado conserva los valores REALES del adjunto: índice 0,
1280×720, **60 FPS solicitados**, backend `auto`. La detección conserva confianza
0.65. No se impusieron valores de versiones anteriores.

## Recursos y persistencia

`scan_cameras()` utiliza `camera_session()` y `camera_info()` existentes. La
apertura valida el primer frame y libera cada intento fallido; el contexto
libera cada captura exitosa al salir, incluso ante excepción o Ctrl+C. El scan
es secuencial y termina antes de solicitar entrada. No hay otra implementación
de `VideoCapture`, ni importación de YOLO/torch/torchvision/ByteTrack desde el
selector. Importarlo tampoco carga OpenCV ni abre cámaras.

Al guardar, se vuelve a leer y validar el JSON vigente con `load_config()`. Se
copia y se reemplaza exclusivamente el valor de `camera_index`; los valores y
tipos de `width`, `height`, `fps` y `backend` se conservan. El formato se escribe
como JSON UTF-8 legible, con indentación de dos espacios.

La escritura usa un temporal único en el mismo directorio, flush y fsync. El
temporal se cierra y valida antes de `os.replace()`, y luego se vuelve a cargar
el destino con `load_config()`. El reemplazo evita publicar JSON escrito a
medias. Un fallo de escritura, sincronización, validación previa o reemplazo
conserva el archivo original; el bloque `finally` retira el temporal. Si falla
la comprobación posterior al reemplazo, se informa el error: el archivo nuevo
puede ya estar instalado. No se promete recuperación ante corte eléctrico,
terminación forzada o modificaciones concurrentes externas; ejecuta un solo
selector a la vez. No quedan temporales tras un guardado normal.

## Verificación automática

Entorno de prueba: Linux x86_64, Python 3.12.14, entorno virtual temporal fuera
del proyecto. Se instalaron las versiones exactas de `requirements.txt` sin
cambiar dependencias. El objetivo Windows/Python 3.13.15 se conserva.

| Comprobación | Antes de cambios | Después |
| --- | --- | --- |
| `python -m compileall src tests` | OK | OK |
| `python -m unittest discover -s tests -v` | 90/90 OK | 114/114 OK |
| `python -m pip check` | Sin conflictos | Sin conflictos |

Las 24 pruebas nuevas cubren importación sin OpenCV/IA, escaneo simulado de
frames válidos y vacíos, fallos de apertura y consulta, liberación secuencial y
Ctrl+C, selección válida e inválida, cancelación, ausencia de cámaras, EOF,
conservación de los otros campos, validación y recarga, persistencia leída por
otro proceso, fallos de escritura parcial/fsync/reemplazo y limpieza de
temporales. También comprueban que los tres ejecutables existentes reciben el
índice guardado, en ejecuciones repetidas, sin preguntas ni escaneo. Sus bucles
de cámara se simulan en esa prueba; no equivale a una validación física.

Todas las escrituras de tests usan `TemporaryDirectory`. Los 90 tests anteriores
incluyen las cuatro pruebas del motor ByteTrack real sobre cajas sintéticas.
El selector se ejecutó además en este servidor sin dispositivos: código 1,
mensaje de ausencia de cámaras, sin traceback y `camera.json` intacto.

Se compararon hashes SHA-256 contra los archivos extraídos del RAR. Solo README
cambia entre los archivos originales. El ZIP incluye la carpeta completa de
código y documentación; excluye `.venv`, cachés, `.ultralytics`, pesos, metadatos
Git y otros artefactos generados. No se manipularon commits, ramas ni remotos.

## Validación física pendiente en Windows

No hay webcam ni escritorio Windows en el servidor de validación. No se declara
aprobada la prueba física del selector. En el equipo real, conserva tu entorno y
pesos locales al aplicar los archivos actualizados. Desde `capstone-vision`:

```powershell
.\.venv\Scripts\Activate.ps1
python --version
python -m compileall src tests
python -m unittest discover -s tests -v
python -m pip check
Get-Content .\config\camera.json
python -m src.camera_selector
Get-Content .\config\camera.json
```

1. Conecta DroidCam u otra cámara, cierra programas que la usen y ejecuta el
   selector. Debe listar solamente los índices que entregan frames.
2. Prueba `texto`, `-1` y `5`: debe volver a preguntar. Selecciona un índice
   listado, por ejemplo `1` solo si existe. Verifica que solo cambió
   `camera_index` y que siguen intactos ancho, alto, FPS y backend.
3. Ejecuta por separado los siguientes comandos, cerrando cada visor con `q` o
   ESC antes del siguiente:

```powershell
python -m src.main
python -m src.detect
python -m src.track
```

4. Comprueba en consola y en la imagen que los tres usan la cámara seleccionada,
   sin preguntar. Repite los comandos en procesos nuevos y comprueba que el
   índice persiste y que el dispositivo se libera al cerrar.
5. Ejecuta otra vez `python -m src.camera_selector` para cambiar de cámara, si
   existe otra. Repite la comprobación. Prueba también cancelar con `q`.
6. Si puedes desconectar todas las cámaras, ejecuta el selector: debe terminar
   con código 1 (`$LASTEXITCODE` en PowerShell), sin cambiar el JSON. Si solo
   desconectas la elegida y ejecutas un visor, debe mostrar su error seguro,
   sin seleccionar silenciosamente un índice distinto.

## Configuración por equipo y Git

`camera_index` depende del dispositivo y su enumeración; 1 no significa siempre
DroidCam. `camera.json` está versionado y ejecutar el selector genera un cambio
local. Revisa el diff y evita subir accidentalmente esa selección si otros
computadores necesitan otro índice. No se añade `camera.local.json` ni otra capa
de configuración en esta iteración.
