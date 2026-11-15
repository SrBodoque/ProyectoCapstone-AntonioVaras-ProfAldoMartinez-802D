# LimpIA — lanzador unificado

Implementación del 14 de noviembre de 2026 en `feature/visualizador-presentacion`.
El lanzador coordina los módulos existentes: no sustituye el visualizador profesional,
la presentación FIFO, YOLO, trackers, contador ni calibrador MP4 estable.

## Inicio

Desde `capstone-vision`, con el entorno existente activo:

```powershell
python ejecutable.py
python ejecutable.py --mp4
python ejecutable.py --camara
python ejecutable.py --calibrar --mp4
python ejecutable.py --calibrar --camara
python ejecutable.py --help
```

Sin argumentos: Abrir video, Abrir cámara, Calibrar zonas y Salir. Con un origen
explícito se omite el menú inicial. Cancelar un diálogo vuelve al menú si se inició
allí; desde un comando directo termina limpiamente. Al cerrar una sesión abierta
desde el menú se regresa al selector. Un fallo de cámara permite reintentar,
selección manual, cambiar a MP4 o cancelar; un fallo del visualizador regresa al menú
tras cerrar su ventana, sin matar abruptamente el proceso.

Preparación exacta para este equipo, sin reinstalar ni copiar pesos:

```powershell
$original = 'C:\Users\juanc\Downloads\ProyectoCapstone-AntonioVaras-ProfAldoMartinez-802D\Fase_2\Evidencias_Proyecto\Vision-Artificial\capstone-vision'
$python = Join-Path $original '.venv\Scripts\python.exe'
Set-Location 'C:\Users\juanc\Downloads\LimpIA-visualizador-presentacion\Fase_2\Evidencias_Proyecto\Vision-Artificial\capstone-vision'
& $python ejecutable.py --mp4
```

Si la política de PowerShell no permite activar un entorno, usar su `python.exe`
explícitamente como arriba, sin cambiar políticas del sistema.

## Videos y perfiles

`--mp4` abre un selector nativo de MP4. Se comprueba existencia, formato y lectura
de un frame real antes de continuar. Después se elige JSON existente o calibración
nueva. No se aplica sala_v4 por defecto a otra grabación.

Ejemplo sin diálogos de rutas ni ajustes, con nueva inferencia:

```powershell
& $python ejecutable.py --mp4 `
  --video "$original\videos_testing\nuevo_angulo\video_03.mp4" `
  --zones config/baselines/sala_v4.json --tracker bytetrack `
  --device cuda:0 --weights-dir "$original"
```

Cuando se selecciona un perfil mediante diálogos aparece una revisión antes de
iniciar. La pantalla muestra nombre del perfil, tracker, dispositivo y carpeta de
pesos; permite ByteTrack (predeterminado) o BoT-SORT sin ReID y CPU/CUDA disponibles.
Los argumentos completamente especificados evitan esa revisión redundante.

Los perfiles MP4 se validan por esquema, geometría, dimensiones y hash del video.
Los de cámara, por esquema, polígonos, índice y resolución; además se exige confirmar
el encuadre y orientación A exterior / B puerta. Igual resolución no prueba igual
posición: no se certifica precisión física por esa comprobación básica.

Se reutiliza la preferencia CPU/GPU existente si es válida; si no puede utilizarse,
se informa y se ofrece selección explícita. No hay fallback silencioso. Dispositivo,
tracker y carpeta de pesos elegidos se conservan en memoria al volver al menú, sin
escribir preferencias personales. `--device cpu`, `--device cuda:0`, `--tracker botsort`
y `--weights-dir RUTA` están disponibles. Opcionalmente se puede definir
`LIMPIA_WEIGHTS_DIR` para la carpeta inicial de pesos. No se descargan modelos.

## Selección de cámara

```powershell
& $python ejecutable.py --camara
& $python ejecutable.py --camara --camera-index 0
& $python ejecutable.py --camara --camera-index 0 --tracking-only `
  --tracker bytetrack --device cuda:0 --weights-dir "$original"
```

MSMF es el backend inicial en Windows. `--camera-backend` admite los backends del
proyecto; la selección manual ofrece los correspondientes al sistema operativo.

