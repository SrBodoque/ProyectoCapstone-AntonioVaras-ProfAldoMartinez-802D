# Validación técnica del desarrollador — 17 de septiembre de 2026

## Estado y límites

HITO 1 IMPLEMENTADO. Validación técnica realizada en Linux x86_64 con Python 3.12.14, no con el Python objetivo. Pendiente ejecutar en Windows 10/11 con Python 3.13.15 x64 y webcam física. No se aprueba todavía el hito ni se declara validada la estabilidad del hardware.

Instalación en .venv limpio: opencv-python 4.14.0.94 (cv2 4.14.0), NumPy 2.5.3 resuelto por pip, pip 25.0.1. No se cambió la versión objetivo del proyecto. No se instaló manualmente NumPy ni se usaron paquetes globales.

## Comprobaciones realizadas

Los comandos Linux se ejecutaron desde la raíz, usando `.venv/bin/python` donde se indica `python` en esta tabla. La creación del venv usó el Python disponible del entorno.

| Comando o prueba | Resultado |
| --- | --- |
| `python --version` / `git --version` | OK: Python 3.12.14; Git 2.51.1. Objetivo 3.13.15 pendiente en Windows. |
| `python -m venv .venv` | OK: entorno aislado creado. |
| `python -m pip install -r requirements.txt` | OK: OpenCV y su dependencia transitiva instalados. |
| `python -m pip list` | OK: pip 25.0.1, opencv-python 4.14.0.94, numpy 2.5.3. |
| `python -m pip check` | OK: No broken requirements found. |
| `python -m compileall src tests` | OK: sintaxis válida. |
| `python -c "import src.config, src.camera, src.main, src.diagnostics; print('Imports OK')"` | OK: los cuatro módulos se importan sin abrir hardware. |
| `python -m unittest discover -s tests -v` | OK: primera pasada 15 pruebas; después de revisar, suite final de 16 pruebas aprobada. |
| `python -m src.diagnostics` | OK: información y configuración correctas; advertencia explícita sobre versión Python diferente. |
| `python -m src.diagnostics --scan` | OK del diagnóstico: ningún dispositivo entre 0 y 4. PENDIENTE POR HARDWARE para disponibilidad real. |
| `python -m src.main` | OK del manejo de error: código 1 y explicación de ausencia de sesión gráfica. Preview físico PENDIENTE POR HARDWARE. |
| Llamada a `main()` con DISPLAY temporal simulado | OK: cámaras realmente ausentes, mensaje comprensible, retorno 1; sin crear ventana. Solo se permitió llegar al intento de captura, no se simuló una webcam real. |
| Descarga pip con `--platform win_amd64 --python-version 3.13 --only-binary=:all:` desde requirements | OK: wheels opencv-python 4.14.0.94 y numpy 2.5.3 para el objetivo disponibles. Esto no ejecuta Windows ni valida sus DLL. |
| `git init`, `git status --short --untracked-files=all`, `git check-ignore`, `git remote -v` | OK: repositorio local, sin remoto; .venv/cachés/logs ignorados; configuración y documentación versionables. No se hizo commit ni push. |
| Inspección de privacidad y rutas | OK: sin archivos visuales generados, sin rutas del computador incorporadas, sin funciones de almacenamiento/transmisión en src. |

## Cobertura de las pruebas simuladas

Configuración cargada desde otro directorio; valores numéricos inválidos, booleanos, NaN e infinito; archivo ausente, JSON malformado y campos incompletos. Captura: liberación ante error del consumidor, Ctrl+C, apertura fallida, excepción nativa, fallo del primer frame y fallback. Preview: q, ESC, cierre de ventana, fallo posterior de lectura y error de UI; limpieza de ventanas incluso si no se abre la cámara. Backends: orden automático Windows y rechazo de backend de otro sistema.

Se usan unittest y unittest.mock, de la biblioteca estándar; ninguna dependencia adicional. Las pruebas crean solo JSON temporal dentro de TemporaryDirectory y lo eliminan. La configuración real permanece intacta.

## Errores y correcciones

La segunda revisión encontró dos expectativas de tests atadas a camera_index=0, que habrían fallado al configurar legítimamente otra webcam. Se corrigieron para usar la configuración actual. Se añadió una prueba que exige limpieza de ventanas cuando todos los intentos de apertura fallan. No hubo errores de instalación ni pruebas fallidas en las ejecuciones registradas.

Los avisos nativos de OpenCV durante el escaneo son resultado de la ausencia de dispositivos. Se mantienen visibles y se acompañan de mensajes entendibles; no se ocultan excepciones importantes.

## Tres revisiones

1. Primera validación: estructura base, instalación aislada, compilación, imports, 15 tests, diagnóstico con escaneo, ausencia de escritorio y reglas Git.
2. Segunda revisión: lectura de cámara, preview, diagnóstico, instrucciones y plantilla; corrección de expectativas de tests; 16 tests aprobados y ejecución real del error de cámara ausente. Comprobación de wheels para Windows/Python 3.13.
3. Tercera revisión final: coherencia de todos los archivos, configuración inicial, alcance sin módulos futuros, rutas y privacidad, ejecución final de suite/compilación/dependencias, limpieza de cachés y verificación de contenido del ZIP.

## Pendiente en equipo objetivo

