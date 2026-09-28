# Separación de preview directo y selector

Corrección sobre el ZIP actual adjunto, 2026-09-27 (Chile).

1. **Estado:** implementación lista para revisión. Validación completa pendiente por dependencias ausentes y descarga bloqueada en este entorno. Revisadas funcionalidad, regresión y entrega; no se declara aceptación integral.
2. **ZIP final:** `capstone-vision-main-separado.zip`, proyecto completo, una raíz `capstone-vision/`, integridad CRC y extracción verificadas.
3. **src.main:** abre directamente el índice entero configurado o el override temporal `--camera N`. Nunca escanea, lista cámaras ni pide input. Si camera_index es auto y no hay override, muestra un error que remite al nuevo comando; no elige cámara arbitraria. El JSON adjunto se conserva en auto para no cambiar detect/track.
4. **src.main_seleccionar_camera:** siempre utiliza discovery al arrancar, incluso con índice entero en el JSON. Cero cámaras: error; una: selección automática; varias: selector con reintento de entradas inválidas. Selección temporal, sin escribir JSON. No carga YOLO/ByteTrack; no acepta --camera, pues para apertura explícita existe src.main.
5. **Arquitectura reutilizada:** camera.py y su resolver/sondeo/backends intactos. El nuevo entrypoint delega en `src.main.run_preview`; existe un solo loop de frames/FPS/overlay/cierres, idéntico al anterior. No se duplican la lógica de cámara ni el loop de preview.
6. **Archivos nuevos:** `src/main_seleccionar_camera.py`, `tests/test_preview_modes.py`, `REPORTE_MAIN_SEPARADO.md`.
7. **Archivos modificados:** `src/main.py`, `tests/test_multicamara.py`, `README.md`, `docs/03a_seleccion_multicamara.md`, `docs/resultados_pruebas.md`, `docs/validacion_tecnica.md`. Ningún archivo de configuración cambia.
8. **README diff:** 14 líneas añadidas, 4 eliminadas; dos comandos claros bajo Ejecución y precisión en Configuración. Sin reconstruir/reordenar; CRLF conservado.
9. **Requirements diff:** ninguno. No dependencias nuevas; .gitignore intacto.
10. **Tests nuevos:** 19/19 OK con dobles explícitos, ejecutables sin OpenCV instalado; validan ambos modos, error ante auto, selección, inmutabilidad, imports y recursos. No constituyen prueba de drivers reales.
11. **Tests previos:** los 121 métodos se conservan. 117/117 tests de lógica pasan antes y después con OpenCV simulado en un adaptador externo de validación. Las 4 pruebas de integración real ByteTrack no pudieron ejecutarse por falta de dependencias. H1/H2/H3 e integración permanecen idénticos; los tests multicámara solo adaptan el preview al nuevo entrypoint y sus expectativas de configuración/cancelación.
12. **Compileall:** código 0.
13. **Pip check:** código 0, No broken requirements found. Esto no acredita la instalación del requirements: faltan OpenCV y las bibliotecas IA.
14. **Unittest:** comando completo con código 1; 23 tests ejecutados, 5 errores de importación/setup por dependencias ausentes. Suite de 140 tests definida, **sin aprobación completa** en este entorno. El baseline ya presentaba esa limitación.
15. **Diagnostics:** normal y --scan con código 1 por falta de cv2; no se efectuó scan real. Ambos módulos siguen sin cambios. La instalación intentada fue bloqueada por la red (403); no se modificaron requisitos para sortearlo.
16. **Regresión H1:** modo directo restaurado, sin IA; loop y tests H1 intactos. Nuevo comando reutiliza el preview. Los imports de ambos funcionan sin bibliotecas de visión.
17. **Regresión H2:** detect.py, detector.py y detection.json idénticos; pruebas de lógica simuladas pasan. Ejecución real pendiente.
18. **Regresión H3:** track.py, tracker.py, tracking.json y YAML idénticos; lógica simulada pasa. Integración real/ejecución física pendientes en esta tarea.
19. **Recursos:** tests verifican liberación entre sondeos y antes del selector, liberación de la cámara final y destrucción de ventanas con q/ESC/cierre/error/Ctrl+C. Cancelar antes del preview no crea ventanas. No se guardan imágenes/videos.
20. **Limitaciones:** Linux/Python 3.12.14 frente a objetivo Windows/Python 3.13.15; faltan dependencias y hardware accesible. Se conservan límites del scanner 0–4, índices variables y llamadas nativas potencialmente lentas. La simulación no garantiza comportamiento de drivers ni rendimiento.
21. **Git:** sin .git adjunto; comparación contra ZIP. Sin init, commit, push ni cambio de remotes. Entrega limpia; se conservan .vscode y logs/.gitkeep.
22. **Pruebas físicas pendientes:** CAM-01–CAM-09 añadidas sin modificar resultados históricos: directo, selector con una/varias cámaras, integrada, DroidCam, cierres y regresión detect/track. Todas PENDIENTES.
23. **Comandos exactos:** desde la raíz con el entorno activado. Para `src.main` sin argumentos, configurar un índice entero en camera.json; con el JSON auto actual usar el override directo. Reemplazar 0 por el índice real disponible.

    ```powershell
    python -m pip install -r requirements.txt

    # Preview directo: requiere camera_index entero en camera.json
    python -m src.main

    # Alternativa directa temporal, compatible con camera_index auto
    python -m src.main --camera 0

    # Preview con selección, incluso con JSON fijo
    python -m src.main_seleccionar_camera

    python -m src.detect
    python -m src.track
    python -m src.diagnostics
    python -m src.diagnostics --scan

    python -m compileall src tests
    python -m pip check
    python -m unittest discover -s tests -v

    python -c "import src.main"
    python -c "import src.main_seleccionar_camera"
    python -c "import src.detect"
    python -c "import src.track"
    ```

24. **Siguiente paso:** completar validación ordinaria con dependencias reales y CAM-01–CAM-09. Devolver salidas de tests/diagnósticos y si cada modo abre/libera la cámara correcta, si el selector aparece solo donde corresponde y si el JSON permanece intacto. Rendimiento/CUDA/oclusiones/bottom-center quedan fuera de esta tarea. Hito 4 no implementado.
