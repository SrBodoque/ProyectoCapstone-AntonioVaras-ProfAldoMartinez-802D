# Corrección de cámara AUTO-FIRST

Fuente: ZIP actual adjunto. Fecha: 2026-09-27 (Chile).

1. **Estado:** corrección implementada y probada con recursos simulados. La validación integral sigue pendiente por dependencias ausentes en el entorno actual. No se declara aprobación física ni de la suite con bibliotecas reales.
2. **ZIP:** `capstone-vision-camera-autofirst.zip`, proyecto completo con raíz única, CRC y extracción verificados. Sin cachés, entornos, pesos, medios ni temporales.
3. **Causa del error original:** src.main llamaba a direct_camera_config antes de buscar; ese helper exigía un entero y rechazaba auto, que era el valor configurado.
4. **Solución:** nueva función find_first_available_camera en camera.py reutiliza probe_camera, camera_session, open_camera y SCAN_INDICES. Retorna en el primer frame válido y libera cada sondeo; no duplica apertura ni preview.
5. **src.main:** sin CLI prueba índices 0–4 en orden, usa la primera funcional y se detiene. No muestra lista/selector ni solicita input. Funciona con camera_index auto o entero sin editar JSON. Si no hay cámara, muestra un error con diagnostics --scan.
6. **src.main --camera:** prioridad absoluta. Abre directamente N sin búsqueda previa. Si falla, no cambia a otro índice; conserva el fallback existente de backends para ese mismo N. No escribe JSON.
7. **src.main_seleccionar_camera:** archivo intacto; recorre todo el rango, lista candidatos y permite escoger cuando hay varias cámaras. Comparte el mismo loop de preview, sin YOLO/ByteTrack.
8. **Archivos modificados:** src/camera.py, src/main.py, tests/test_preview_modes.py, tests/test_multicamara.py, README.md, docs/03a_seleccion_multicamara.md, docs/resultados_pruebas.md y docs/validacion_tecnica.md. Nuevo: REPORTE_CAMERA_AUTOFIRST.md. Configuraciones, selector y módulos IA intactos.
9. **Tests nuevos:** 12 casos para primer índice, parada temprana, fallo de 0 y éxito de 1, rango compartido, ausencia de stdin, entero histórico, CLI sin sondeo, índice 99 sin fallback, primer frame fallido, Ctrl+C, reapertura fallida y ausencia de búsqueda por frame. Suite de preview: 31/31 OK con dobles explícitos.
10. **Tests previos:** los 140 tests previos se conservan/adaptan al nuevo contrato. H1/H2/H3 e integración intactos. La comprobación suplementaria pasó 136/136 antes y 148/148 después con OpenCV simulado; cuatro pruebas ByteTrack real siguen pendientes.
11. **Compileall:** código 0 antes y después.
12. **Pip check:** código 0 antes y después; comprueba consistencia de lo instalado, no que esté instalado todo requirements. Faltan OpenCV y bibliotecas IA.
13. **Unittest:** suite ordinaria con código 1 por cinco errores de importación/setup (sin dependencias), ya presentes en baseline. Ahora define 152 tests; no se afirma aprobación completa. Diagnostics normal/scan también devuelve 1 por falta de cv2. Imports y ayuda de los cuatro comandos pasan. Entorno Linux/Python 3.12.14; objetivo Windows/Python 3.13.15 pendiente. La instalación previa de esta sesión fue bloqueada por la red.
14. **Regresión H1:** webcam/OpenCV únicamente, mismo loop; AUTO-FIRST y FORCED tienen pruebas de lógica, cierre y recursos. Sin IA ni selector en src.main.
15. **Regresión H2:** detect.py, detector.py y detection.json idénticos; lógica simulada pasa. Inferencia real pendiente en este entorno.
16. **Regresión H3:** track.py, tracker.py, tracking.json y YAML idénticos; sin cambios de CPU/CUDA, IDs, trails, thresholds o bottom-center. Integración real pendiente.
17. **Recursos:** sondeos liberados entre índices/backends y antes de la sesión final; se prueba Ctrl+C y errores. Una reapertura fallida no reinicia búsqueda. Cierre de preview conserva finally/destroyAllWindows. No se añaden guardados de imágenes/videos.
18. **README diff:** solo 2 líneas sustituidas (título y descripción breve); sin reordenar, reformatear ni reconstruir.
19. **Requirements diff:** ninguno; no dependencias nuevas. .gitignore intacto. Sin commit, push o cambios de remotes; .vscode y logs/.gitkeep conservados.
20. **Pruebas físicas pendientes:** AF-01–AF-08 en docs/resultados_pruebas.md: PC con una cámara, laptop con dos, selector, override, índice ausente, cero cámaras, liberación y regresión detect/track. No se afirma que DroidCam se haya probado aquí. Los índices pueden variar por equipo/backend; los drivers pueden tardar en responder.
21. **Comandos exactos:** desde la raíz con el entorno virtual activado. Mantener camera_index auto; 0/1 son ejemplos de índices y no identifican marcas.

    ```powershell
    # AUTO-FIRST: primera funcional, sin preguntar
    python -m src.main

    # FORCED: índice explícito, sin búsqueda ni fallback a otro índice
    python -m src.main --camera 0
    python -m src.main --camera 1

    # INTERACTIVE: escaneo completo y selección
    python -m src.main_seleccionar_camera

    python -m src.detect
    python -m src.track
    python -m src.diagnostics
    python -m src.diagnostics --scan

    python -m compileall src tests
    python -m pip check
    python -m unittest discover -s tests -v
    ```

Si faltan dependencias en el equipo de prueba, instalar el requirements existente con `python -m pip install -r requirements.txt`. Devolver salidas de tests/diagnósticos y resultado de AF: cámara utilizada, selector/input sí/no, override, errores y liberación. Esta entrega no implementa Hito 4 ni los ajustes pendientes de rendimiento/tracking.
