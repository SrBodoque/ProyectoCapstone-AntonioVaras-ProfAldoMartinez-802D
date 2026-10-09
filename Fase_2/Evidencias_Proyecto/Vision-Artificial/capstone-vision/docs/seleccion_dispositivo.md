# Selección opcional y local CPU/CUDA — implementación y validación

Actualización 2026-10-09 sobre el ZIP actual: la base compartida queda en CPU;
la selección personal se guarda en `config/device.local.json`. El selector es
opcional. Las cifras de la entrega anterior se conservan como evidencia histórica.

Mejora incremental sobre `capstone-vision(2).rar`, incluyendo su selector de
cámara. No se reconstruyeron los Hitos 1–3 ni se implementó el siguiente hito.
Los reportes históricos se conservan: el baseline original de Hito 2 fue CPU.

## Uso habitual

Desde `capstone-vision`, con el entorno activado:

```powershell
python -m src.device_selector
```

CPU aparece como opción 0. Las demás opciones corresponden a GPUs visibles para
PyTorch, con índice y nombre. El número del menú no es el índice CUDA: por
ejemplo, opción 1 puede corresponder a `cuda:0`. Si una GPU no puede consultarse,
se omite con aviso y las restantes mantienen sus identificadores CUDA reales.
El selector ofrece las GPUs detectadas; antes de guardar la elegida comprueba
que puede ejecutar una operación pequeña. No carga YOLO, pesos ni cámaras.

Entradas vacías, letras, negativos y opciones fuera del menú se rechazan y se
vuelve a preguntar. `q` cancela sin escribir. EOF devuelve 1, Ctrl+C devuelve 130.
Un fallo de guardado o prueba CUDA devuelve 1 con un mensaje claro.

Luego ejecuta, uno por vez:

```powershell
python -m src.detect
python -m src.track
```

Sin selector ni archivo local, ambos usan CPU sin warnings, preguntas ni escritura.
Si existe una preferencia local válida, ambos la resuelven sin preguntar. Para cambiarla, ejecuta otra vez
el selector. `src.main` sigue siendo preview de cámara. `src.camera_selector`
permanece independiente y sin modificaciones.

CPU puede configurarse si PyTorch funciona. Si falla su importación, el selector
termina con un mensaje controlado antes del menú; no guarda nada. La inferencia
CPU también necesita PyTorch funcional. Si PyTorch es CPU-only, no se ofrecen GPUs aunque Windows detecte una
NVIDIA física. El selector nunca ejecuta pip ni instala Toolkit/cuDNN.

## Restricción encontrada y cambios mínimos

La restricción estaba en `src/config.py`, `load_detection_config()`, líneas
147–148 del adjunto: rechazaba cualquier valor distinto de `cpu`. Se sustituyó
por `validate_device_format()` compartido desde el nuevo `src/devices.py`.

El formato admite `cpu` y `cuda:N`, con N decimal no negativo, sin ceros
iniciales, hasta el máximo entero de 32 bits. Rechaza `gpu`, `cuda`, `cuda:-1`,
`cuda:x`, listas, booleanos y cadenas arbitrarias. No importa PyTorch al leer la
configuración. `cuda:999999` es un formato válido, pero se rechaza al intentar
usarlo si el índice no está entre los dispositivos disponibles.

`src.detector.load_person_model()` ya era el punto de carga compartido por
`PersonDetector` y `PersonTracker`. Se añadió allí la validación de disponibilidad
antes de cargar pesos. En esta actualización ese mismo cargador llama al único
resolver y devuelve el modelo junto con `DeviceResolution`. Detector y tracker
conservan base/preferencia y usan el dispositivo efectivo en su copia de config.
`detect.py` y `track.py` muestran ese valor efectivo en consola y overlay;
`predict()` / `track()` conservan el resto de sus argumentos.

