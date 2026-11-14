# Selección de recursos y pesos del lanzador — revisión vigente

## Causa y alcance

El default anterior de `--weights-dir` era PROJECT_ROOT: el worktree nuevo no
contiene yolo26n.pt. El archivo estaba en el módulo del repositorio original.
Se corrige la resolución en el lanzador, sin copiar pesos, descargar modelos,
modificar detection.json ni cambiar inferencia, conteo, calibración, sondeo de cámara,
FIFO o cadencia.

Archivos ajustados: `src/launcher.py`, `src/launcher_ui.py`, `tests/test_launcher.py`,
`tests/validate_launcher_local.py`; nuevo auxiliar `src/launcher_resources.py`.
README y las guías enlazan esta revisión.

## Preferencias y pesos

Preferencias locales no versionadas: `%LOCALAPPDATA%\LimpIA\launcher.json` en Windows.
En otros sistemas, fallback `~/.local/share/LimpIA/launcher.json`. La escritura es
atómica mediante temporal propio y reemplazo del JSON de preferencias; no escribe
configuración personal versionada ni toca modelos o perfiles.

Se guardan última carpeta válida de pesos, dispositivo del lanzador, video, perfil
y directorios de perfiles utilizados. Una cancelación previa a completar las
validaciones no sustituye la última selección válida. La validez de carpeta requiere
`yolo26n.pt` existente y no vacío; la carga del checkpoint sigue siendo responsabilidad
del pipeline existente. No se carga un detector adicional para validar la carpeta.

Prioridad de pesos: CLI explícita (se respeta incluso si necesita corrección),
LIMPIA_WEIGHTS_DIR válido, preferencia válida, raíces conocidas válidas. La raíz
original se obtiene por el directorio Git común y la ruta relativa del módulo,
sin codificar nombres de usuario ni rutas personales. Git es opcional: el EXE
puede usar preferencias y raíces externas sin Git. Si no hay pesos disponibles,
Preparar sesión permite buscar otra carpeta; Iniciar muestra el error y mantiene
la ventana abierta hasta corregirlo o cancelar. No hay descargas automáticas.

## Catálogos acotados

Raíces: módulo actual, `resource_roots` configurados en preferencias, última carpeta
de pesos, `LIMPIA_RESOURCES_DIR` y módulo equivalente del repositorio Git original,
si existe. No se recorre el disco ni se enumeran otros worktrees indiscriminadamente.

Videos: solo `videos_testing`, hasta tres niveles de subcarpetas. Exploración
ordenada, máximo 64 directorios, 256 entradas por directorio y 500 archivos por raíz;
se ignoran enlaces y directorios de entornos, backups, respaldos y runs. Se eliminan
rutas duplicadas, se distingue el nombre con su carpeta y se prioriza el último video
si sigue disponible. Al seleccionarlo se valida lectura OpenCV real. El catálogo
se calcula fuera del hilo gráfico. Siempre existe Buscar otro archivo, incluso
con catálogo vacío. `--video` evita el selector.

Perfiles: `config/baselines`, `config/zones`, `results_testing` de raíces conocidas
y directorios de perfiles usados/configurados. Se descartan archivos grandes,
JSON no geométricos e incompatibles; el resultado muestra nombre y procedencia.
El hash del video se calcula para prefiltrar antes de validar candidatos mediante
el cargador existente. Se verifican esquema, polígonos, hash de video e integridad
del perfil y dimensiones. No se intercambian hashes de video_03 y video_03_original.

El último JSON se prioriza solo si vuelve a superar compatibilidad. Un único
candidato se informa y aparece como acción predeterminada. Siempre se ofrecen
Buscar otro JSON y Calibrar nuevas zonas; cámara también ofrece Solo tracking.
Si un JSON externo elegido en la interfaz es inválido, se permite corregirlo sin
reiniciar el flujo ni volver a sondear la cámara. Los errores de rutas explícitas
por CLI se comunican sin sustituir silenciosamente esos parámetros.

En cámara se filtra índice/resolución, y se conserva la confirmación obligatoria de
encuadre antes de contar. Un candidato recordado no acredita posición ni precisión.
El sondeo de dispositivos permanece exactamente igual a la versión validada.

## Dispositivo y Preparar sesión

