# Selección multicámara — Mejora entre H3 y H4

El índice 0 puede representar una cámara diferente en cada computador. Esta mejora permite elegir entre webcam integrada, USB, DroidCam, cámaras virtuales y capturadoras que OpenCV pueda abrir. No presupone marcas ni asigna DroidCam al índice 1. Se procesa **una cámara por ejecución**; no hay captura simultánea.

## Selección al iniciar

Los previews tienen tres modos con el mismo loop OpenCV, sin YOLO ni ByteTrack:

- **AUTO-FIRST — `python -m src.main`:** prueba índices 0–4 en orden y se detiene al primer frame válido. No lista todas las cámaras ni llama a input. Funciona tanto con `camera_index: "auto"` como con un entero; sin CLI ese campo no fija el índice para este comando. Si ninguna funciona, devuelve código 1 y sugiere `python -m src.diagnostics --scan`.
- **FORCED — `python -m src.main --camera N`:** el override tiene prioridad absoluta, abre N sin búsqueda previa y no cambia a otro índice si falla. No modifica el JSON.
- **INTERACTIVE — `python -m src.main_seleccionar_camera`:** fuerza el descubrimiento 0–4 para esa ejecución, aunque el JSON tenga un entero. Usa el resolver existente y después el preview compartido; no escribe el JSON. No acepta `--camera`: para abrir un índice concreto usa `src.main --camera N`.

La precedencia de la tabla siguiente se conserva para **detección y tracking**:

| Prioridad | Configuración | Comportamiento |
| --- | --- | --- |
| 1 | `--camera N` | Abre el índice indicado, sin scan ni selector; no escribe el JSON |
| 2 | `camera_index` entero | Abre ese índice directamente; no cambia de índice si falla |
| 3 | `camera_index: "auto"` | Escanea índices 0–4 una sola vez, antes del procesamiento |

`config/camera.json` trae `"camera_index": "auto"`; conserva 1280×720, 30 FPS y backend `auto`. Se aceptan exactamente `"auto"` o enteros 0–2147483647 (límite existente de OpenCV). Se rechazan booleanos, negativos, decimales, `"0"`, `"AUTO"` y `null`. El archivo completo se valida incluso si se usa un override: `--camera` no oculta un JSON inválido.

En INTERACTIVE (y en auto de detect/track), cero cámaras produce un error con recomendaciones y código 1; una se selecciona sin solicitar entrada; varias muestran un selector por **índice real**, no por posición en la lista. Por ejemplo, con índices 0 y 2, introducir 1 es inválido. Una entrada incorrecta vuelve a preguntar sin reescanear. `q` cancela limpiamente (código 0); Ctrl+C también cierra y libera recursos. Sin consola interactiva o ante EOF se termina con código 1. Para preview directo utiliza `python -m src.main --camera N`; detect/track mantienen el override o índice fijo del JSON. Argumentos CLI inválidos terminan con código 2 y ayuda de uso.

No se implementa `r`: para conectar o activar otra cámara, cancela y vuelve a ejecutar. Los nombres son genéricos (`Cámara 0`, etc.). Se muestra el tamaño real del primer frame, backend informado y FPS reportados por el driver; estos FPS no son una medición de rendimiento. Propiedades ausentes se muestran como desconocidas/no informadas.

## Comandos

Desde la raíz, con el entorno virtual activado:

```powershell
python -m src.main  # Primera funcional, sin preguntar ni editar el JSON
python -m src.main_seleccionar_camera
python -m src.detect
python -m src.track

python -m src.main --camera 1
python -m src.detect --camera 1
python -m src.track --camera 1

python -m src.diagnostics
python -m src.diagnostics --scan

python -m compileall src tests
python -m unittest discover -s tests -v
python -m pip check
```

El índice 1 es solo un ejemplo: usa el disponible en tu equipo. Para fijar el preview usa `src.main --camera N`; en detect/track también puedes fijar un entero en `config/camera.json`. Para seleccionar en preview ejecuta `src.main_seleccionar_camera`; para volver al auto de detect/track restaura `"auto"`. El JSON adjunto se conserva en `"auto"` y `src.main` funciona sin cambios de configuración. `--help` está disponible en los cuatro comandos.

`diagnostics` sin `--scan` no abre cámaras. Con `--scan` utiliza el mismo descubrimiento 0–4, informa resultados y termina **sin selector**, incluso con varias cámaras. Conserva los diagnósticos de entorno, dependencias, detección y tracking. Un scan completado sin dispositivos puede devolver 0 si el resto del diagnóstico está correcto; esto no certifica disponibilidad de hardware.

