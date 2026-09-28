# Reporte final — Selección multicámara

Fecha: 2026-09-27. Fuente: proyecto actual del ZIP adjunto, sin reconstrucción. Mejora de infraestructura entre H3 y H4.

1. **Estado:** implementada y validada automáticamente. Tres pasadas completas: funcionalidad, regresión y calidad de entrega. Apta para ejecutar las pruebas físicas; aceptación de hardware pendiente.
2. **ZIP final:** `capstone-vision-multicamara.zip`, proyecto completo bajo una única raíz `capstone-vision/`, con integridad CRC y extracción verificadas.
3. **Problema resuelto:** permite elegir la cámara antes de iniciar preview, detección o tracking, sin asumir que índice 0 representa siempre el dispositivo deseado.
4. **Arquitectura:** discovery/probe/selector/resolución en `src/camera.py`; argparse compartido en `src/camera_cli.py`; validación en `src/config.py`. Reutiliza `open_camera` y `camera_session`. `diagnostics --scan` usa el mismo discovery.
5. **Precedencia:** CLI `--camera N` → índice fijo del JSON → descubrimiento si el JSON contiene `"auto"`.
6. **Auto:** un scan 0–4 al inicio; cero genera error, una se elige sola, varias muestran selector por índice real. Entradas inválidas repiten sin scan; q cancela.
7. **Índice fijo:** apertura directa, sin scan ni selector. Puede probar varios backends para el mismo índice; no cambia a otro índice si falla.
8. **--camera:** disponible en main/detect/track, temporal y sin escribir JSON. Rechaza negativos/no enteros; conserva límite de OpenCV 2147483647. La configuración completa sigue validándose.
9. **Archivos nuevos:** `src/camera_cli.py`, `tests/test_multicamara.py`, `docs/03a_seleccion_multicamara.md`, `REPORTE_MULTICAMARA.md`.
10. **Archivos modificados:** `config/camera.json`; `src/config.py`, `src/camera.py`, `src/main.py`, `src/detect.py`, `src/track.py`, `src/diagnostics.py`; `tests/test_hito1.py`, `tests/test_hito2.py`, `tests/test_hito3.py`; `README.md`; `docs/resultados_pruebas.md`, `docs/validacion_tecnica.md`. Los tests previos solo cambian cuatro líneas de fixtures para fijar la cámara de sus sesiones; mantienen métodos y aserciones.
11. **README diff:** tres notas breves sobre CLI, auto/fijo y enlace a la guía. 6 líneas añadidas (3 de texto y 3 vacías), 0 eliminadas. Sin reordenar, reescribir ni cambiar CRLF.
12. **Requirements diff:** ninguno, idéntico byte a byte. `.gitignore` también intacto. No nuevas dependencias.
13. **Tests nuevos:** 31 métodos con subcasos: tipos/rangos, prioridades, 0/1/varias cámaras, índices no consecutivos, reintentos, cancelación, EOF/stdin, recursos, metadata, fallback, CLI, diagnósticos y tres pipelines.
14. **Tests previos:** 90/90 pasan: 16 H1, 32 H2, 38 H3 y 4 integración real de ByteTrack con cajas sintéticas. Antes de editar también pasaban 90/90 en el entorno preparado.
15. **Compileall:** código 0.
16. **Pip check:** código 0, `No broken requirements found`.
17. **Unittest:** código 0, **121/121 OK** (1.503 s). Pruebas de cámara con fakes; no requieren webcam ni pesos.
18. **Diagnostics:** normal y --scan retornan 0. Normal no abre cámara; scan recorre 0–4 y devuelve lista vacía. Entorno Linux/Python 3.12.14; objetivo Windows/Python 3.13.15 pendiente. El entorno global inicialmente carecía de bibliotecas: se instalaron las versiones del requirements en un entorno aislado antes del baseline.
19. **Regresión H1:** sigue siendo OpenCV + webcam, sin YOLO/ByteTrack. Loop intacto e imports ligeros. Pruebas de cierre y errores pasan.
20. **Regresión H2:** YOLO sin tracking persistente. `src/detector.py` y detection.json idénticos; confidence 0.65 conservado. No nueva inferencia YOLO real en esta tarea.
21. **Regresión H3:** YOLO + ByteTrack, mismos IDs temporales y parámetros. `src/tracker.py`, tracking.json y YAML idénticos. Loop intacto; integración ByteTrack real y tests pasan.
22. **Recursos:** capturas liberadas entre intentos, índices y antes del selector. Probado ante open/read/set fallidos, frames vacíos, excepciones, Ctrl+C y cancelación. El frame de probe se descarta y no llega a YOLO. La sesión seleccionada conserva su finally.
23. **Errores:** cero cámaras, índice fallido, entrada inválida, EOF y stdin no interactivo tienen manejo explícito; q retorna 0, errores de uso/hardware 1, CLI inválida 2. Los tres comandos produjeron error controlado sin traceback por ausencia de hardware; sin escritorio mantienen su mensaje previo. Avisos nativos de OpenCV pueden aparecer en stderr.
24. **Rendimiento:** scan exclusivamente al inicio, fuera de los tres loops. Prueba de tres frames por modo confirma un único scan y tres inferencias donde corresponde. Sin benchmark artificial; FPS físicos pendientes.
25. **Privacidad:** sin reconocimiento facial, ReID, grabación, almacenamiento ni envío de frames de sondeo. Solo metadata. No se añadieron media/runs al proyecto. El indicador luminoso puede encenderse durante scan.
26. **Limitaciones:** índices variables por equipo/driver/backend; scan 0–4; nombres genéricos; alias físicos no identificables de forma fiable; una cámara virtual puede entregar un frame congelado; cambios de disponibilidad entre scan y reapertura; llamadas nativas sin timeout garantizado. Se procesa una cámara por sesión. No se implementó reescaneo r.
27. **Git:** el ZIP no trae .git. Comparación contra el original; sin init, commit, push ni cambios de remotes. Commit manual por el usuario en GitHub Desktop.
28. **Limpieza:** entrega sin .venv, cachés, .pyc, pesos, runs, media, temporales, logs de validación ni settings generados. Conserva `.vscode/` y `logs/.gitkeep`. README/config/src/docs/tests/requirements incluidos, sin carpeta raíz duplicada.
29. **Pruebas físicas pendientes:** MC-01–MC-15 preparadas en `docs/resultados_pruebas.md`, todas PENDIENTES: cámara única, integrada+DroidCam, ambas selecciones, H1/H2/H3, fijo, override, entrada inválida, DroidCam apagado, liberación, cierres, IDs y privacidad. Los resultados físicos previos permanecen intactos.
30. **Comandos exactos:** desde `capstone-vision`, con el entorno virtual activado y `"camera_index": "auto"` para los comandos sin override. Ejecutar por separado; 1 es un ejemplo, reemplazar por el índice real disponible.

    ```powershell
    python -m src.main
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

31. **Resultados solicitados:** PC con una cámara: índices detectados, auto sí/no y cámara correcta sí/no. Laptop+DroidCam: índices/resolución/backend, selector sí/no y apertura de integrada/DroidCam sí/no. Main: ambas sí/no; detect: DroidCam+YOLO sí/no; track: DroidCam+ByteTrack sí/no y observaciones de IDs. Override funciona sí/no y JSON intacto; fijo evita selector sí/no; recursos liberados sí/no; FPS H3 aproximados tras selección; crashes/tracebacks sí/no y mensaje completo; archivos visuales creados sí/no. Adjuntar salidas de validación y fichas MC.
32. **Siguiente paso:** después de validar físicamente la selección, **Hito 4 — Calibración espacial**. No implementado ahora: no zonas, línea, IN/OUT ni perfiles por cámara.