Todas las pruebas A–K en resultados_pruebas.md permanecen PENDIENTES: versión Python exacta, intérprete Windows, instalación real, webcam, estabilidad ≥30 segundos, teclas físicas, liberación, cambios de configuración y privacidad. Los controladores pueden ignorar propiedades o bloquear temporalmente llamadas nativas; el MVP no tiene timeout de hardware ni reconexión automática.

---

# HITO 2 - DETECCIÓN DE PERSONAS — 25 de septiembre de 2026

## Fuente de verdad y baseline

Se extrajo `capstone-vision.rar` adjunto y se leyeron todos los archivos fuente, configuración, pruebas, README, documentación y ajustes de VS Code antes de editar. No se reutilizó como base una carpeta de otra conversación. El RAR incluye un .venv de Windows/Python 3.13.15 y cachés; ese entorno se conservó intacto durante el trabajo, pero no es ejecutable en Linux ni se distribuye dentro del ZIP de código actualizado.

El adjunto real contiene 16 tests con los dos casos de fallback corregidos para solicitar `auto` explícitamente. Su `config/camera.json` contiene `backend: auto`, aunque las notas físicas históricas describen MSMF. Se conservó el archivo real sin imponer otro backend.

Antes de cambios, en entorno temporal aislado Linux x86_64/Python 3.12.14: **16/16 tests OK**, `compileall src` OK, diagnóstico sin acceso a webcam OK, `pip check` sin conflictos. Los avisos simulados v4l2/auto son esperados. No había fallos previos de código. El Python objetivo no se cambió.

## Versiones realmente instaladas y cargadas

| Componente | Distribución instalada | Versión cargada |
| --- | --- | --- |
| Python de validación | 3.12.14 Linux x86_64 | 3.12.14; objetivo Windows 3.13.15 pendiente |
| opencv-python | 4.14.0.94 | cv2 4.14.0 |
| ultralytics | 8.4.163 | 8.4.163 |
| torch | 2.14.0 | 2.14.0+cu130 |
| torchvision | 0.29.0 | 0.29.0+cu130 |

El wheel PyPI de torch para Linux instala sus runtimes CUDA como dependencias transitivas. No se instaló/configuró un driver o toolkit del sistema manualmente ni se utilizó GPU: `torch.cuda.is_available()` dio False y la inferencia se ejecutó con `device=cpu`. El sufijo de compilación no cambia las versiones fijadas en requirements.

Se ejecutó `python -m pip install -r requirements.txt` sobre el entorno de validación y `python -m pip check`: **No broken requirements found**. No se introdujeron dependencias directas adicionales para tests.

## Primera pasada — funcionalidad

- **48/48 pruebas unittest aprobadas: 16 Hito 1 + 32 Hito 2**.
- Configuración: JSON/BOM, directorio de trabajo alternativo, archivos ausentes/malformados, claves extra y tipos/rangos (incluidos bool, NaN e infinito).
- Detector: importación diferida, checkpoint creado una sola vez por ejecución, parámetros propagados, filtro person doble, confianza, cajas, tiempos opcionales, rechazo de entradas URL/índice/vacías, error de carga y error de inferencia.
- Recursos/UI simulados: q, ESC, X, Ctrl+C durante carga/inferencia, fallo de carga, inferencia, UI, lectura y apertura; se exige release y destrucción de ventanas.
- Diagnóstico: dependencia ausente, importación fallida/DLL y JSON inválido con mensajes claros; ajustes locales sin sincronización ni autoinstalación.
- Métricas: cálculo del FPS excluyendo primera inferencia; ocultar confianza no elimina etiqueta person.
- `compileall src tests`: OK. Imports de detector, detect y main sin cargar cv2/torch/ultralytics: OK.

### Carga e inferencia reales en CPU

La API oficial descargó una vez `yolo26n.pt` (aprox. 5.3 MB) de los assets oficiales. Se cargó y se ejecutó sobre dos frames negros sintéticos de 1280×720: 0 detecciones en ambos.

Se volvió a cargar con red bloqueada en el proceso para comprobar reutilización local de pesos. Resultado: **0 intentos de conexión**, 0 personas en ambos frames sintéticos, sin carpeta `runs/` ni archivos visuales. En esa comprobación se obtuvieron aproximadamente:

| Entrada | Inferencia | Procesamiento completo |
| --- | --- | --- |
| Primer frame sintético | 39.9 ms | 998.7 ms (incluye inicialización) |
| Segundo frame sintético | 20.3 ms | 22.1 ms |

La imagen de ejemplo `bus.jpg` ya incluida en el paquete de Ultralytics produjo 4 cajas, todas clase 0 (`person`), inferencia aprox. 41.6 ms. Se leyó desde el paquete y procesó en memoria; no se copió al proyecto ni se guardaron resultados. Esto comprueba ejecución real de la API, no precisión estadística ni una prueba física de webcam. Estos tiempos del entorno Linux no son una promesa para los computadores del usuario.

## Segunda pasada — regresión

Se ejecutó nuevamente la suite completa: **48/48 OK**. Comparación SHA-256 con los archivos del RAR: `src/camera.py`, `src/main.py`, `tests/test_hito1.py` y `config/camera.json` permanecen idénticos byte a byte. No se cambiaron los ajustes de VS Code, el init del paquete ni docs 00/01.