## Implementación y recursos

`camera.py` concentra `probe_camera`, `find_first_available_camera`, `discover_cameras`, `select_camera` y `resolve_camera_config`. `camera_cli.py` comparte argparse sin importar OpenCV o IA. `src.main` sin CLI llama a `find_first_available_camera`, que reutiliza `probe_camera` y retorna en el primer éxito sin recorrer los índices restantes. Con CLI no llama a ninguna búsqueda. El entrypoint INTERACTIVE conserva el resolver con una copia temporal en auto y delega en `src.main.run_preview`; existe un único loop de preview que recibe el índice ya resuelto. Detect/track conservan su resolución previa a la sesión. Los loops de frames permanecen intactos: H1 es preview OpenCV; H2 usa YOLO sin IDs; H3 usa YOLO + ByteTrack con IDs temporales.

Cada sondeo reutiliza `camera_session` / `open_camera`: abrir, comprobar estado, solicitar propiedades, leer un primer frame válido y liberar. Un fallo de backend libera su captura antes del siguiente intento. En Windows se conserva DSHOW → MSMF → CAP_ANY; Linux conserva V4L2 → CAP_ANY; macOS conserva AVFoundation → CAP_ANY. Un backend explícito conserva su política anterior.

Se devuelve solo metadata: ninguna captura queda abierta al mostrar el selector, y el frame de sondeo se descarta sin inferencia, guardado ni envío. La cámara seleccionada se vuelve a abrir para la sesión normal, con la misma política de backends. Si ya no está disponible, se informa el fallo del índice elegido; no se elige otra cámara silenciosamente. El cierre de la sesión conserva la liberación mediante `finally`, incluso con errores o Ctrl+C.

La búsqueda añade tiempo al arranque: AUTO-FIRST solo sondea hasta el primer éxito; INTERACTIVE recorre el rango completo y puede encender brevemente los indicadores de varias cámaras. En AUTO-FIRST el sondeo exitoso también se libera antes de reabrir esa cámara para el preview. Si falla la reapertura, se informa el error sin reiniciar la búsqueda. No existe scan dentro de los loops ni trabajo adicional de selección por frame. No se realizó un benchmark de FPS físicos: debe compararse en el equipo y escena del usuario.

## Privacidad y limitaciones

- No se añaden dependencias, reconocimiento facial, ReID, grabaciones, capturas, audio ni envío de imágenes. Los IDs de H3 siguen siendo temporales.
- Los índices pueden variar con equipo, dispositivos, reinicios, drivers y backend. No constituyen identidades persistentes ni perfiles de calibración.
- Hay como máximo un candidato por índice: un éxito detiene el fallback de ese índice. OpenCV no proporciona aquí una identidad física fiable para eliminar alias del mismo dispositivo bajo índices distintos; no se deduplican por resolución porque dos cámaras reales pueden compartirla.
- El scan solo cubre 0–4. Un índice superior conocido puede abrirse con CLI; detect/track también admiten JSON fijo.
- La comprobación exige un frame válido; no identifica si la imagen de una cámara virtual está actualizada, congelada o es un cartel del driver. Tampoco garantiza que siga disponible después del scan.
- La reapertura conserva la política de backends, sin fijar el backend que funcionó durante el sondeo. Si cambian dispositivos o drivers entre ambas operaciones, la correspondencia física del índice puede cambiar. Reinicia y verifica la vista antes de usarla.
- Las llamadas nativas del driver pueden tardar o bloquearse; no se promete un timeout universal. Si un driver se queda bloqueado, puede ser necesario cerrar el proceso o corregirlo. Algunos avisos nativos de OpenCV aparecen en stderr aunque Python controle el error sin traceback.
- En Linux sin escritorio se conserva el error de sesión gráfica antes de intentar el preview. Diagnóstico y tests funcionan sin ventanas. Para INTERACTIVE usa una terminal interactiva (por ejemplo PowerShell). AUTO-FIRST y FORCED no necesitan stdin; sí necesitan escritorio para el preview.
- Windows, Python 3.13.15, DroidCam y webcams reales requieren validación física. La corrección AUTO-FIRST añade AF-01–AF-08 en [resultados](resultados_pruebas.md). Los registros MC/CAM anteriores conservan su contexto histórico; en particular, la antigua exigencia de entero para src.main ya no aplica. No se han aprobado las pruebas físicas AF desde el servidor de desarrollo.

El siguiente hito sigue siendo **Hito 4 — Calibración espacial**. No se implementan zonas, línea, IN/OUT ni perfiles por cámara en esta mejora.