Se prueban por defecto índices 0–4. `--camera-limit N` acepta 1–16; cada dispositivo
tiene `--probe-timeout SEGUNDOS` (4 por defecto, 0,1–30 permitidos). El escaneo corre
fuera del hilo Tk, con progreso y cancelación. Cada prueba se realiza en un proceso
hijo propio; si el driver queda bloqueado, solo se termina ese hijo. Los intentos
se liberan antes de devolver metadatos. Se requiere un frame BGR válido: isOpened
no basta. No se solicita cambiar FPS durante el sondeo.

Una sola cámara se elige automáticamente y se informa índice/backend/resolución;
varias muestran selector; ninguna ofrece reintentar, índice/backend manual, MP4
o cancelar. Un índice por CLI se respeta y se prueba una sola vez antes de ofrecer
alternativas. Se reutilizan AvailableCamera y la captura nativa del visualizador.
El scanner histórico tiene rango fijo y no tiene timeout; permanece intacto.

El sondeo termina su apertura antes de iniciar la sesión. Abrir de nuevo al entrar
en preview o visualizador es deliberado y secuencial: no se conservan dos capturas
simultáneas ni se promete reservar el dispositivo frente a otras aplicaciones.

Si no hay perfil compatible, seleccionar **Solo tracking**. El conteo aparece
deshabilitado. El parser interno del visualizador conserva su ruta predeterminada
de zonas, pero esa ruta se IGNORA en tracking-only; no se aplica sala_v4 a la webcam.
Con perfil válido, se usa el mismo contador A/B existente tras confirmar encuadre.

## Calibración MP4

```powershell
& $python ejecutable.py --calibrar --mp4
& $python ejecutable.py --calibrar --mp4 --video 'RUTA.mp4' `
  --frame 0 --output 'PERFIL_NUEVO.json' --reviewer 'Responsable'