`src.config.load_config()` conserva firma y validaciones de cámara; comparte solo el lector JSON con detección. `src.main` permanece sin imports IA. Diagnóstico mantiene los datos y el escaneo previos, e informa IA sin cargar pesos; si IA falla, termina con código 1 tras conservar el diagnóstico de cámara.

Las anotaciones de resultados físicos previos del usuario se conservaron y se agregó una aclaración a la frase histórica de «pendientes» que contradice los estados OK. No se alteró la aprobación previa.

## Tercera pasada — entrega y errores encontrados

1. Ultralytics inicialmente intentó usar `/tmp` al no existir el directorio padre de ajustes: se corrigió creando la carpeta local de configuración antes de importar. Diagnóstico final sin ese warning.
2. El README original tenía bloques de comandos mal cerrados, explicaciones dentro de bloques ejecutables y proponía `git init` dentro de un módulo de un repositorio existente. Se corrigió manteniendo instalación, entorno, diagnóstico y preview del Hito 1; se agregó la ruta de actualización sin borrar .venv.
3. Se corrigió en la nueva ficha física la expresión de exclusión de .venv/.git para reconocer separadores Windows.
4. La simulación completa de resolución pip con `--platform win_amd64` desde Linux falló por evaluar `platform_system == Linux` con el sistema anfitrión y buscar un wheel Windows de NCCL. No se atribuye a un conflicto real en Windows. Comprobación alternativa: se descargaron los cuatro wheels directos Windows/CPython 3.13 con `--no-deps`. Su metadata confirma `torchvision 0.29.0 -> torch==2.14.0` y dependencias CUDA Linux protegidas por marcadores de plataforma. Esto acredita disponibilidad de paquetes directos, no ejecución de DLL ni resolución de todas las transitivas en Windows.
5. `python -m src.main` y `python -m src.detect` devuelven 1 con explicación de ausencia de sesión gráfica en este servidor. Es el manejo esperado del entorno sin escritorio; no es una aprobación física del visor.

Se verificaron pesos ignorados, opciones save desactivadas, ausencia de media/runs, rutas derivadas del proyecto, documentación, alcance y contenidos de la entrega. Se excluyen .venv, pesos, metadatos Git, cachés y ajustes generados del ZIP. El entorno temporal de validación y wheels temporales se eliminan al finalizar, sin tocar el .venv adjunto.

## Estado de Git

El RAR no trae `.git`; `git status` indica que no es un repositorio. Se revisaron diferencias con `git diff --no-index` y hashes contra la extracción original. No se hizo git init, staging, commit, push ni cambio de remoto. `.gitignore` ya ignoraba `*.pt`; se añadieron `runs/` y `.ultralytics/`. Revisar `git status`/`git diff` en el repositorio real después de aplicar el ZIP.

## Estado final y pendientes

**HITO 2 IMPLEMENTADO Y VALIDADO AUTOMÁTICAMENTE EN LINUX; ACEPTACIÓN FÍSICA PENDIENTE.**

Resultados finales: tests 48/48 OK; compileall OK; pip check sin conflictos; diagnóstico completo código 0; modelo cargado e inferencia real CPU OK. Sin webcam ni escritorio accesibles: se dejan las pruebas A–Q PENDIENTES en `resultados_pruebas.md` para Windows 10/11, Python 3.13.15, DroidCam/personas, UI, estabilidad, FPS, cierre y reutilización real del dispositivo. No se declara aprobado Hito 2 hasta recibir esos resultados.


---

# HITO 3 — BYTETRACK — Validación del 26-09-2026 UTC

## Fuente y baseline anterior a cambios

Se inspeccionó y extrajo el ZIP `capstone-vision(4).zip` adjunto; el archivo de encargo se leyó completo. Se revisaron código, configuraciones, dependencias, README, documentación, tests y VS Code. Se excluyeron caches, settings generados y pesos adjuntos del código de trabajo. No se reconstruyó el proyecto ni se creó un proyecto paralelo. El ZIP no contenía `.git`.

El intérprete global de este servidor es Python 3.12.14 y inicialmente no tenía OpenCV/Ultralytics/torch/torchvision. La primera suite falló al importar cv2; diagnostics informó esa carencia. Compileall e imports diferidos sí pasaron. El `pip check` global sin conflictos no acreditaba que las dependencias del proyecto estuvieran instaladas.

Se creó un entorno aislado de prueba, fuera del proyecto entregable, y se instalaron las cuatro versiones exactas de requirements original. Antes de editar el código: **48/48 tests OK (16 H1 + 32 H2), compileall OK, pip check OK, diagnostics código 0, imports H1/H2 OK**. La carencia inicial era del entorno, no un fallo previo del proyecto.

Valores reales conservados: cámara 0, 1280×720, 30 FPS solicitados, backend auto; detección yolo26n.pt, confianza **0.65**, IoU 0.70, tamaño 640, CPU, person 0. No se impuso 0.50 ni MSMF por referencias históricas.

## Dependencias efectivamente comprobadas

