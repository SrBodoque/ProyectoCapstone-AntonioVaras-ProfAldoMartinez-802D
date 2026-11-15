# Calibracion del lanzador: autoguardado ? 2026-11-14

## Resultado y alcance

En `feature/visualizador-presentacion`, partiendo de HEAD `29d870d`, se elimino la seleccion obligatoria de salida antes del editor. `Dibujar zonas nuevas` abre el frame 0 del video seleccionado; `--frame` permite otro indice. No pregunta carpeta, nombre JSON ni responsable antes de dibujar. `S` valida y guarda una version nueva; el responsable se solicita al guardar si no se proporciono por CLI. `W` es la opcion secundaria Guardar como. El guardado satisfactorio cierra el editor y ofrece usar el perfil, mostrando la ruta completa.

Modificar JSON existente muestra el catalogo compatible y deja Buscar otro JSON como alternativa. Carga las zonas sin alterar el original. Salir sin guardar, incluso con un perfil inicial, no exporta un JSON nuevo. Los errores y cancelaciones del guardado mantienen la geometria en el editor para reintentar.

## Implementacion

- `src/launcher.py`: catalogo de perfiles para edicion; salida/responsable diferidos hasta S/W; frame inicial directo; confirmacion con ruta completa.
- `src/launcher_calibration.py`: adaptador del editor existente, con callback de guardado y salida tras S; conserva los controles geometricos, validacion de resolucion y hash del MP4. La ruta anterior sin callback sigue disponible.
- `src/launcher_autosave.py` (nuevo): versiones a partir de nombres y metadatos de perfiles compatibles y archivos existentes en el directorio destino. Valida un archivo temporal completo usando los exportadores/loaders reales antes de publicarlo mediante enlace duro exclusivo. No reemplaza archivos; una colision concurrente busca otra version. No crea el JSON final mientras se dibuja. El destino automatico permanece en el worktree actual. Camara publica tambien procedencia y mantiene `physical_count_validated=false`. Si falla la publicacion del perfil de camara, retira solo el sidecar creado por ese mismo intento.
- `tests/test_launcher.py`: adapta dos contratos de mocks al guardado por S y catalogo, conservando comprobaciones.
- `tests/test_launcher_autosave.py` (nuevo): 15 pruebas para versiones, esquemas/hash/geometria, no sobrescritura, colisiones concurrentes, errores/reintentos, cancelacion, output explicito, Guardar como, camara/procedencia, editor real con entradas simuladas y opciones inmediatas del visualizador.
- `tests/validate_launcher_autosave_local.py` (nuevo): integracion real Tk/OpenCV/CUDA con eventos de dibujo automatizados y preferencias aisladas.
- `README.md`: instrucciones de uso.

No se cambio detector, tracking, conteo A/B, FIFO, cadencia, visualizadores, calibrador tecnico ni exportadores estables. `config/baselines/sala_v4.json` y baseline abeb344 permanecen intactos. `--output` explicito se respeta; los puntos de entrada tecnicos no se editaron. No se instalaron dependencias. Sin commit, push, merge ni PR.

## Reproduccion

Directorio: `C:/Users/juanc/Downloads/LimpIA-visualizador-presentacion/Fase_2/Evidencias_Proyecto/Vision-Artificial/capstone-vision`.
Interprete existente: `C:/Users/juanc/Downloads/ProyectoCapstone-AntonioVaras-ProfAldoMartinez-802D/Fase_2/Evidencias_Proyecto/Vision-Artificial/capstone-vision/.venv/Scripts/python.exe`.

- Uso: `python ejecutable.py --calibrar --mp4`. Seleccionar video_03, Dibujar zonas nuevas, dibujar/cerrar A y B, S, indicar responsable, aceptar inicio. Repetir para verificar incremento de version. W permite otra ruta; Q/Esc permite cancelar.
- Regresion: `python -B -m unittest discover -s tests -v`, tres procesos independientes.
- Integracion automatizada: `python -B tests/validate_launcher_autosave_local.py --resources <directorio-original-capstone-vision>`. Usa video_03 original y pesos externos existentes; crea una nueva version de prueba sin borrar archivos previos.

## Tres regresiones finales

- Ronda 1: Ran 676 tests in 28.215s; OK (skipped=3); log `logs/autosave-final-1.txt`.
- Ronda 2: Ran 676 tests in 27.184s; OK (skipped=3); log `logs/autosave-final-2.txt`.
- Ronda 3: Ran 676 tests in 26.836s; OK (skipped=3); log `logs/autosave-final-3.txt`.

Sin advertencias de ciclo de vida Tk en las tres. Omisiones heredadas: integracion real ReID, integracion MP4 optativa y prueba de symlink sin permisos. Ninguna corresponde a las pruebas nuevas. `python -B -m pip check`: No broken requirements found. `git diff --check` correcto; ningun cambio preparado en Git.

## Aceptacion grafica

La integracion con entrada automatizada abrio el editor OpenCV real sin dialogo de guardado, dibujo A/B a traves de su callback registrado, pulso S, genero versiones nuevas y utilizo inmediatamente el perfil con ByteTrack/cuda:0. Una ejecucion proceso 65 fotogramas sin errores Tk ni de sesion; hash del baseline conservado. Los JSON creados en results_testing/calibration_profiles son artefactos de prueba, con responsable identificado como integracion automatizada; no constituyen una nueva calibracion humana ni validacion del conteo fisico. Informes exclusivos `logs/autosave-real-<uuid>.json` y salida final `logs/autosave-real-final.txt`.

La aceptacion manual mediante control de Windows sigue pendiente: `get_window_state` fallo con `FrameArrived timed out: timed out waiting on channel`; tras refrescar la seleccion y activar la ventana, fallo con `window capture timed out: timed out waiting on channel`. Se cerro el intento propio bloqueado. No se presenta la integracion automatizada como comprobacion manual. Se solicito al usuario verificar el recorrido sin explorador anticipado.

La captura fisica de camara no se repitio: el autoguardado/perfil/procedencia de camara se verifico con fixtures y su captura estable se conserva. Recomendacion: completar la aceptacion manual antes de autorizar un commit/push.

Resultado final exacto: `video_03.zones.v7.json`, 65 fotogramas procesados en cuda:0, sin error de sesion/Tk y baseline conservado. Se preservaron tambien los artefactos v5/v6 de los intentos de prueba anteriores.


## Aceptacion humana posterior

El usuario confirmo personalmente que `python ejecutable.py --calibrar --mp4`, seleccionando video_03 y Dibujar zonas nuevas, abre inmediatamente el editor correcto sin pedir un JSON. La correccion principal de autoguardado queda aceptada manualmente. El ajuste posterior de navegacion se documenta por separado.
