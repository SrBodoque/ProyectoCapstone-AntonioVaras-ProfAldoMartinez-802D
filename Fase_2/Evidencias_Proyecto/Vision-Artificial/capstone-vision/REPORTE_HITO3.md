# REPORTE FINAL — HITO 3

1. **Estado Hito 3.** Implementado sobre el ZIP real adjunto y validado automáticamente en Linux. **Aceptación física pendiente** en Windows/Python 3.13.15/webcam. No se declara aprobado el hito físico.

2. **ZIP final.** `capstone-vision-hito3.zip`, carpeta raíz única `capstone-vision/`, proyecto completo limpio. Se verifican CRC y extracción antes de entregar. El reporte está incluido.

3. **Implementación.** `python -m src.track`: YOLO26n + ByteTrack explícito, CPU, una carga de modelo, persistencia, IDs temporales, confianza, trails limitados y métricas diferenciadas. Reutiliza cámara y carga/validación del modelo. Sin zonas, línea, IN/OUT ni conteo operacional.

4. **Árbol real.** Se incluyen 31 archivos fuente/documentales. Tabla de todas las rutas relativas a `capstone-vision/`:

| Ruta                              | Estado     |
| --------------------------------- | ---------- |
| `.gitignore`                      | Conservado |
| `.vscode/extensions.json`         | Conservado |
| `.vscode/settings.json`           | Conservado |
| `README.md`                       | Modificado |
| `REPORTE_HITO2.md`                | Conservado |
| `REPORTE_HITO3.md`                | Nuevo      |
| `config/bytetrack_capstone.yaml`  | Nuevo      |
| `config/camera.json`              | Conservado |
| `config/detection.json`           | Conservado |
| `config/tracking.json`            | Nuevo      |
| `docs/00_contexto_vision.md`      | Conservado |
| `docs/01_entorno_y_webcam.md`     | Conservado |
| `docs/02_deteccion_personas.md`   | Conservado |
| `docs/03_tracking_bytetrack.md`   | Nuevo      |
| `docs/resultados_pruebas.md`      | Modificado |
| `docs/validacion_tecnica.md`      | Modificado |
| `logs/.gitkeep`                   | Conservado |
| `requirements.txt`                | Modificado |
| `src/__init__.py`                 | Conservado |
| `src/camera.py`                   | Conservado |
| `src/config.py`                   | Modificado |
| `src/detect.py`                   | Conservado |
| `src/detector.py`                 | Modificado |
| `src/diagnostics.py`              | Modificado |
| `src/main.py`                     | Conservado |
| `src/track.py`                    | Nuevo      |
| `src/tracker.py`                  | Nuevo      |
| `tests/test_hito1.py`             | Conservado |
| `tests/test_hito2.py`             | Conservado |
| `tests/test_hito3.py`             | Nuevo      |
| `tests/test_hito3_integration.py` | Nuevo      |

5. **Archivos nuevos.** `REPORTE_HITO3.md`, `config/bytetrack_capstone.yaml`, `config/tracking.json`, `docs/03_tracking_bytetrack.md`, `src/track.py`, `src/tracker.py`, `tests/test_hito3.py`, `tests/test_hito3_integration.py`.

6. **Archivos modificados.** `README.md`, `docs/resultados_pruebas.md`, `docs/validacion_tecnica.md`, `requirements.txt`, `src/config.py`, `src/detector.py`, `src/diagnostics.py`. Cambios incrementales: configuración y diagnóstico ampliados, carga de modelo compartida, documentación añadida y dependencia lap declarada.

7. **Deliberadamente conservados.** `.gitignore`, `.vscode/extensions.json`, `.vscode/settings.json`, `REPORTE_HITO2.md`, `config/camera.json`, `config/detection.json`, `docs/00_contexto_vision.md`, `docs/01_entorno_y_webcam.md`, `docs/02_deteccion_personas.md`, `logs/.gitkeep`, `src/__init__.py`, `src/camera.py`, `src/detect.py`, `src/main.py`, `tests/test_hito1.py`, `tests/test_hito2.py`. Comparación byte a byte contra el ZIP. README y registros físicos originales también se conservaron completos dentro de sus ampliaciones.

8. **Dependencias.** Cuatro versiones originales sin cambio. Se añade `lap==0.5.12`: el matching integrado lo requiere y requirements previo no lo instalaba. No es un paquete ByteTrack externo. PyYAML ya es transitivo. Todo se instala desde requirements, sin autoinstalación al ejecutar tracking.