| Componente | Validación local | Objetivo conservado |
| --- | --- | --- |
| Python | 3.12.14, Linux x86_64, entorno aislado | 3.13.15 x64, Windows |
| OpenCV | opencv-python 4.14.0.94; cv2 4.14.0 | Sin cambio |
| Ultralytics | 8.4.163 | Sin cambio |
| torch | distribución 2.14.0; cargado 2.14.0+cu130 | Sin cambio |
| torchvision | distribución 0.29.0; cargado 0.29.0+cu130 | Sin cambio |
| lap | 0.5.12 | Nueva dependencia directa necesaria |
| PyYAML | 6.0.3, transitoria de Ultralytics | No nueva instalación independiente |

`lap` no llega con las cuatro dependencias originales y el módulo `matching.py` instalado lo requiere como `lap>=0.5.12`. Se agregó `lap==0.5.12` a requirements; no se instaló ByteTrack externo. Se descargó/verificó su wheel para Windows CPython 3.13 x64, sin ejecutar Windows. La instalación Linux resolvió runtimes GPU transitivos propios de torch: no se configuró CUDA manualmente ni se usó GPU; disponibilidad CUDA False, inferencia CPU.

Se compararon los ocho campos YAML con el archivo distribuido en Ultralytics 8.4.163 y se probó el BYTETracker real. Esta versión usa `track_buffer` directamente en frames procesados y limita el buffer de tracks removidos a 1000. No fueron necesarios campos YAML adicionales.

## Primera pasada — Funcionalidad y correcciones

H3 implementa configuración separada, YAML explícito, clase de datos Track, modelo único, persistencia, extracción de cajas/IDs, cajas sin ID, métricas, trails acotados y limpieza. Se reutiliza carga/validación de modelo y cámara existentes. No se ejecutan predict y track sobre el mismo frame.

La primera ejecución ampliada tuvo 86 tests: un fallo reveló que el nuevo diagnóstico interpolaba una excepción PackageNotFoundError sin nombre emitida por el mock. Se agregó tratamiento específico para dependencia lap ausente, con mensaje claro. Después se añadieron cuatro pruebas del ByteTrack real: **90/90 OK**.

Cobertura H3: 38 pruebas de configuración/rutas, YAML/rangos/tipos, IDs inválidos/duplicados/no finitos, geometría, modelo único, una llamada por frame, persistencia obligatoria, filtro person, opciones sin guardado, tiempos válidos, historial limitado y caducado, visualización, FPS, errores y limpieza de recursos. Más 4 pruebas reales del motor con cajas sintéticas: dos trayectorias móviles, oclusión breve, segunda asociación de baja confianza, expiración/reentrada e inmovilidad. Los cuatro métodos pueden cubrir más de un escenario.

## Inferencia real de YOLO + ByteTrack

Se descargó el checkpoint oficial mediante Ultralytics, una vez. No se utilizaron los pesos adjuntos como fuente de código o dependencias. Dos frames negros sintéticos dieron 0 tracks: primer procesamiento 1001.7 ms / inferencia 44.4 ms; segundo procesamiento 25.0 ms / inferencia 22.7 ms. Son comprobaciones de API, no cámara física.

Se utilizó `bus.jpg`, imagen de ejemplo incluida en el paquete instalado, leída en memoria. Una inicialización y 60 repeticiones posteriores mantuvieron **4 tracks, IDs 1/2/3/4**. La instancia BYTETracker permaneció idéntica, hubo un solo callback de tracking por evento y los frames vacíos incrementaron la edad del motor. H2 sobre la misma muestra devolvió 4 detecciones person sin track_id.

| Medida en muestra repetida, CPU | Resultado |
| --- | --- |
| Frames medidos después del arranque | 60 |
| Primera inferencia / procesamiento | 61.9 / 1080.6 ms |
| Inferencia media posterior | 40.8 ms |
| Procesamiento YOLO + tracking medio | 46.5 ms |
| Rango de procesamiento | 27.4–198.8 ms |
| Llamadas reales a predictor.inference | 60 para 60 frames |
| Intentos de conexión bloqueados/detectados | 0 |
| Archivos nuevos durante la prueba local | 0 |

El spy envolvió el método real `predictor.inference` con `wraps`: no sustituyó resultados ni desactivó la inferencia. La instrumentación exploratoria inicial usó un hook en el objeto modelo equivocado y contó también callbacks predeterminados como si fueran del tracker; se corrigió el procedimiento antes de registrar esta evidencia. No se interpretaron esos fallos de instrumentación como fallos de tracking.

Se bloquearon conexiones de sockets en el proceso de comprobación tras instalar dependencias y disponer de pesos. No hubo intentos de red ni media/runs generados. Esto complementa la revisión de opciones save desactivadas; no demuestra privacidad de otras aplicaciones que el usuario ejecute.

**FPS de webcam H3: PENDIENTE.** Esta muestra repetida no incluye captura ni GUI, fue ejecutada en un servidor distinto y coincidió con otras comprobaciones; sus tiempos no son un benchmark controlado. No es válido concluir cuánto sube o baja frente a los 20–24 FPS y 27–31 ms H2 físicos informados por el usuario. Se medirán en el mismo equipo/escena.

## Segunda pasada — Regresión

Suite final **90/90 OK = 16 H1 + 32 H2 + 38 H3 + 4 integración ByteTrack**. Los 48 tests previos permanecen byte a byte intactos. También son idénticos al ZIP `src/main.py`, `src/camera.py`, `src/detect.py`, `config/camera.json` y `config/detection.json`.