Se revisó `select_device()` del Ultralytics 8.4.163 instalado: admite `cuda:N`
directamente. Se comprobó su selección de `cuda:1` con funciones de hardware
simuladas. No se almacena un nombre comercial ni se requiere conversión interna.
Los índices corresponden a los visibles para PyTorch, incluyendo restricciones
externas de `CUDA_VISIBLE_DEVICES`; pueden diferir entre entornos/equipos.

## Disponibilidad, prueba ligera y errores

`src/devices.py` concentra formato, consulta y validación, compartidos por
configuración, selector, cargador del modelo y diagnóstico:

- Consulta `torch.cuda.is_available()`, `device_count()` y `get_device_name(i)`.
- Informa el build mediante `torch.version.cuda`.
- Para `cuda:N`, exige disponibilidad y `N < device_count()`.
- Antes de guardar una GPU y antes de cargar el modelo, crea un tensor de un
  elemento en esa GPU, suma 1, sincroniza ese índice y verifica el resultado.
- CPU no requiere consultas CUDA ni una prueba GPU.

Un fallo de asignación, kernel, sincronización o resultado impide guardar una
GPU elegida explícitamente. En runtime, una preferencia local CUDA que no pasa
esa misma validación produce warning y CPU temporal; el archivo no se modifica.
El mensaje indica `python -m src.device_selector`. Si una inferencia falla después de inicializarse,
permanecen los manejadores existentes: se informa el error y se liberan cámara y
ventanas. No se introdujo un segundo intento de inferencia en otro dispositivo.

La prueba pequeña no certifica memoria suficiente para todos los modelos ni
sustituye una prueba física prolongada. No hay optimización del modelo, cambios
de precisión, umbrales, tamaño de entrada, cámara, trails ni asociación.

## Persistencia

`save_device()` valida el dispositivo elegido y escribe exclusivamente
`{"device": "cpu"}` o `{"device": "cuda:N"}` en `config/device.local.json`.
No lee ni modifica los parámetros YOLO para guardarlos. El menú valida la base
y permite reemplazar explícitamente una preferencia local corrupta.

Escribe JSON UTF-8 legible en un temporal único dentro del mismo directorio,
hace flush/fsync, cierra y valida el temporal, ejecuta `os.replace()` y recarga
el destino. El bloque `finally` elimina el temporal. Fallos previos al reemplazo
(incluyendo prueba GPU, escritura parcial, validación, fsync o permisos de
reemplazo) conservan el original. El destino nunca se publica parcialmente
escrito. Una falla de lectura posterior al reemplazo se informa; en ese punto
la nueva configuración validada puede estar ya instalada. No se promete
recuperación frente a terminación forzada, corte eléctrico o ediciones externas
concurrentes. Ejecuta un selector a la vez.

`config/detection.json` cambia respecto del ZIP actual únicamente `cuda:0`
por `cpu`; confianza 0.65 y los demás parámetros quedan intactos. La selección
del usuario se guarda solo en su archivo local. También se conservan
las configuraciones de cámara (1280×720, 60 FPS, auto), tracking y YAML.

## Diagnóstico e instalación

`python -m src.diagnostics` informa versión instalada/cargada, build CUDA,
disponibilidad, cantidad/nombres de GPUs, base, preferencia local, dispositivo
efectivo y fallback por separado. No guarda, pregunta ni carga pesos. Para una
preferencia GPU ejecuta la misma prueba ligera con tensor que runtime, de modo
que también detecta kernels o sincronización no utilizables. El fallback local
es un aviso y no vuelve incompleto el diagnóstico por sí solo. Un import roto
de PyTorch sigue siendo error: CPU no puede reparar una DLL bloqueada.

La comparación de versiones ya utilizaba `installed.split('+')[0]`; se conservó.
Las variantes `2.14.0+cpu` / `2.14.0+cu132` y `0.29.0+cu132` no generan una falsa
incompatibilidad con los objetivos base. Los tests verifican estos sufijos.