9. **Versiones.** Entorno de revisión: Python 3.12.14 Linux x86_64; OpenCV 4.14.0.94/cv2 4.14.0; Ultralytics 8.4.163; torch 2.14.0+cu130; torchvision 0.29.0+cu130; lap 0.5.12; PyYAML 6.0.3. Objetivo Python 3.13.15 x64 Windows conservado, no ejecutado aquí. CUDA disponible False; se usa CPU. Runtimes GPU llegaron transitivamente con torch Linux, sin configuración CUDA manual. Wheel lap Windows cp313 x64 verificado.

10. **ByteTrack.** YAML cotejado con Ultralytics instalado: tracker_type bytetrack, high 0.25, low 0.10, new 0.25, buffer 30, match 0.80, fuse_score true. Sin campos adicionales requeridos ni cambios de optimización.

11. **Tracking.** `tracker_config=config/bytetrack_capstone.yaml`, `persist=true`, `show_track_id=true`, `show_trail=true`, `trail_length=30`. Persist debe mantenerse true; trail admite 1–300. Ruta relativa validada, parámetros del motor separados.

12. **Baseline H1 antes de cambios.** 16/16 tests OK, imports y compileall OK. Entorno original del servidor sin cv2: se investigó y resolvió instalando las versiones exactas antes de editar. No se atribuyó ese fallo de entorno al proyecto.

13. **Baseline H2 antes de cambios.** 32/32 tests OK, diagnostics código 0 y pip check sin conflictos en entorno aislado. Modelo/detección reales conservados; confianza real del ZIP **0.65**, no 0.50. Baselines físicos informados por el usuario no se sustituyen por mediciones sintéticas.

14. **Pruebas automáticas H3.** 38 nuevas pruebas de configuración/IDs/modelo/persistencia/privacidad/recursos/historial más 4 pruebas del BYTETracker real con cajas sintéticas. No descargan ni cargan pesos en la suite. Historial probado con 10 000 IDs sucesivos.

15. **Regresión H1.** 16/16 OK; main.py, camera.py y camera.json idénticos. Sigue siendo preview sin YOLO ni pesos. Webcam física pendiente de repetir en esta versión.

16. **Regresión H2.** 32/32 OK; detect.py idéntico, detect() sigue usando predict sin tracking. En inferencia real de muestra devolvió 4 detecciones person sin IDs. Extracción mínima de carga del modelo a función compartida.

17. **Compileall.** `python -m compileall src tests`: código 0.

18. **Pip check.** Código 0, `No broken requirements found` después de instalar lap.

19. **Tests.** **90/90 OK**: 16 H1 + 32 H2 + 38 H3 + 4 integración real ByteTrack.

20. **Diagnostics.** Código 0; conserva datos anteriores y agrega YAML, parámetros, persistencia, trail y dependencia/import ByteTrack sin descargar pesos. Scan 0–4: sin webcam disponible. Los tres visores devuelven 1 con mensaje claro de falta de sesión gráfica; no es prueba física exitosa.

21. **No doble inferencia.** Revisión de código y mocks: una llamada model.track por frame y ninguna llamada adicional a predict/detect. Instrumentación con wraps del método real predictor.inference: **60 llamadas para 60 frames** posteriores al arranque. Misma instancia ByteTrack y un callback de tracking por evento; no se acumulan callbacks.

22. **Rendimiento medido.** Imagen de ejemplo del paquete repetida 60 veces en CPU: 4 IDs estables; media YOLO 40.8 ms, procesamiento completo 46.5 ms, rango 27.4–198.8 ms. Inicialización 1080.6 ms. Es una prueba de API sin captura/GUI y con carga concurrente de revisión, no benchmark controlado. **FPS webcam H3 pendiente**; no se compara directamente con los 20–24 FPS físicos H2 del usuario.

23. **Errores encontrados.** Dependencias ausentes en servidor; lap faltante en instalación original; un caso del diagnóstico con excepción sin nombre falló en test. En el script de comprobación se detectaron además dos errores de instrumentación: hook sobre objeto no usado por el predictor y conteo conjunto de callbacks predeterminados/tracking.

24. **Correcciones.** Entorno aislado con versiones fijadas, lap declarado, excepción de dependencia ausente tratada específicamente y mensaje claro. Instrumentación corregida para observar inferencia real y solo callbacks del tracker. Reejecución exitosa. No se cambió el detector para ocultar cama/mochila.

25. **Limitaciones.** Confianza 0.65 conservada filtra antes de ByteTrack y deja sin candidatos su segunda asociación de baja confianza 0.10–0.25. Se informa expresamente; umbrales no se confunden. IDs pueden perderse o intercambiarse; no representan identidad. Buffer mide frames, no segundos. La API puede omitir detecciones sin confirmar. Sin validación física Windows/webcam ni promesas de 30 FPS.