El único cambio en detector.py extrae su carga/validación a la función compartida `load_person_model`; el método detect conserva su llamada predict y estructura Detection sin ID. H1 importa sin cv2/torch/ultralytics/lap; la cámara y pesos se requieren únicamente al ejecutar su función correspondiente. Imports de los tres entrypoints juntos también pasan sin cargar bibliotecas IA o cámara.

## Tercera pasada — Entrega

| Comprobación | Resultado |
| --- | --- |
| `python -m compileall src tests` | Código 0 |
| `python -m pip check` | Código 0; No broken requirements found |
| `python -m unittest discover -s tests -v` | Código 0; 90 tests OK |
| `python -m src.diagnostics` | Código 0; versiones/config/YAML/import ByteTrack, sin pesos |
| `python -m src.diagnostics --scan` | Código 0; índices 0–4 sin webcam. Avisos de hardware esperados |
| `python -m src.main` / `src.detect` / `src.track` | Código 1 con explicación de falta de sesión gráfica. Es manejo de error, no validación física |
| Imports de todos los módulos | OK |
| JSON/YAML y rutas | Validadores y tests OK; rutas configuradas relativas al proyecto |
| Historial | Test de 10 000 IDs: máximo 32 historiales con buffer 30; vaciado posterior |
| Privacidad | Sin archivos visuales/runs; prueba de inferencia local sin intentos de red |
| Conservación documental | README original y resultados previos íntegros dentro de los archivos ampliados |
| Git | Sin .git adjunto; comparación contra ZIP, sin init/commit/push/remotos |
| Entrega | Árbol limpio, CRC y extracción del ZIP comprobados antes de entregar |

No se guardan rutas del entorno del desarrollador en configuraciones ni código. Las rutas absolutas que muestra diagnostics se calculan al ejecutar. `.gitignore` ya cubre entorno, cachés, `*.py[cod]`, pesos, runs, temporales y logs; no fue necesario cambiarlo.

Se retiraron del árbol final caches creadas al validar, settings técnicos y pesos temporales. Se conserva logs/.gitkeep y VS Code. Las 28 pruebas físicas H3 A–AB están preparadas, todas PENDIENTES; no se aprobaron Windows, webcam, personas, cama/mochila, FPS reales, oclusiones ni liberación física desde este servidor.

## Estado final

**Implementado y validado automáticamente en Linux. Aceptación física H3 pendiente.** Baseline detector 0.65 conservado; no llegan candidatos a la segunda asociación 0.10–0.25. La limitación se informa en consola, README y documentación. No hay hacks contra falsos positivos ni implementación de calibración espacial/Hito 4.

---

## Mejora multicámara — Validación del 2026-09-27

Esta sección corresponde exclusivamente a la mejora entre H3 y H4 sobre el ZIP actual adjunto. Las secciones anteriores conservan sus resultados históricos y no son resultados nuevos de esta tarea.

### Entorno y baseline antes de editar

Validación en Linux x64, Python **3.12.14**, entorno virtual nuevo con el `requirements.txt` adjunto: opencv-python 4.14.0.94, ultralytics 8.4.163, torch 2.14.0, torchvision 0.29.0 y lap 0.5.12. El objetivo Windows/Python **3.13.15** queda para la prueba del usuario; el diagnóstico avisa de la diferencia. No había webcam ni escritorio accesibles.

La primera revisión del intérprete global detectó ausencia de OpenCV y las dependencias IA: los tests/diagnóstico no podían ejecutarse allí. Se investigó como falta de entorno, se instalaron las versiones existentes en un entorno aislado y se repitió el baseline **antes de modificar fuentes**. Resultado: compileall 0, pip check 0, imports 0, **90/90 tests OK**, diagnostics 0, scan 0 con cero cámaras. No se cambiaron requisitos para resolver el entorno.

### Primera pasada — Funcionalidad multicámara

31 nuevos métodos de test, con subcasos, verifican validación estricta, prioridad CLI, copia sin escritura del JSON, índice fijo sin scan, cero/una/varias cámaras, índices 0 y 2, repetición de entradas inválidas sin reescaneo, cancelación, EOF y stdin no interactivo. Los fakes representan capturas separadas y fallan si se intenta abrir otra sin liberar la anterior.

Se verifican apertura fallida, frames ausentes/vacíos, excepciones de OpenCV/OS, Ctrl+C en open/set/read, fallback DSHOW→MSMF en el mismo índice, metadata desconocida, dimensiones tomadas del frame y descarte mediante referencias débiles. Todos los sondeos se liberan antes del input. La desaparición de la cámara seleccionada genera error sin nuevo scan ni cambio de índice.

La integración simulada de H1/H2/H3 procesa tres frames por sesión: una sola llamada al descubrimiento; aperturas 0,1,2,3,4 para scan y luego 2 para uso; overlay con índice 2; tres inferencias en H2/H3, ninguna en los sondeos. H1 no instancia detectores; H2 no instancia tracker. Cancelar no abre sesión, ventanas ni modelos. Ayuda/imports no cargan cv2/torch/ultralytics. Diagnóstico usa discovery y nunca el selector; sin --scan no crea VideoCapture.

### Segunda pasada — Regresión