`requirements.txt` permanece idéntico. README distingue instalación compatible
CPU, wheels CPU-only opcionales y wheels CUDA NVIDIA opcionales. El bloque
cu132 documenta el procedimiento proporcionado como validado por el usuario con
RTX 5060 / driver 610.88; no se instaló ni probó ese equipo desde este servidor.
Si esa instalación ya funciona, solo aplica el código y ejecuta el selector.

## Archivos de la entrega anterior (histórico)

Creados:

- `src/devices.py`: lógica compartida sin dependencias IA al importar.
- `src/device_selector.py`: interacción y persistencia.
- `tests/test_device_selector.py`: 35 pruebas nuevas con CUDA simulado.
- `docs/seleccion_dispositivo.md`: este reporte.

Modificados:

- `src/config.py`: sustituye la restricción CPU-only por validación de formato.
- `src/detector.py`: una llamada al validador compartido antes de cargar el modelo.
- `src/diagnostics.py`: informa hardware y dispositivo configurado.
- `tests/test_hito2.py`: amplía ejemplos inválidos y fija CPU en el fixture del
  modelo simulado para no depender de la selección local.
- `tests/test_hito3.py`: fija CPU y su cargador en el fixture del modelo simulado,
  incluyendo pruebas que construyen `PersonTracker()` sin parámetros.
- `README.md`: instalación opcional, selección, ejecución y enlace a este reporte.

No se eliminó ninguna prueba ni aserción existente. Los casos inválidos anteriores
siguen siendo inválidos; no había un test que rechazara explícitamente `cuda:0`.
Las nuevas pruebas agregan aceptación sintáctica CPU/CUDA y rechazo por hardware.

Idénticos byte a byte: `src/main.py`, `src/detect.py`, `src/track.py`,
`src/tracker.py`, `src/camera.py`, `src/camera_selector.py`, `src/__init__.py`,
todos los archivos de `config/`, `requirements.txt`, `tests/test_hito1.py`,
`tests/test_camera_selector.py`, `tests/test_hito3_integration.py`, reportes,
documentación anterior, `.gitignore` y ajustes de VS Code.

## Evidencia automática de la entrega anterior (histórica)

Entorno de verificación Linux x86_64, Python 3.12.14, dependencias exactas del
requirements. torch cargado 2.14.0+cu130, CUDA build 13.0, CUDA disponible False,
0 GPUs. No se cambió el objetivo Windows/Python 3.13.15.

| Comprobación | Resultado |
| --- | --- |
| Baseline antes de cambios | 114/114 tests, compileall y pip check OK |
| Suite después de cambios | 149/149 tests OK |
| `python -m compileall src tests` | Código 0 |
| `python -m pip check` | Código 0, sin conflictos |
| Suite con `cuda:1` persistido en copia temporal sin GPU | 149/149 OK |
| Selector CPU ejecutado con PyTorch real, configuración temporal | Guardado y recarga OK |
| `python -m src.diagnostics` | Código 0, CPU configurada y CUDA no disponible |
| `python -m src.diagnostics --scan` | Código 0, sin cámaras en este servidor |
| `src.main`, `src.detect`, `src.track` | Código 1: sin sesión gráfica; manejo esperado del entorno |

Las 35 pruebas nuevas cubren imports sin IA/cámaras/input/escritura, CPU-only,
una y varias GPUs, nombre no consultable, consultas fallidas, elección inválida,
prueba ligera, error de kernel/memoria/sincronización, formato y rango, guardado
exclusivo de device, BOM/UTF-8, escritura parcial, temporales, recuperación
explícita a CPU y persistencia leída por otro proceso. Prueban propagación del
índice exacto a predict/track, ausencia de reintentos CPU, liberación ante error
CUDA y lectura por los comandos existentes sin otro selector.

La suite no requiere webcam ni GPU. Sus pruebas del motor ByteTrack real usan
cajas sintéticas, sin descargar pesos. No se ejecutó inferencia física CPU/GPU
ni benchmark nuevo: las pruebas de propagación CUDA utilizan mocks. Se revisó
el diff completo contra el RAR y se compararon hashes para los archivos intactos.

## Validación física en Windows — pendiente