26. **Privacidad.** Frames solo en memoria, sin imágenes/video/audio/cloud/ReID. Sin archivos nuevos ni runs durante la prueba local y **0 intentos de conexión** con sockets bloqueados después de disponer de dependencias/pesos. Se conservan opciones save desactivadas. No se aplican reglas por objeto, posición o inmovilidad.

27. **Git.** ZIP sin .git. Se compararon bytes y diferencias contra el adjunto. Sin git init, alteración de historia/remotos, commit ni push. .gitignore original ya cubría los artefactos descartables.

28. **Limpieza.** Entorno de pruebas fuera del entregable; se eliminan cachés, pyc, pesos de comprobación y settings generados del árbol final. Se excluyen runs, medios y temporales. Se conserva logs/.gitkeep, VS Code, fuente, configuraciones y documentación.

29. **Pruebas físicas pendientes.** Las 28 fichas A–AB en docs/resultados_pruebas.md: H1/H2/H3, quietud/movimiento/distancias/perfil/espalda, oclusiones, salida/reentrada, dos personas/cruce, cama/mochila/combinaciones, ejecución prolongada/memoria, q/ESC/X/Ctrl+C, liberación y privacidad. Todas **PENDIENTES**; las simulaciones no las aprueban.

30. **Comandos exactos.** Extraer el ZIP y aplicar el contenido de su única carpeta sobre el proyecto actual conservando .venv y pesos locales. Abrir terminal en la raíz donde están src y requirements. Cerrar cada visor antes de iniciar el siguiente:

```powershell
.\.venv\Scripts\Activate.ps1
python --version
python -m pip install -r requirements.txt
python -m pip check
python -m compileall src tests
python -m unittest discover -s tests -v
python -m src.diagnostics
python -m src.main
python -m src.detect
python -m src.track
python -m src.main
```

La última apertura de main comprueba liberación tras cerrar track. Si no puedes activar, reemplaza python por `.\.venv\Scripts\python.exe`. Solo si falta entorno, comprueba primero Python 3.13.15 y crea con `py -3.13 -m venv .venv`. Escaneo opcional: `python -m src.diagnostics --scan`. En el repositorio del usuario, revisar `git status --short` y `git diff` después de aplicar los archivos; no se requiere push.

31. **Resultados a devolver.** Salidas de pip check/tests/diagnostics; FPS H3 y tiempos YOLO/procesamiento; ID de persona quieta y cambios en movimiento; oclusiones y salida/reentrada; dos personas, cruces e ID switches; cama, mochila, persona+cama y persona con mochila; duración, memoria, crashes, cierres y liberación de webcam. Basta texto técnico, sin enviar imágenes de personas.

32. **Siguiente hito.** Calibración espacial: Zona B + Zona A + línea final. **No implementado**. Primero completar la caracterización física de H3.

### Conclusión Hito 3

El seguimiento temporal mediante ByteTrack presentó un comportamiento estable durante movimiento normal de una persona.

Mientras la persona permanece visible, el sistema mantiene de forma consistente el mismo track_id durante desplazamientos, cambios de distancia y visibilidad parcial.

Al abandonar parcialmente el campo de visión, incluyendo pruebas con aproximadamente medio cuerpo fuera del frame, el identificador temporal se mantuvo correctamente.

En situaciones de oclusión o salida completa del campo visual, la conservación del ID depende del tiempo durante el cual la persona permanece fuera de detección. Reapariciones rápidas pueden recuperar el mismo track_id, mientras que ausencias más prolongadas generan correctamente un nuevo identificador temporal.

Este comportamiento se considera aceptable debido a que los IDs de ByteTrack representan trayectorias temporales y no identidad permanente de personas.

Durante pruebas adversariales con un umbral de detección reducido a 0.30 se generaron tracks adicionales correspondientes a objetos del entorno. Como consecuencia, se observaron saltos numéricos entre track_id, por ejemplo desde ID 23 a ID 26.

Estos saltos no representan pérdida de personas ni conteos adicionales. Los track_id son identificadores internos y no tienen relación directa con el número de personas que ingresan o salen.

El threshold reducido se utilizó exclusivamente con fines experimentales. La configuración baseline deberá restaurarse al valor normal del proyecto antes de continuar.

El falso positivo conocido asociado a una esquina de una cama continúa pudiendo generar un track en determinadas perspectivas. Esto confirma que ByteTrack realiza seguimiento de detecciones entregadas por YOLO, pero no valida semánticamente si el objeto corresponde realmente a una persona.

Esta limitación será mitigada en etapas posteriores mediante delimitación espacial y validación de trayectoria, donde un evento IN/OUT requerirá una secuencia válida de movimiento y cruce.

El Hito 3 se considera funcionalmente apto para continuar con la calibración espacial, quedando las pruebas multipersona reales como validación adicional recomendada.