**121/121 tests OK**: 16 H1 + 32 H2 + 38 H3 + 4 integración real ByteTrack + 31 multicámara. Los 90 tests previos mantienen todos sus métodos y aserciones. Solo se fijó `camera_index: 0` en cuatro líneas de fixtures H1/H2/H3, para conservar la prueba aislada de una sesión al cambiar el valor por defecto a auto. `test_hito3_integration.py` permanece idéntico; ejercita ByteTrack real con cajas sintéticas, sin webcam ni pesos.

Comparación contra el ZIP original: `src/detector.py`, `src/tracker.py`, `config/detection.json`, `config/tracking.json` y `config/bytetrack_capstone.yaml` son idénticos byte a byte. Los tres loops de frames también son idénticos; solo se añade resolución antes de la sesión. Se conserva confidence 0.65, CPU, IDs temporales y demás parámetros originales. No se implementó H4.

### Tercera pasada — Calidad de entrega

| Comprobación final | Resultado en este entorno |
| --- | --- |
| `python -m compileall src tests` | Código 0 |
| `python -m pip check` | Código 0; No broken requirements found |
| `python -m unittest discover -s tests -v` | Código 0; Ran 121 tests in 1.503s; OK |
| `python -m src.diagnostics` | Código 0; config/versiones/imports correctos, sin abrir cámara |
| `python -m src.diagnostics --scan` | Código 0; índices 0–4, lista vacía, sin selector |
| Imports H1/H2/H3 | Código 0; sin importar OpenCV ni IA al importar los entrypoints |
| `main`, `detect`, `track` sin escritorio | Código 1, error gráfico controlado previo a apertura |
| `main`, `detect`, `track` con guardia gráfica habilitada para probar ausencia de hardware | Código 1, mensaje “No se detectaron cámaras disponibles”, sin traceback Python; no se llegó a crear ventana |
| `--help` en los tres comandos | Código 0; anuncia `--camera N` |
| `--camera -1` en los tres comandos | Código 2; argumento rechazado antes de importar OpenCV |
| README | Solo tres adiciones: 6 líneas añadidas, 0 eliminadas; orden/texto anterior y CRLF conservados |
| requirements / .gitignore | Idénticos byte a byte |
| Historial documental | Resultados/validación ampliados al final; reportes H2/H3 intactos |
| Revisión manual | Selector/argparse comunes; sin scan por frame; sin escrituras de frames ni nuevas dependencias |
| Entrega | Limpieza de cachés/settings; ZIP con raíz única, integridad CRC y extracción comparada archivo por archivo |

Las llamadas nativas de OpenCV pueden imprimir avisos de dispositivos ausentes; no equivalen a un traceback Python ni a una prueba física fallida. Las pruebas con la guardia gráfica habilitada solo ejercitan el error antes de crear ventanas, no simulan un escritorio funcional.

No se descargaron pesos ni se ejecutó nueva inferencia YOLO real: este cambio no toca la inferencia, y su regresión está cubierta por tests y comparación. No se midieron FPS de webcam. Los 15 casos físicos MC-01–MC-15 quedan **PENDIENTES** en `resultados_pruebas.md`. No se afirma que DroidCam o Windows hayan sido probados aquí.

No se añadió .git, no hubo init/commit/push ni cambios de remotes. `.vscode/` y `logs/.gitkeep` se conservan. El ZIP excluye .venv, __pycache__, .pyc, pesos, runs, capturas, videos, logs de validación, temporales y settings de Ultralytics generados durante la comprobación. Los scripts de validación del entorno de desarrollo no se incluyen en el proyecto.

---

## Separación de preview directo / selector — 2026-09-27 (Chile)

Esta sección registra exclusivamente la corrección sobre el ZIP adjunto actual. Los resultados históricos de las secciones anteriores corresponden a sus respectivas entregas y **no deben interpretarse como validación del entorno de esta tarea**.

### Baseline antes de editar

Entorno actual: Linux, Python 3.12.14; sin dispositivos `/dev/video*`. Faltan OpenCV, Ultralytics y PyTorch. Antes de modificar: compileall código 0; pip check código 0; unittest código 1, con errores de importación/setup por dependencias ausentes; diagnostics código 1 por falta de cv2. Se intentó instalar el requirements exacto en un entorno aislado, pero la descarga fue bloqueada por la restricción de red (403 del proxy). No se cambiaron versiones ni requirements para eludir esa limitación.

Como comprobación suplementaria se ejecutaron los 117 tests de lógica H1/H2/H3/multicámara con un módulo OpenCV simulado y metadata marcada como `UNAVAILABLE_TEST_DOUBLE`. Pasaron 117/117 antes de editar. Se excluyeron de esa ejecución las 4 pruebas de integración real ByteTrack, que necesitan bibliotecas no disponibles. El adaptador de validación se mantiene fuera del proyecto; no se incluye ni se activa como fallback de la aplicación.

### Pasada 1 — Funcionalidad

`src.main` ahora resuelve exclusivamente un índice explícito mediante `direct_camera_config`: entero del JSON o override CLI temporal. No llama al resolver multicámara, discovery ni input. Con auto sin override devuelve un error claro que remite a configurar un entero o ejecutar el nuevo comando. `config/camera.json` se conserva en auto para mantener detect/track sin cambios.

