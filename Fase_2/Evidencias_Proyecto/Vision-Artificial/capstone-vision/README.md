# capstone-vision — Hitos 1 y 2

Módulo de visión del sistema inteligente de gestión de limpieza de servicios higiénicos basado en demanda real, proyecto CAPSTONE de Ingeniería en Informática, Duoc UC.

El Hito 1 aprobado permite diagnosticar y visualizar una webcam local. El Hito 2 agrega detección de personas por frame con YOLO26 Nano, sin identificación ni conteo de entradas/salidas. No graba, guarda ni transmite imágenes, video o audio desde la aplicación. El Hito 2 requiere completar las pruebas físicas antes de avanzar.

## Requisitos y versiones

- Windows 10/11 de 64 bits, webcam y sesión de escritorio.
- Visual Studio Code y PowerShell.
- **Python 3.13.15 x64**, instalación convencional, sin modo experimental free-threaded.
- **opencv-python==4.14.0.94**, conservado del Hito 1. Incluye interfaz gráfica; no instalar el paquete headless ni otras variantes de OpenCV conjuntamente.
- **ultralytics==8.4.163**, **torch==2.14.0**, **torchvision==0.29.0**.
- Internet para instalar dependencias y descargar una vez los pesos oficiales. Después, inferencia local en CPU; no se necesita cuenta ni API key.

