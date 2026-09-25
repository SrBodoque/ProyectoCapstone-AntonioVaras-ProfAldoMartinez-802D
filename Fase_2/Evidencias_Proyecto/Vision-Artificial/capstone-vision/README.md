# capstone-vision — Hito 1

Módulo de visión del sistema inteligente de gestión de limpieza de servicios higiénicos basado en demanda real, proyecto CAPSTONE de Ingeniería en Informática, Duoc UC.

Este hito prepara el proyecto y permite diagnosticar y visualizar una webcam local. No detecta ni identifica personas. No graba, guarda ni transmite imágenes, video o audio. El siguiente hito requiere aprobación explícita después de las pruebas físicas.

## Requisitos y versiones

- Windows 10/11 de 64 bits, webcam y sesión de escritorio.
- Visual Studio Code y PowerShell.
- **Python 3.13.15 x64**, instalación convencional, sin modo experimental free-threaded.
- **opencv-python==4.14.0.94**, única dependencia directa. Incluye interfaz gráfica; no instalar el paquete headless ni otras variantes de OpenCV conjuntamente.
- Internet solamente para descargar herramientas/dependencias. La aplicación no necesita red.

Descarga Python desde su [página oficial de versión](https://www.python.org/downloads/release/python-31315/), opción Windows installer (64-bit). Habilita su incorporación a PATH durante la instalación y abre una terminal nueva. OpenCV está fijado según su [distribución en PyPI](https://pypi.org/project/opencv-python/4.14.0.94/). No cambies versiones ante un error sin registrar y revisar primero la causa.

## Instalación desde cero en PowerShell

Extrae el ZIP. En VS Code, usa **Archivo > Abrir carpeta** y selecciona la carpeta que contiene este README, `requirements.txt` y `src`. Abre **Terminal > Nueva terminal**, perfil PowerShell. Todos los comandos siguientes se ejecutan desde esa raíz.

```version pyhton
Para confirmar que version de python hay:
py --version 

Para verificar que existe 3.13.15 en el paquete para instalarlo
winget show --id Python.Python.3.13 --versions 

Si 3.13.15 no aparece, entonces no debes ejecutar ese comando con --version 3.13.15, 
porque Winget no tiene esa versión disponible en ese paquete.

si aparece, instálala con Winget; si no aparece, usa el instalador oficial

So aparece la version en el paquete, insatalar:

winget install --id Python.Python.3.13 --version 3.13.15 -e --scope user

Para confirmar que es la version correcta
py -3.13 --version



------------------------------------------------------------------
```powershell
Get-Location
Get-ChildItem
python --version
python -c "import struct; print(struct.calcsize('P') * 8)"
```
------------------------------------------------------------------

Debe mostrar `Python 3.13.15` y `64`. Si aparece otra versión, detente antes de crear el entorno. Comprueba `Get-Command python` y, si tienes el lanzador de Python, `py -3.13 --version`. Solo si este último indica exactamente 3.13.15 puedes usar `py -3.13 -m venv .venv` en lugar del primer comando siguiente. Si Python abre Microsoft Store, revisa instalación, PATH y alias de ejecución de Windows.

```powershell
Primero ingresar a la carpeta del proyecto HigieneSmart


python -m venv .venv "si da error usar: py -3.13 -m venv .venv"
.\.venv\Scripts\Activate.ps1
python --version
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
```

Ejecuta una línea a la vez. Si falla una, registra el error y no continúes como si hubiese pasado. No copies entornos virtuales entre computadores: el ZIP no incluye `.venv`.

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

Usa ejecución como módulo **desde la raíz**, no `python src/main.py` ni el botón que ejecuta el archivo suelto. `diagnostics` sin `--scan` no abre la cámara. Con `--scan` prueba 0 a 4, lee un frame por intento exitoso y libera inmediatamente cada cámara antes de pasar a la siguiente. Puede encender su indicador luminoso; no guarda esos frames. Índices ausentes generan avisos y no abortan todo el diagnóstico. Un escaneo sin cámaras devuelve 0 porque completó el diagnóstico, no porque haya aprobado la webcam.

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

El repositorio local se inicializó en el workspace sin remoto ni push. El ZIP no incluye metadatos `.git`; puedes inicializarlos en tu copia:

```powershell
git init
git status --short --untracked-files=all
```

`.venv`, cachés y logs se ignoran; documentación y configuración se conservan. No se ha agregado una licencia. `logs/` está reservado: actualmente solo hay mensajes técnicos de consola, no archivos de log.

`src/config.py` valida configuración; `camera.py` gestiona capturas; `main.py` presenta video; `diagnostics.py` inspecciona el entorno. `tests/` usa solo `unittest` y dobles de prueba para errores y liberación de recursos: no demuestra funcionamiento físico de la cámara.

Completa [las pruebas de aceptación](docs/resultados_pruebas.md). Consulta [el procedimiento detallado](docs/01_entorno_y_webcam.md) y [el contexto](docs/00_contexto_vision.md). La validación del entorno del desarrollador se registra separadamente en `docs/validacion_tecnica.md`. No avances al siguiente hito sin aprobación explícita.
