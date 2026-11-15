# Navegacion del lanzador ? 2026-11-14

## Diagnostico

`Cancelled` representaba tanto cancelar una operacion como terminar el flujo. En `main()`, `if choosing_menu or not menu: return 0` cerraba el proceso al cancelar una sesion iniciada por CLI. La cancelacion del editor y del catalogo de perfiles se propagaba hasta ese nivel; tampoco existian retornos locales suficientes. El selector Video MP4/Camara ya existia para Calibrar zonas: se reutilizo.

## Correccion

Se mantienen una raiz Tk y Toplevels modales. El controlador distingue menu, selector de fuente, seleccion de entrada, base de calibracion, perfil, confirmacion y preparacion. Las cancelaciones se resuelven en el nivel que abrio la pantalla; no se implementa navegacion recursiva ni se crean nuevos mainloops.

- Editor Esc/Q/X sin guardar: Base de calibracion. Con geometria sucia se conserva la confirmacion de descarte del editor estable; no se exporta un JSON.
- Catalogo de JSON para modificar: Base de calibracion.
- Base: seleccion de video/camara; si la calibracion se abrio desde Zonas de transicion, vuelve a ese catalogo.
- Catalogo de videos/camaras: selector de fuente cuando corresponde a calibracion; en apertura normal, menu.
- Selector de fuente: menu.
- Explorador nativo de MP4/JSON: vuelve al catalogo que lo abrio.
- Preparar sesion: perfil anterior o confirmacion del perfil recien guardado, sin volver a dibujar. Conserva tracker, dispositivo y carpeta de pesos; preserva la entrada cuando corresponde. Se eliminan solo estados de perfil/confirmacion incompatibles al cambiar de entrada.
- Visualizador cerrado/finalizado: libera la sesion, une su worker y vuelve al menu, tambien con comandos directos.
- Dialogos secundarios: Volver/Cancelar, Esc y X regresan. En comprobaciones en curso, Esc/X solicita cancelacion y espera liberacion del worker. En la validacion de dispositivo dentro de Preparar sesion, cancela esa comprobacion y permanece en Preparar sesion.
- Menu principal: solo Salir o X termina. Esc no cierra el proceso.

Los comandos `python ejecutable.py --calibrar --mp4` y `--calibrar --camara` omiten inicialmente el selector de fuente, pero permiten regresar a el y al menu. Se respetan las rutas CLI explicitas al iniciar; una salida ya guardada no se reutiliza para sobrescribir al regresar. Hay selector de camara incluso si solo se detecta una, para permitir volver.

El host del visualizador cancela sus temporizadores nuevos despues de cerrar su Toplevel y detener/join de la sesion. No se modifican ticks, FIFO, captura ni cadencia del visualizador. `StringVar.get()` y cambios de widgets siguen exclusivamente en el hilo principal; CUDA/probes mantienen la cola y workers existentes.

## Archivos de esta correccion

- `src/launcher.py`: retornos por etapa, menu persistente y contexto de sesion.
- `src/launcher_ui.py`: Esc/Volver/X, conservacion de ajustes y limpieza de timers del host.
- `tests/test_launcher.py`: expectativa actualizada de regreso al menu tras un comando directo.
- `tests/test_launcher_navigation.py` (nuevo): 19 pruebas, incluyendo widgets Tk reales con Esc/X/Volver, worker cancelado, editor con/sin cambios, preservacion de contexto, cancelacion de selectores nativos, dos aperturas y ausencia de timers pendientes.
- `tests/validate_launcher_navigation_local.py` (nuevo): recorrido integrado de ventanas reales Tk/OpenCV y dos sesiones CUDA, con entrada de prueba automatizada.
- `README.md`, este documento y nota de aceptacion en `LAUNCHER_CALIBRATION_AUTOSAVE.md`.

Los cambios de autoguardado previos permanecen en el arbol y no se atribuyen a este ajuste. La apertura directa sin pedir JSON ya fue aceptada personalmente por el usuario. No se modifico ahora el adaptador/calibrador estable para redefinir sus controles: se maneja su Cancelled en el controlador.

## Validacion grafica integrada

Comando: `python -B tests/validate_launcher_navigation_local.py --resources <capstone-vision-original>`.
Salida final: `logs/navigation-real-final.txt`; informes exclusivos `logs/navigation-real-<uuid>.json`.