Prioridad: `--device` explícito; preferencia del lanzador; preferencia local existente;
inventario real. Sin preferencia se prefiere cuda:0 si está disponible y supera
la validación real; de lo contrario se ofrece la selección de dispositivos.
CPU sigue disponible. Si falla el elegido, se informa y requiere otra selección:
no hay fallback silencioso ni cambios de Torch/CUDA o del baseline CPU.

Preparar sesión conserva el diseño y muestra fuente seleccionada, perfil, tracker,
dispositivo, carpeta de pesos e Iniciar. La selección se aplica al lanzador y no
modifica `config/detection.json` ni `config/device.local.json`.

## Uso

Desde el módulo, utilizando el entorno Python existente:

```powershell
python ejecutable.py --mp4
python ejecutable.py --camara
python ejecutable.py --mp4 --video "RUTA_VIDEO.mp4" --zones "RUTA_PERFIL.json"
python ejecutable.py --mp4 --video "RUTA_VIDEO.mp4" --zones "RUTA_PERFIL.json" --device cpu --weights-dir "RUTA_MODELOS"
```

Para una raíz externa opcional:

```powershell
$env:LIMPIA_RESOURCES_DIR = 'D:\RecursosLimpIA'
python ejecutable.py --mp4
```

Los comandos de calibración de LAUNCHER.md siguen vigentes. No se introducen nuevos
parámetros de tracking, conteo o velocidad.

## Comprobaciones realizadas

- Desde otro CWD (`Downloads`), encontró automáticamente el módulo original con
  pesos y descubrió **13 MP4**. La búsqueda no depende del directorio de ejecución.
- En recursos reales: **1 perfil compatible** para video_03.mp4 acelerado y **0**
  para video_03_original.mp4. No se reutilizó sala_v4 para el original.
- Arranque real sin `--weights-dir` ni `--device`: encontró el modelo externo,
  eligió **cuda:0**, hizo nueva inferencia local, procesó **65 frames** y mostró
  **60 consecutivos**, sin errores. Reporte: `logs/launcher-resources-real-start.json`.
- No se repitió innecesariamente el MP4 completo: esta revisión solo altera selección
  y preferencias. El pipeline no cambió; su aceptación integral previa de **21 IN /
  20 OUT, 5.732 frames** está en LAUNCHER.md y `logs/launcher-real-mp4.json`.
  La prueba nueva parcial no se presenta como otra comprobación integral de 21/20.

Empaquetado: el auxiliar se importa estáticamente y usa PROJECT_ROOT relativo al
módulo, APPDATA externo y Git opcional. No precisa rutas personales dentro del código.
Esta es compatibilidad prevista de rutas; **no se afirma un EXE validado**: PyInstaller
sigue ausente y las pruebas de binario de LAUNCHER.md permanecen pendientes.
No se instalaron paquetes ni se modificó el entorno estable.

## Regresiones definitivas

Tres procesos independientes después del último ajuste funcional:

| Ejecución | Resultado | Duración |
| --- | --- | --- |
| 1 | 659 pruebas, OK; 3 omisiones heredadas | 25,197 s |
| 2 | 659 pruebas, OK; 3 omisiones heredadas | 25,015 s |
| 3 | 659 pruebas, OK; 3 omisiones heredadas | 25,172 s |

Logs: `logs/launcher-resources-final-v4-1.txt`, `-2.txt`, `-3.txt` y
`logs/launcher-resources-final-v4.json`. Las omisiones siguen siendo las integraciones
heredadas que esperan pesos dentro del worktree y el caso de symlinks Windows;
no se cuentan como aprobadas. Los tests de preferencias usan APPDATA temporal y
no modifican las preferencias reales del usuario.

La regresión conserva CLI, archivos externos, cancelación, cámaras sin conteo,
calibración y exportación, además de catálogo vacío, deduplicación, último video,
JSON compatible por hash y dimensiones, pesos externos/persistencia, prioridad
CUDA y CPU explícita y recuperación de JSON inválido.

`pip check` sin requisitos rotos; `git diff --check` sin errores. Sin cambios en
sondeo de cámara, motor/trackers, visualizadores, cadencia, perfiles congelados,
videos, pesos, detection.json u otras ramas. Sin commit, push, merge ni PR.
La ejecución de un EXE y la calibración física definitiva de conteo en cámara
continúan pendientes, tal como se documentó en LAUNCHER.md.
