# Correccion de inicio Tkinter ? 2026-11-14

## Causa demostrada

En `TkDialogs.settings.start()` (`src/launcher_ui.py`), el callback del boton creaba `lambda cancel: validate_device(device.get())`. `device` es un `tkinter.StringVar` creado en el hilo principal. `busy()` ejecutaba esa lambda en `LimpIA-launcher-check`; por tanto, el acceso a Tcl ocurria en el worker, antes de validar CUDA. Una reproduccion aislada con la expresion anterior y el mismo `busy()` devuelve exactamente `RuntimeError: main thread is not in main loop`, incluso sin cargar PyTorch. No es un fallo de CUDA.

El cierre de variables Tk retenidas por callbacks/tracebacks tambien puede producir el aviso observado de `Variable.__del__`. No se ocultaron stderr ni excepciones, ni se desactivo GC.

## Cambio minimo

Se lee `device.get()` en el callback grafico y se entrega al worker solo la cadena seleccionada. La cancelacion de esa comprobacion vuelve a Preparar sesion con un mensaje y permite reintentar; antes `Cancelled` escapaba del callback Tk.

Se conserva una raiz Tk y ventanas Toplevel. Los widgets, StringVar y destruccion de ventanas pertenecen al hilo principal. `busy()` mantiene su Queue y sondeo `after`: el worker solo valida recursos; el resultado se procesa en el hilo grafico, se destruye el dialogo y se une el worker. `wait_window` procesa eventos de la misma raiz; no se creo otro Tk/mainloop. Los errores de dispositivo quedan visibles en Preparar sesion, sin fallback silencioso. La cancelacion espera que termine el trabajo en curso, sin abandonar el hilo. El cierre del visualizador conserva la detencion y liberacion existentes.

## Archivos de esta correccion

- `src/launcher_ui.py`: captura del dispositivo y manejo local de Cancelled.
- `tests/test_tk_startup.py`: boton real de Preparar sesion, dos sesiones CPU, comprobacion de hilo en cada StringVar.get, worker no grafico, GC activo, errores no capturados y recuperacion de cancelacion/error con reintento. Complementa las pruebas existentes de menu, cancelacion real de busy y cierre/join.
- `tests/validate_tk_startup_local.py`: menu Tk real y boton de inicio real, CUDA y dos visualizadores reales en la misma raiz; informe de errores y workers.
- Este documento.

## Hardware

Prueba final: RTX 5060, `cuda:0`, ByteTrack, `video_03.mp4`, `config/baselines/sala_v4.json` (video3v4), pesos externos originales. Dos aperturas desde el menu en el mismo proceso: 65 fotogramas procesados cada una, ambas detenidas sin error, cero errores de callbacks/Tk finalizers y cero workers LimpIA pendientes. Informe: `logs/tk-startup-real-cuda-final.json`; salida completa: `logs/tk-startup-real-cuda-final.txt`.

La prueba automatiza los botones reales de menu y Preparar sesion; suministra las rutas ya conocidas por CLI para no automatizar el selector nativo de archivos. No equivale a una nueva validacion del conteo completo; no se cambio procesamiento, FIFO ni cadencia.

## Preservacion

Sin cambios en baseline abeb344, perfiles, modelos/pesos, deteccion, tracking, conteo, captura, calibrador o visualizador tecnico. Se conservaron descubrimiento de recursos y preferencias. Sin commit/push/merge/PR. El diff de archivos versionados respecto de abeb344 contiene solo README.md, previamente modificado por el desarrollo del visualizador; los archivos del lanzador siguen sin versionar en feature/visualizador-presentacion.

## Tres regresiones finales independientes

Comando: `python -B -m unittest discover -s tests -v`, en tres procesos nuevos.

- Ronda 1: Ran 661 tests in 26.985s; OK (skipped=3); avisos Tk: [].
- Ronda 2: Ran 661 tests in 25.964s; OK (skipped=3); avisos Tk: [].
- Ronda 3: Ran 661 tests in 26.214s; OK (skipped=3); avisos Tk: [].

Los tres skips son heredados de la suite; no se omitieron las nuevas pruebas Tk. Los mensajes FFmpeg de MP4 invalido pertenecen a fixtures negativos existentes. No hubo RuntimeError de Tk ni excepciones de Variable.__del__.