Descarga Python desde su [página oficial de versión](https://www.python.org/downloads/release/python-31315/), opción Windows installer (64-bit). Habilita su incorporación a PATH durante la instalación y abre una terminal nueva. OpenCV está fijado según su [distribución en PyPI](https://pypi.org/project/opencv-python/4.14.0.94/). No cambies versiones ante un error sin registrar y revisar primero la causa.

## Instalación desde cero en PowerShell

Extrae el ZIP. En VS Code, usa **Archivo > Abrir carpeta** y selecciona la carpeta que contiene este README, `requirements.txt` y `src`. Abre **Terminal > Nueva terminal**, perfil PowerShell. Todos los comandos siguientes se ejecutan desde esa raíz.


## 2. Python

Comprueba el intérprete antes de crear un entorno nuevo:

```powershell
py --list
py -3.13 --version
```

Debe mostrar **Python 3.13.15**. Si no está instalado, usa el instalador oficial enlazado arriba. Con Winget puedes comprobar disponibilidad:

```powershell
winget show --id Python.Python.3.13 --versions
```

Solo si aparece 3.13.15, se puede solicitar esa versión:

```powershell
winget install --id Python.Python.3.13 --version 3.13.15 -e --scope user
```

Si Winget indica que no hay actualización, verifica de nuevo `py -3.13 --version`; ese aviso no acredita la versión instalada. Si no coincide, usa el instalador oficial. Si `python` abre Microsoft Store, utiliza el lanzador `py` y revisa instalación/PATH.

## 3. Entorno e instalación

Desde la raíz del repositorio compartido, entra una sola vez en el módulo:


PRIMER PASO:
```powershell
cd .\Fase_2\Evidencias_Proyecto\Vision-Artificial\capstone-vision
```

**Si ya tienes el .venv funcional del Hito 1, consérvalo y salta la creación.** Solo en un computador sin entorno, después de verificar Python:

```powershell
py -3.13 -m venv .venv
```

Activa y actualiza las dependencias del mismo entorno:

```powershell
.\.venv\Scripts\Activate.ps1
python --version
python -c "import struct; print(struct.calcsize('P') * 8)"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
```

Esperado: Python 3.13.15, 64 bits y `No broken requirements found`. Ejecuta una línea a la vez. No copies entornos entre computadores: la entrega actualizada no incluye `.venv`; al copiar sus archivos sobre tu proyecto, conserva tu entorno local.

Si PowerShell bloquea la activación, puedes **evitar cambiar cualquier política** usando el intérprete directamente:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m src.diagnostics
```

En cualquier comando posterior sustituye `python` por `.\.venv\Scripts\python.exe` si no activaste el entorno. Alternativamente, solo para esa terminal y si las políticas de tu organización lo permiten:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

No requiere una modificación global ni ejecutar como administrador. No intentes eludir una política corporativa.

## Seleccionar intérprete en VS Code

Instala las extensiones recomendadas cuando VS Code lo sugiera. Presiona `Ctrl+Shift+P`, busca **Python: Select Interpreter**, selecciona `.venv\Scripts\python.exe`; si no aparece usa **Enter interpreter path** y navega a ese archivo dentro del proyecto. Abre una nueva terminal y verifica:

```powershell
python -c "import sys; print(sys.executable); print(sys.prefix != sys.base_prefix)"
```

Esperado: el ejecutable de `.venv` y `True`. La configuración de VS Code propone ese intérprete, pero no reemplaza automáticamente una selección anterior. Si `code` está disponible en PATH también puedes abrir la carpeta desde PowerShell con `code .`.

## Diagnóstico, pruebas automáticas y webcam

```powershell
python -m src.diagnostics
python -m unittest discover -s tests -v
python -m src.diagnostics --scan
python -m src.main
```

Usa ejecución como módulo **desde la raíz**, no `python src/main.py` ni el botón que ejecuta el archivo suelto. `diagnostics` sin `--scan` no abre la cámara. Con `--scan` prueba 0 a 4, lee un frame por intento exitoso y libera inmediatamente cada cámara antes de pasar a la siguiente. Puede encender su indicador luminoso; no guarda esos frames. Índices ausentes generan avisos y no abortan todo el diagnóstico. Un escaneo sin cámaras puede devolver 0 si el entorno está completo: eso significa que completó el diagnóstico, no que haya aprobado la webcam. En Hito 2, dependencias IA ausentes/rotas o configuración de detección inválida devuelven 1 después de informar y completar el escaneo de cámara.

El preview debe mostrar video en vivo, resolución del frame, FPS aproximados del bucle, índice y backend. Los FPS empiezan en 0 hasta completar el primer intervalo de medición. La consola muestra valores solicitados y los reportados por el controlador, que pueden ser diferentes. Mantén la ventana enfocada y cierra con `q` minúscula o `ESC`. También se atiende el cierre de ventana; `Ctrl+C` en la terminal realiza limpieza. La app devuelve 1 ante un error y 0 ante cierre normal.

Mantén el preview al menos 30 segundos. Repite apertura y cierre con ambas teclas; luego comprueba que Cámara de Windows puede usar la webcam. Cierra Cámara de Windows antes de volver a nuestra aplicación.

## Configuración

Edita `config/camera.json` con la aplicación cerrada:

```json
{
  "camera_index": 0,
  "width": 1280,
  "height": 720,
  "fps": 30,
  "backend": "auto"
}
```

Reinicia el programa para cargar cambios. No hay recarga en vivo ni valores alternativos ocultos: los cinco campos son obligatorios. El índice es entero no negativo, dimensiones enteras positivas, FPS positivo finito; backend es una cadena reconocida. Los booleanos no se aceptan como números. Campos extra se rechazan para detectar errores de escritura.

En Windows `auto` intenta DirectShow, después MSMF y por último selección automática de OpenCV. Un intento debe abrir y entregar un primer frame; si falla se libera antes del siguiente. Puedes forzar `dshow` o `msmf`; en ese caso no hay fallback. En otros sistemas existen `v4l2` (Linux) y `avfoundation` (macOS). No se fuerzan backends de otro sistema. Los parámetros son solicitudes: el hardware puede ignorarlos.

## Problemas comunes

| Síntoma                       | Acción                                                                                                                                                                                                  |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| No abre cámara                | Cierra otras aplicaciones, revisa USB y permisos de cámara para aplicaciones de escritorio en Configuración de Windows. Ejecuta `--scan` y usa un índice que entregue frames.                           |
| Abre pero no entrega frames   | Prueba el otro backend de Windows o resolución 640×480 a 30 FPS, reinicia y registra el resultado.                                                                                                      |
| No existe `cv2` / error DLL   | Confirma el intérprete y la instalación. Guarda el error completo; revisa que no haya paquetes OpenCV de variantes distintas. Consulta los requisitos de runtime de Windows de la distribución oficial. |
| `No module named src`         | Abre terminal en la carpeta donde está `requirements.txt` y usa `python -m src.main`.                                                                                                                   |
| JSON inválido o campo ausente | Restaura los cinco campos del ejemplo, comillas dobles y sin coma final.                                                                                                                                |
| FPS o tamaño distintos        | Compara propiedades reportadas y resolución visible. El dispositivo no garantiza los valores pedidos.                                                                                                   |
| Teclas no cierran             | Enfoca la ventana de video; usa q minúscula o ESC. Como alternativa usa Ctrl+C en terminal.                                                                                                             |
| Entorno sin escritorio        | El preview requiere sesión gráfica. En Linux sin display se informa el error antes de iniciar la GUI.                                                                                                   |

## Git y organización

Este módulo pertenece al repositorio compartido en `Fase_2/Evidencias_Proyecto/Vision-Artificial/capstone-vision`. Copia los archivos actualizados dentro del mismo módulo y revisa los cambios desde el repositorio padre. **No crees un repositorio Git anidado.**

```powershell
git status --short --untracked-files=all
git diff
```

La entrega no incluye `.git`, no hace commits ni push y no cambia remotos o licencias.

`.venv`, cachés, logs, pesos `*.pt`, `runs/` y ajustes locales `.ultralytics/` se ignoran; documentación y configuración se conservan. No se ha agregado una licencia. `logs/` está reservado: actualmente solo hay mensajes técnicos de consola, no archivos de log.

`src/config.py` valida configuración; `camera.py` gestiona capturas; `main.py` presenta video; `diagnostics.py` inspecciona el entorno. `tests/` usa solo `unittest` y dobles de prueba para errores y liberación de recursos: no demuestra funcionamiento físico de la cámara.

Completa [las pruebas de aceptación](docs/resultados_pruebas.md). Consulta [el procedimiento detallado](docs/01_entorno_y_webcam.md) y [el contexto](docs/00_contexto_vision.md). La validación del entorno del desarrollador se registra separadamente en `docs/validacion_tecnica.md`.

## Hito 2 - Detección de personas

Desde esta carpeta y con el entorno existente:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip check
python -m src.diagnostics
python -m unittest discover -s tests -v
python -m compileall src tests
python -m src.main
python -m src.detect
```

Cierra el preview antes de ejecutar detección. `python -m src.main` sigue siendo la prueba de cámara **sin IA**. `python -m src.detect` muestra cajas `person`, confianza y métricas. Enfoca la ventana y cierra con `q` o `ESC`; también admite la X y Ctrl+C. Después comprueba que `src.main` pueda usar inmediatamente la cámara.

La primera ejecución de detección descarga **yolo26n.pt** mediante la API oficial de Ultralytics si falta. El checkpoint queda en la raíz de este módulo y no se versiona ni viene en el ZIP. Necesitas Internet para esa descarga y para instalar dependencias. Una vez descargado, se reutiliza localmente. La aplicación entrega a YOLO el frame ya capturado por `camera.py`; no entrega índices/URLs a YOLO ni abre una segunda captura. La carga sucede una vez por ejecución, dentro de la sesión de cámara para garantizar su liberación ante errores.

La primera importación de PyTorch, descarga, carga y primera inferencia pueden tardar. La consola distingue carga e inicialización; los FPS se empiezan a medir después de esa primera inferencia.

Edita `config/detection.json` con la aplicación cerrada:

```json
{
  "model": "yolo26n.pt",
  "confidence_threshold": 0.25,
  "iou_threshold": 0.70,
  "image_size": 640,
  "device": "cpu",
  "person_class_id": 0,
  "show_confidence": true
}
```

| Parámetro | Significado y validación |
| --- | --- |
| `model` | Este hito acepta exclusivamente el checkpoint oficial `yolo26n.pt`, relativo a la raíz del módulo. |
| `confidence_threshold` | Número finito entre 0 y 1. Umbral inicial 0.25; subirlo puede reducir falsos positivos y perder personas difíciles. No es el valor definitivo ni una exactitud garantizada. |
| `iou_threshold` | Número finito entre 0 y 1; umbral de solapamiento para NMS en la ruta estándar del modelo. |
| `image_size` | Entero positivo. Tamaño de inferencia solicitado; Ultralytics puede ajustarlo al stride. No cambia la resolución de captura. |
| `device` | `cpu` únicamente para este baseline reproducible. CUDA disponible en diagnóstico no cambia la selección. |
| `person_class_id` | Entero no negativo; para este checkpoint debe ser 0. Se comprueba que la clase 0 y la seleccionada sean `person`. |
| `show_confidence` | Booleano true/false. Controla el número junto a la caja. |

Los siete campos son obligatorios; se rechazan campos extra, NaN, infinito y booleanos usados como números. Las rutas de configuración/pesos dependen de la ubicación del módulo, no del directorio de trabajo.

La ventana muestra resolución real del frame, cámara/backend, modelo/dispositivo, **personas en ese frame**, FPS del pipeline e inferencia en ms. Personas/frame no son entradas, salidas ni personas únicas. `FPS pipeline` incluye el ciclo de lectura, inferencia y visualización entre frames; aparece `midiendo` al inicio. `Inferencia` usa `Results.speed['inference']` y muestra `N/D` si no se informa. No equivale a tiempo total por frame ni a latencia desde el sensor/DroidCam. El FPS reportado por el controlador en consola no es una medición del sensor. No se exige 30 FPS.

Privacidad: inferencia en memoria con `save=False`, `save_txt=False`, `save_conf=False`, `save_crop=False`, `show=False` y `visualize=False`. No hay archivos de imágenes/videos/labels, audio, identificación, tracking ni servicios externos. Se desactivan telemetría y auto-instalación de Ultralytics; `.ultralytics/` puede contener ajustes técnicos locales, nunca capturas. `ultralytics-platform` puede instalarse como dependencia transitiva del paquete solicitado; la aplicación no usa ese servicio ni requiere claves. DroidCam proporciona la cámara virtual por Wi-Fi: ese enlace previo es distinto del procesamiento local del módulo, que no retransmite frames.

### Problemas frecuentes de detección

- Dependencia ausente o DLL: confirma `.venv`, usa `python -m pip install -r requirements.txt` y `python -m pip check`; conserva el mensaje completo. No instales headless junto a OpenCV GUI.
- `diagnostics` tarda al inicio: importa las bibliotecas IA para verificar su carga, sin pesos ni inferencia. Si falla alguna, informa el detalle y sigue verificando el resto y la cámara.
- Fallo de descarga/carga: verifica conexión en el primer inicio y permisos de escritura en el proyecto. No sustituyas el checkpoint por uno no oficial. Si sospechas descarga incompleta, con la app cerrada elimina solo `yolo26n.pt` y reintenta.
- Clase incorrecta: restaura `person_class_id: 0` y verifica los pesos oficiales. No se continúa silenciosamente con otra clase.
- Primera imagen lenta: separa inicialización del rendimiento posterior. Mide durante al menos 60 s.
- FPS bajo: registra CPU y métricas, prueba `image_size: 320` y compara detección; no confundas tamaño de inferencia con resolución de cámara.
- Falsos positivos/negativos: mejora iluminación y encuadre, registra distancia/orientación y ajusta el umbral gradualmente. Una detección parcial no garantiza un futuro cruce válido.
- Aviso de DSHOW seguido de MSMF: conserva el comportamiento de fallback del Hito 1. Puedes elegir `msmf` en `camera.json` si ya está comprobado en ese equipo.

Procedimiento y fundamentos: [docs/02_deteccion_personas.md](docs/02_deteccion_personas.md). Pruebas físicas A–Q: [docs/resultados_pruebas.md](docs/resultados_pruebas.md). Validaciones ejecutadas y límites: [docs/validacion_tecnica.md](docs/validacion_tecnica.md).

Ultralytics es una dependencia externa del prototipo académico. No se cambia la licencia del repositorio; cualquier despliegue comercial futuro requiere revisar sus [condiciones vigentes](https://www.ultralytics.com/license).

Reporte de esta entrega: [REPORTE_HITO2.md](REPORTE_HITO2.md).
