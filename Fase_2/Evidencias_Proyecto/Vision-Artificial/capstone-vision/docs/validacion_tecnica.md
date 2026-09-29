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