Recorrido real automatizado: menu -> calibrar -> fuente video -> video_03 -> nuevo -> editor real/Esc -> base -> modificar -> catalogo JSON/Esc -> base/Esc -> catalogo video/Esc -> fuente camara -> seleccion camara/Esc -> fuente/Esc -> menu -> MP4/perfil -> Preparar sesion/Esc -> perfiles -> Preparar sesion/iniciar -> visualizador/cierre -> menu -> segunda sesion -> visualizador/cierre -> menu/X.

Dos sesiones ByteTrack/cuda:0 con pesos originales: 65 fotogramas procesados cada una, sin error. Cero errores de callbacks/finalizadores Tk y cero workers LimpIA pendientes. Todos los pasos previstos se completaron. La ventana de seleccion de camara es real, pero su deteccion se simulo con un AvailableCamera; no se declara prueba de captura fisica de camara ni precision del conteo. Los eventos Esc/X/dibujo se inyectan mediante las APIs del propio toolkit: es integracion grafica automatizada, no aceptacion humana nueva.

Las pruebas unitarias comprueban aparte X del editor, confirmacion de descarte, X/Volver de Preparar sesion, Esc en menu, cancelacion de busy y ausencia de after pendientes. No se reintento el helper externo de captura de Windows, que habia fallado anteriormente; este recorrido no lo necesita.

## Reproduccion manual especifica

Desde el worktree de presentacion:

1. `python ejecutable.py --calibrar --mp4`: elegir video_03, Dibujar zonas nuevas, Esc. Debe aparecer Base de calibracion.
2. Elegir Modificar JSON existente y Volver: Base. Volver otra vez: catalogo de videos. Volver: selector de fuente. Volver: menu.
3. Repetir entrando desde `python ejecutable.py` -> Calibrar zonas. Elegir Camara, volver de su selector; debe aparecer fuente. En el preview/editor, Esc debe volver a Base; confirmar descarte solo si hay cambios.
4. Abrir video/perfil -> Preparar sesion. Cambiar tracker y Volver; elegir perfil otra vez y comprobar que se conserva. Cancelar no debe iniciar un worker de inferencia.
5. Iniciar visualizador, cerrar con X y abrir otra sesion desde el menu. Cerrar el menu con X o Salir. Esc en el menu no lo termina.

Los recorridos automatizables quedaron cubiertos; estas instrucciones permiten una comprobacion humana adicional, sin presentarla como ya recibida. No se requiere repetir la validacion fisica del conteo para este cambio de control de flujo.

## Preservacion y Git

Rama feature/visualizador-presentacion. Sin cambios en baseline abeb344, config/baselines/sala_v4.json, modelos/pesos/videos, detector, trackers, conteo, configuraciones de deteccion, calibradores tecnicos ni modulos de procesamiento/visualizacion. Las comprobaciones de diff de esos archivos contra HEAD no mostraron cambios. Sin dependencias nuevas ni modificaciones de preferencias personales en pruebas (LOCALAPPDATA aislado). `pip check` correcto. `git diff --check` correcto. Sin cambios preparados, commit, push, merge ni PR. Recomendacion: revisar el diff y la navegacion humana antes de autorizar commit/push.

## Tres regresiones finales independientes

Interprete: `.venv/Scripts/python.exe` del capstone-vision original, Python 3.13.15. Comando: `python -B -m unittest discover -s tests -v`. Tres procesos nuevos, despues del ultimo cambio funcional y sin inferencias GPU concurrentes.

- Ronda 1: Ran 695 tests in 29.991s; OK (skipped=3); avisos Tk: []. Log `logs/navigation-final-v2-1.txt`.
- Ronda 2: Ran 695 tests in 29.839s; OK (skipped=3); avisos Tk: []. Log `logs/navigation-final-v2-2.txt`.
- Ronda 3: Ran 695 tests in 30.030s; OK (skipped=3); avisos Tk: []. Log `logs/navigation-final-v2-3.txt`.

Las tres omisiones heredadas corresponden a integracion ReID, integracion MP4 optativa y symlink sin permisos. Las 19 pruebas nuevas de navegacion se ejecutaron. Sin fallos/errores de unittest. Los logs de la primera serie (693 pruebas) son anteriores a los ultimos dos casos de retorno y no se usan como evidencia final.