`src.main_seleccionar_camera` carga/valida el JSON, fuerza auto en una copia temporal y llama al resolver existente de camera.py, incluso si el JSON contiene un entero. Después delega en `src.main.run_preview`. No acepta --camera: la apertura por índice corresponde al comando directo. Sondeo/selector/apertura/backends permanecen intactos. Solo hay un loop de preview, idéntico al original.

19 tests nuevos en `test_preview_modes.py`, con dobles explícitos de OpenCV y VideoCapture, pasan sin dependencias de visión instaladas. Verifican imports ligeros, directo sin discovery/input, índice 0, override con auto sin mutación, error ante auto/índices inválidos, fallo sin cambiar de cámara, reutilización del resolver/preview, cero/una/varias cámaras, entrada inválida sin rescan, q, EOF/stdin ausente, Ctrl+C durante sondeo/preview, ESC/cierre de ventana y desaparición de cámara seleccionada. Se verifica liberación entre sondeos y antes del input. Estos tests validan control de flujo y recursos simulados, no OpenCV nativo ni drivers.

### Pasada 2 — Regresión

117/117 tests anteriores de lógica vuelven a pasar con el mismo adaptador suplementario. Los 121 métodos de test existentes se conservan. H1/H2/H3 y las 4 pruebas de integración permanecen byte a byte intactos. En test_multicamara solo se adapta el preview automático al nuevo entrypoint, se fija la configuración del test del entrypoint directo y se refleja que cancelar antes del preview no crea ventanas que destruir. No se eliminan tests ni se omiten fallos dentro de la suite entregada.

Comparación byte a byte: `camera.py`, `camera_cli.py`, `config.py`, `detect.py`, `track.py`, `diagnostics.py`, `detector.py`, `tracker.py`, todas las configuraciones, requirements y .gitignore permanecen idénticos. No se cambian YOLO, ByteTrack, confidence, CPU/CUDA, IDs, trails, geometría ni parámetros. Los dos previews importan sin cv2/torch/ultralytics ni módulos de detección/tracking.

### Pasada 3 — Entrega y resultados finales

| Comprobación | Resultado actual |
| --- | --- |
| `python -m compileall src tests` | Código 0 |
| `python -m pip check` | Código 0: No broken requirements found; no demuestra que requirements esté instalado |
| `python -m unittest discover -s tests -p test_preview_modes.py -v` | Código 0; 19/19 tests nuevos OK con dobles explícitos |
| Regresión suplementaria con OpenCV simulado | 117/117 OK; integración real ByteTrack excluida de esta comprobación |
| `python -m unittest discover -s tests -v` | Código 1; Ran 23 tests, errors=5 por importación/setup sin dependencias; **suite completa no aprobada en este entorno** |
| `python -m src.diagnostics` | Código 1: No module named cv2 |
| `python -m src.diagnostics --scan` | Código 1 por falta de cv2; no se llegó al scan real |
| Imports separados de main, main_seleccionar_camera, detect y track | Código 0 en los cuatro |
| --help de los cuatro entrypoints | Código 0 |
| Ejecución real de los dos previews | Código 1, mensaje de instalación de OpenCV; sin ventana ni cámara real |
| README | Diff mínimo: 14 líneas añadidas, 4 eliminadas; sección Ejecución y una precisión necesaria en Configuración; CRLF conservado |
| Historial y archivos no relacionados | Preservados; nuevas pruebas CAM añadidas al final |
| ZIP | Proyecto completo con raíz única; CRC y extracción comparada archivo por archivo; sin cachés, pesos ni medios |

La suite entregada define **140 tests = 121 anteriores + 19 nuevos**. No se informa “140/140 OK”: faltan la ejecución ordinaria con las dependencias reales y la validación física. El comando normal no fue alterado para simular éxito ni saltar pruebas de integración. El código está implementado para revisión, pero la aceptación integral queda pendiente del entorno Windows/Python 3.13.15 del usuario.

Antes de dar por aprobada la corrección, ejecutar en el entorno del usuario `python -m pip install -r requirements.txt`, compileall, pip check, unittest y ambos diagnósticos. Completar CAM-01–CAM-09 de resultados_pruebas.md; reportar salidas y cualquier error. No se certifica DroidCam ni funcionamiento físico desde este servidor.

No se hizo init/commit/push ni cambio de remotes. Se preservan .vscode y logs/.gitkeep. Se retiraron cachés y settings de prueba antes de crear `capstone-vision-main-separado.zip`. No se implementó Hito 4 ni se abordaron los otros problemas pendientes.

---

## Corrección AUTO-FIRST — 2026-09-27 (Chile)

Esta sección registra la corrección sobre el ZIP actual adjunto después de la prueba física que detectó el rechazo de `camera_index: "auto"`. Los resultados anteriores se conservan como historial de cada entrega; no acreditan la ejecución de esta versión con dependencias reales.

### Baseline antes de modificar

Linux/Python 3.12.14, sin OpenCV, Ultralytics ni PyTorch instalados y sin dispositivos `/dev/video*`. La instalación de dependencias ya había sido bloqueada por la restricción de red durante esta sesión; no se cambiaron requisitos ni se repitió esa instalación para esta corrección.