Aplica el contenido de la carpeta entregada conservando tu `.venv`, pesos y
ajustes locales. Desde la raíz del módulo, no desde la raíz del repositorio:

```powershell
.\.venv\Scripts\Activate.ps1
python --version
python -m compileall src tests
python -m unittest discover -s tests -v
python -m pip check
```

1. Primero ejecuta detect/track sin selector ni archivo local: deben usar CPU.
Después elige CPU (opción 0) y comprueba la preferencia local con:

```powershell
Get-Content .\config\device.local.json
python -m src.diagnostics
python -m src.detect
python -m src.track
```

Cierra cada visor con q/ESC antes del siguiente. Deben ejecutar sin preguntas.

2. En el equipo CUDA ya validado, vuelve a ejecutar el selector:

```powershell
python -m src.device_selector
Get-Content .\config\device.local.json
python -m src.diagnostics
python -m src.detect
python -m src.track
```

Elige la opción que muestre `CUDA:0 - NVIDIA GeForce RTX 5060`. Debe guardarse
`cuda:0`; diagnostics debe mostrar build 13.2, CUDA disponible True y el índice
configurado. Cierra cada visor antes del siguiente y comprueba también nuevas
ejecuciones en procesos separados. En otra terminal puedes observar:

```powershell
nvidia-smi -l 1
```

Es una comprobación adicional de actividad; la elección del selector se basa en
PyTorch. No se promete un FPS determinado ni que todo ByteTrack ejecute en GPU:
`device` selecciona dónde ejecuta YOLO; la asociación conserva su implementación.

3. Para probar el fallback temporal, con `cuda:0` local guardado, abre una terminal nueva y
oculta las GPUs solo en esa sesión, restaurando luego el valor anterior:

```powershell
$capstonePreviousCudaVisibility = $env:CUDA_VISIBLE_DEVICES
try {
    $env:CUDA_VISIBLE_DEVICES = '-1'
    python -m src.diagnostics
    python -m src.detect
    python -m src.track
} finally {
    if ($null -eq $capstonePreviousCudaVisibility) {
        Remove-Item Env:CUDA_VISIBLE_DEVICES -ErrorAction SilentlyContinue
    } else {
        $env:CUDA_VISIBLE_DEVICES = $capstonePreviousCudaVisibility
    }
}
```

Con cámara accesible, detect/track deben avisar y continuar en CPU. La preferencia
local `cuda:0` debe conservarse para una futura ejecución con CUDA recuperada.
Si falla primero la cámara o el escritorio, resuelve ese requisito para alcanzar
la validación del modelo. No cambia detection.json ni device.local.json.
No hace falta desinstalar drivers ni modificar el entorno de otro proceso.

4. Ejecuta el selector de nuevo para volver a CPU. Prueba también `q`, entrada
inválida y que detection.json y camera.json permanezcan idénticos al guardar.

## Git, privacidad y fuentes

No se inicializó ni manipuló Git, ramas, historial, commits o remotos.
`camera_index` depende del equipo: revisa sus cambios antes de subir camera.json.
La preferencia personal `device` ahora está ignorada en `config/device.local.json`
y debe excluirse al preparar ZIP; `.gitignore` no filtra automáticamente un ZIP. El ZIP contiene código/documentación
completos; excluye `.venv`, caches, settings generados, pesos y runs.

No se agregaron grabación de imágenes/video, audio, servicios cloud o telemetría.
La carga diferida y las opciones de privacidad de Ultralytics se conservan.

Fuentes primarias consultadas, además del código instalado en las versiones del
requirements:

- [PyTorch: API CUDA](https://docs.pytorch.org/docs/stable/cuda.html): disponibilidad,
  recuento, nombres y sincronización.
- [Ultralytics: select_device](https://docs.ultralytics.com/reference/utils/torch_utils/#ultralytics.utils.torch_utils.select_device):
  formato cuda:N e índices visibles para PyTorch.
- [Instalación oficial de PyTorch](https://pytorch.org/get-started/locally/): elección
  de plataforma y variante del wheel.


## Resolución vigente y archivos inválidos

Orden único en `src/devices.py`: preferencia local válida → base de detection.json.
La base distribuida es CPU. Ausencia local es normal y no crea ningún archivo.
JSON local corrupto, campo ausente, formato inválido o lectura inaccesible producen
warning y se ignoran para esa ejecución, sin reparar silenciosamente el archivo.
La base sigue siendo estricta: falta de detection.json o parámetros esenciales
inválidos producen error; no se ocultan mediante valores predeterminados.
Una GPU puesta manualmente en la base mantiene validación estricta; el fallback
se aplica a la preferencia local personal. Si una inferencia falla después de
inicializarse, permanece el manejo existente; no se repite una inferencia en CPU.

`DeviceResolution` conserva `base_device`, `local_preference`, `effective_device`,
`fallback` y avisos. La copia interna usada por predict/track contiene el valor
efectivo; los JSON originales no cambian. Cámara, DSHOW/MSMF, preview, modelo,
umbrales, ByteTrack, IDs y trails mantienen su comportamiento.

La instalación normal es suficiente para CPU. CUDA sigue siendo manual/opcional,
y no hay reglas por nombre RTX 5060/GTX 1650. El caso reportado WinError 4551 al
importar torch por bloqueo de torch.dll se conserva como contexto del usuario:
no se reproduce ni se modifica seguridad Windows. Su import CPU fue reportado
funcional; detect/track en ese notebook siguen pendientes de prueba física.


## Evidencia automática de esta actualización (2026-10-09)

Entorno aislado Linux x86_64 / Python 3.12.14; versiones exactas de requirements,
con torch 2.14.0+cpu y torchvision 0.29.0+cpu. CUDA build None, disponible False,
0 GPUs. El objetivo Windows/Python 3.13.15 no fue modificado.

| Comprobación actual | Resultado |
| --- | --- |
| ZIP original, tras instalar dependencias en entorno de prueba | 149/149 tests OK |
| Suite actual | 177/177 tests OK: 28 casos nuevos, pruebas previas adaptadas |
| compileall src tests | Código 0 |
| pip check | Código 0, sin conflictos |
| diagnostics, sin preferencia local | Código 0; base CPU / local no configurada / efectivo CPU |
| Imports config/devices/device_selector/main/detect/track | Código 0 |
| YOLO26n real, frame negro sintético, sin selector | Inferencia CPU OK; archivo local no creado |
| YOLO + ByteTrack reales, frame negro sintético, sin selector | Inferencia CPU OK; archivo local no creado |
| Preferencia cuda:0 con PyTorch CPU real | Ambas inferencias CPU OK; warning; preferencia conservada |
| Selector CPU con PyTorch real | Preferencia local guardada; base y cámara intactas |
| Preferencia local corrupta con PyTorch CPU real | Ambas inferencias CPU OK; archivo corrupto conservado |
| main/detect/track en este servidor sin escritorio | Código 1 controlado por ausencia de sesión gráfica |

Las inferencias usan pesos oficiales, pero frames sintéticos sin personas: no
certifican precisión, IDs con personas, webcam, FPS ni GPU física. El ByteTrack
real también se verifica con cajas sintéticas en la suite existente. La primera
validación antes de instalar dependencias fallaba por falta de cv2/Ultralytics;
se registró como limitación inicial y se repitió sobre el ZIP original tras
instalar los paquetes. Un primer intento de suite modificada se interrumpió por
un mock del import de PyTorch sin adaptar al menú nuevo; el fixture fue corregido
y la suite completa posterior pasó. No quedó un fallo de pruebas pendiente.

DEV-01 a DEV-08 en `resultados_pruebas.md` siguen pendientes como pruebas físicas.
Se revisaron funcionalidad, regresión y distribución, incluyendo el diff completo
contra el ZIP original, conservación byte a byte de cámara/requirements/tracking,
y exclusión del archivo local de la entrega.