```

Seleccionar video, elegir si se dibuja desde cero o se modifica un JSON existente,
elegir salida nueva, responsable y frame de referencia (0 por defecto). Para dar
una base directamente se admite `--zones PERFIL_EXISTENTE.json`.

Se reutilizan `reference_frame`, `edit_frame` y `export_video_zones` del calibrador
MP4 existente. Controles: A/B elige zona; clic izquierdo agrega/arrastra vértices;
Enter o clic derecho cierra el polígono; S guarda (nombre del perfil); Q/Esc sale.
Al salir se exporta el JSON vinculado al hash de video y se ofrece iniciar con él.
Si cambia el MP4 mientras se editan las zonas se rechaza la exportación, como en
el flujo estable. Editar una base no modifica su archivo original.

## Calibración de cámara

```powershell
& $python ejecutable.py --calibrar --camara
& $python ejecutable.py --calibrar --camara --camera-index 0
```

Tras seleccionar cámara, base opcional, archivo nuevo y responsable, se abre preview.
**Espacio** captura un frame en memoria; Esc/Q cancela. Se libera la cámara antes
de abrir el editor sobre la imagen congelada. El adaptador reutiliza CalibrationEditor,
preview_size, render_editor y ZoneStore, conservando el índice real del dispositivo;
no crea un MP4 temporal ni duplica algoritmos geométricos.

Dibujar A exterior y B puerta, guardar con S y cerrar con Q. Se exporta un ZoneProfile
compatible con el contador y un archivo `NOMBRE.provenance.json` con procedencia,
resolución, responsable, orientación y advertencia de encuadre. El esquema principal
no admite campos adicionales; por eso la procedencia va en un sidecar. Este sidecar
no es un perfil seleccionable para el contador. No se guarda la imagen capturada.

El perfil solo sirve mientras permanezcan posición, orientación y geometría. El
sidecar registra `physical_count_validated: false`: calibrar un frame no acredita
conteo correcto sobre personas. La validación definitiva se hará en la sala instalada.
Al guardar se ofrece usar el perfil; antes de contar se confirma el encuadre.

Se exigen archivos nuevos: no se sobrescribe ningún JSON, incluso si es experimental.
Las salidas dentro de un directorio llamado `baselines` se rechazan. Se validan todos
los perfiles generados antes de usarlos. Cancelar no toca perfiles anteriores.

## Arquitectura y archivos de esta tarea

| Archivo nuevo | Función |
| --- | --- |
| ejecutable.py | Entrada Python/futura entrada EXE; freeze_support antes de analizar CLI |
| src/launcher.py | Argumentos, coordinación, validación y opciones para el visualizador |
| src/launcher_ui.py | Menú pequeño, diálogos, revisión y tareas sin bloquear Tk |
| src/launcher_probe.py | Sondeos nativos acotados y liberación de procesos/cámaras |
| src/launcher_calibration.py | Captura congelada, adaptadores del editor y exportación exclusiva |
| packaging/LimpIA.spec | Candidato onedir con lista explícita de configuraciones públicas |
| packaging/build_limpia.py | Constructor reproducible principal; preflight sin instalaciones |
| packaging/build_limpia.ps1 | Variante PowerShell sujeta a la política de firma del equipo |
| tests/test_launcher.py | 33 pruebas nuevas de CLI, selección, errores, geometría y recursos |
| tests/validate_launcher_local.py | Aceptación opt-in con ventana e inferencia reales |
| tests/check_launcher_cameras.py | Sondeo físico acotado, solo metadatos |
| LAUNCHER.md | Esta guía |

Único archivo previo editado en esta tarea: README, para enlazar esta guía.
`src.view_presentation`, `src.view_count_results`, `src.presentation_*`, calibrador
MP4, cámara histórica, detector, trackers, motor A/B y configuraciones permanecen
intactos. Se registran errores técnicos en `logs/launcher/UUID.log`, separados del menú.

## Estado real del EXE

**No se construyó ni se considera validado LimpIA.exe.** PyInstaller no está
instalado. El preflight Python informó esa ausencia y no instaló paquetes. La
variante .ps1 no pudo ejecutarse porque la política del equipo exige firma digital;
no se cambió la política ni se sugiere desactivarla. La entrada Python de construcción
está disponible con el mismo propósito, sujeta a las dependencias de build.

Desde un entorno de build ya preparado y autorizado, compatible con Python 3.13
y las versiones del proyecto, sin reinstalar el entorno estable de H5.2:

```powershell
& 'RUTA_PYTHON_BUILD\python.exe' packaging/build_limpia.py --check
& 'RUTA_PYTHON_BUILD\python.exe' packaging/build_limpia.py
```

El script no instala nada. Si faltan dependencias se detiene. El resultado candidato
se coloca en `logs/packaging/UUID/dist/LimpIA/LimpIA.exe`, fuera del seguimiento Git.
La distribución es onedir: copiar toda la carpeta LimpIA, incluida `_internal`.
Usar una carpeta portátil de usuario con escritura: los módulos existentes escriben
logs/configuración local de Ultralytics relativos a su raíz; no se afirma soporte
para ejecutar desde una carpeta de instalación de solo lectura.

La estructura de datos usa rutas relativas a `__file__`, conservando el mecanismo
del proyecto. El spec solo añade camera/detection/tracking/counting JSON y los YAML
ByteTrack/BoT-SORT sin ReID; excluye videos, resultados, perfiles y pesos del proyecto.
Los pesos se seleccionan externamente mediante el lanzador o `--weights-dir`.
El constructor Python inspecciona el candidato y rechaza pesos/videos/preferencias
privadas antes de recomendar siquiera pruebas de distribución.

Fundamento del formato y rutas: [documentación de spec de PyInstaller](https://pyinstaller.org/en/stable/spec-files.html)
y [resolución de recursos en ejecución](https://pyinstaller.org/en/stable/runtime-information.html).
El spec y el script PowerShell se analizaron sintácticamente; esto no sustituye
construcción ni pruebas en runtime. Se usa freeze_support para los sondeos al congelar.
No hay rutas absolutas del desarrollador dentro del código.

Requisitos pendientes de comprobar con el binario: hooks/DLL de Torch, torchvision,
OpenCV, Tk, Pillow, lap y Ultralytics; CPU/CUDA; driver NVIDIA compatible con la build
CUDA del entorno de construcción; apertura MP4 y cámara; calibraciones; cancelación;
rutas desde dist y liberación. No se descarga CUDA/Torch ni se incorporan modelos.
Un build exitoso no basta: ejecutar esos ensayos antes de distribuir.

## Evidencia de esta tarea

Se completó nueva inferencia integral pasando por Launcher.prepare y la ventana
real existente, sin predicciones guardadas:

- Video de sala, ByteTrack, cuda:0, conf. 0.65, imgsz 640, sala_v4.
- **5.732 frames procesados y dibujados, secuenciales; 21 IN / 20 OUT**.
- Estado Finalizado, sin error; 197,72 s incluyendo arranque de la ventana/modelo.
- Reporte: `logs/launcher-real-mp4.json`.

Hardware real de cámara:

- Escaneo de índices 0–2, MSMF, timeout 4 s; terminó en **1,69 s**.
- Solo índice **0**, **1280×720**, 30 FPS informados por el driver.
- Reporte: `logs/launcher-real-camera-scan.json`.
- Flujo del lanzador con índice explícito: **303 frames inferidos, 299 dibujados**,
  CUDA real, tracking-only, sin error; entradas/salidas deshabilitadas.
- La diferencia incluye warmup, cola cancelada al detener y la política de actualidad
  del modo tracking-only; no se afirma ausencia de muestreo de cámara ni conteo validado.
- Reporte: `logs/launcher-real-camera.json`. Su campo técnico prepared_zones conserva
  el default del parser del visualizador: NO fue aplicado al estar tracking-only activo.

Calibración: exportación JSON, esquema y geometría se comprobaron con frames sintéticos,
dobles de captura y el editor real sobre una base sintética, incluyendo índice de cámara
2 y sidecar. No se inventó una calibración física de la sala. Cancelación de menú y tarea
ocupada se probaron con Tk real. Los mocks de inferencia/captura no se presentan como
precisión física. El sondeo que abre sin frame y el timeout se cubren con dobles.

Comandos reproducibles:

```powershell
& $python -B -m unittest discover -s tests -p test_launcher.py -v
& $python -B -m unittest discover -s tests -v
& $python -B -m pip check
& $python -B tests/validate_launcher_local.py --resources "$original" --report logs/aceptacion-lanzador-nueva.json
& $python -B tests/validate_launcher_local.py --resources "$original" --camera --report logs/camara-lanzador-nueva.json
```

Las rutas de reportes deben ser nuevas. Los resultados de las tres regresiones
finales se detallan a continuación. No hacer commit, push ni PR sin autorización.

### Tres regresiones definitivas

Después del último cambio funcional y de pruebas:

| Proceso independiente | Resultado | Duración unittest |
| --- | --- | --- |
| 1 | 655 pruebas, sin fallos; 3 omisiones heredadas | 24,651 s |
| 2 | 655 pruebas, sin fallos; 3 omisiones heredadas | 24,463 s |
| 3 | 655 pruebas, sin fallos; 3 omisiones heredadas | 24,549 s |

Cada ejecución incluye 33 pruebas nuevas del lanzador y toda la regresión previa.
Los logs finales son `logs/launcher-final-v4-suite-1.txt`, `-2.txt`, `-3.txt` y
`logs/launcher-final-v4-suites.json`. Los intentos anteriores se conservaron y no
se usan para sustituir estas tres ejecuciones posteriores a la última corrección.
No hubo advertencias de destrucción de intérpretes Tk en los tres logs finales.

Omisiones heredadas: integración real ReID que espera pesos detector/clasificador
en la raíz del worktree, integración histórica MP4 que espera el detector allí y
creación de symlinks sin privilegio Windows. No se contaron como aprobadas. La prueba
integral nueva sí utilizó el detector externo configurado y CUDA reales, con 21/20.

`pip check`: No broken requirements found. `git diff --check`: sin errores; diff
preparado vacío. El baseline y su tag continúan apuntando al commit abeb344.
No se hicieron commit, push ni PR. Recomendación: revisar manualmente los diálogos
y realizar la calibración definitiva con la cámara instalada antes de autorizar
commit o certificar el conteo físico. El lanzador Python está implementado; la
construcción y ejecución real de LimpIA.exe permanecen pendientes, diferenciadas
de la preparación del spec y scripts.

Revisión vigente de catálogos, carpeta de pesos persistente y prioridad CUDA:
[LAUNCHER_RESOURCES.md](LAUNCHER_RESOURCES.md).
