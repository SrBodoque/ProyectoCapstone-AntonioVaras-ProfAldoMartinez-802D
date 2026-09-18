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