| Comprobación previa | Resultado |
| --- | --- |
| compileall | Código 0 |
| pip check | Código 0; no acredita presencia de los paquetes del requirements |
| unittest ordinario | Código 1; 23 tests ejecutados, 5 errores de importación/setup por dependencias ausentes |
| tests de preview aislados | 19/19 OK con dobles explícitos |
| Regresión suplementaria | 136/136 OK con módulo OpenCV simulado; excluye 4 pruebas de integración real ByteTrack |
| diagnostics | Código 1: No module named cv2 |

El adaptador suplementario, externo al proyecto, marca su metadata como `UNAVAILABLE_TEST_DOUBLE`. No se instala una falsa biblioteca OpenCV ni se añade un fallback simulado a la aplicación. La suite ordinaria conserva sus pruebas y expone la falta de dependencias.

### Corrección y revisión funcional

La causa estaba en la llamada a `direct_camera_config` desde el entrypoint antes de la búsqueda: con auto generaba el error de índice entero. Ahora `src.main` carga/valida el JSON, verifica el entorno gráfico y, si no hay --camera, llama a `camera.find_first_available_camera`. Esta función reutiliza SCAN_INDICES y probe_camera, prueba 0–4 en orden y retorna inmediatamente el primer candidato que entregue un frame válido. No llama al discovery completo, select_camera ni input.

El sondeo exitoso se libera antes de la reapertura normal. El índice resuelto se pasa al preview existente; su loop de frames/FPS/overlay/cierres permanece idéntico. Si la reapertura falla, informa el error sin reanudar búsqueda. Con --camera N se omite toda búsqueda y se conserva la apertura directa de N, con fallback únicamente entre los backends existentes para ese mismo índice.

El modo automático funciona con JSON auto o entero; ese campo se sigue validando pero no elige el índice para src.main sin CLI. La configuración se copia en memoria y nunca se persiste. Los helpers internos de preview siguen recibiendo un índice ya resuelto, para que el selector pueda reutilizar el loop sin disparar otra búsqueda.

Se agregaron 12 tests y se adaptaron las expectativas previas que exigían rechazo de auto/apertura del índice fijo sin CLI. La cobertura anterior se conserva; los tests H1/H2/H3 e integración son idénticos al ZIP. El test de propagación de errores del entrypoint multicámara utiliza ahora CLI explícita para aislar el runner simulado de la búsqueda real.

Los nuevos casos verifican retorno del índice 0 sin tocar 1–4, retorno de 1 cuando 0 falla, uso del rango compartido, varias cámaras con auto y sin stdin, entero histórico ignorado sin override, CLI 0/1 sin ningún probe, CLI 99 fallido sin fallback, dispositivo que abre pero no entrega frame, Ctrl+C durante sondeo, fallo de reapertura sin nuevo scan y una única búsqueda antes de tres frames. Se mantienen los tests del selector con dos cámaras, elección de la segunda, entradas inválidas, q/EOF y liberación de todas las capturas.

### Regresión y revisión de entrega

Comparación contra el ZIP adjunto: todas las funciones y clases anteriores de camera.py permanecen iguales; solo se añade find_first_available_camera. main_seleccionar_camera.py, detect.py, track.py, diagnostics.py, detector.py, tracker.py, config.py, camera_cli.py, todos los JSON/YAML, requirements.txt y .gitignore son idénticos byte a byte. No se modifica IA, CPU/CUDA, IDs, trails, thresholds, bottom-center ni geometría. No hay búsqueda por frame.

| Validación final | Resultado |
| --- | --- |
| `python -m compileall src tests` | Código 0 |
| `python -m pip check` | Código 0; No broken requirements found, con dependencias requeridas todavía ausentes |
| `python -m unittest discover -s tests -p test_preview_modes.py -v` | Código 0; 31/31 OK con dobles explícitos |
| Regresión suplementaria con OpenCV simulado | 148/148 OK; 136 anteriores adaptados + 12 nuevos; excluye integración real ByteTrack |
| `python -m unittest discover -s tests -v` | Código 1; Ran 35 tests, errors=5 por dependencias ausentes |
| diagnostics normal y --scan | Código 1 por falta de cv2; sin escaneo real |
| Imports y --help de main, selector, detect y track | Código 0 en los cuatro |
| Ejecución real de ambos previews | Mensaje controlado de falta de OpenCV; no se abrió cámara ni GUI real |
| README | Solo 2 líneas sustituidas: título del preview y descripción corta; CRLF conservado |
| Historial | Resultados/validación ampliados al final, reportes previos intactos |
| ZIP | Raíz única, CRC y extracción comprobados; sin cachés, entornos, pesos, media, settings ni logs de validación |

Se definen **152 tests = 140 anteriores + 12 nuevos**. No se informa 152/152 OK ni se afirma validación física: faltan las 4 pruebas reales ByteTrack y la ejecución ordinaria de toda la suite con las dependencias instaladas. La aceptación completa requiere ejecutar las comprobaciones normales en Windows/Python 3.13.15 y completar AF-01–AF-08.

No hubo init/commit/push ni cambio de remotes. Se conserva .vscode y logs/.gitkeep. La entrega es `capstone-vision-camera-autofirst.zip`; el siguiente trabajo sobre rendimiento/tracking o Hito 4 no se implementó.
