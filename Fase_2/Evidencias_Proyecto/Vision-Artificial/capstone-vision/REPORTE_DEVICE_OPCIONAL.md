**Reporte final — capstone-vision: dispositivo opcional y preferencia local**

Fecha: 9 de octubre de 2026. Fuente de verdad: ZIP adjunto actual y encargo adjunto `Texto pegado(2).txt`. La recuperación anterior se utilizó como contexto; las comprobaciones se hicieron sobre el código real del ZIP.

1. **ESTADO GENERAL.** Implementación completa y validación técnica aprobada: 177/177 pruebas, compileall, pip check, imports y diagnostics. Se comprobaron inferencias reales CPU con YOLO26n y ByteTrack sobre frames sintéticos. La aceptación física en Windows, webcam y NVIDIA permanece pendiente. No se implementó Hito 4.

2. **CAUSA ORIGINAL CONFIRMADA.** El ZIP distribuía `config/detection.json` con `device: cuda:0`. El selector anterior escribía ahí y ambos pipelines exigían esa GPU. Recrear `.venv` conservaba el JSON; en un entorno sin CUDA utilizable se abortaba antes de cargar YOLO. La captura DSHOW/MSMF era independiente.

3. **SOLUCIÓN IMPLEMENTADA.** Base compartida CPU; selector opcional que escribe exclusivamente una preferencia local; resolución única antes de cargar el modelo; fallback temporal cuando una GPU local no supera la validación existente. Se conservan los parámetros del modelo y la cámara.

4. **ARQUITECTURA FINAL DE DISPOSITIVO.** `src/devices.py` contiene `load_device_preference()`, `resolve_effective_device()` y `DeviceResolution`. El punto compartido `load_person_model()` devuelve el modelo y la resolución a `PersonDetector` y `PersonTracker`. No hay resolvers distintos para detect/track ni consultas CUDA por frame.

   | Concepto | Ubicación o comportamiento |
   | --- | --- |
   | Configuración base | `config/detection.json`, versionada, CPU en la entrega |
   | Preferencia personal | `config/device.local.json`, opcional, solo en la copia de trabajo de ese computador |
   | Precedencia | Preferencia local válida → base |
   | Estado conservado | base, preferencia local, efectivo, fallback y avisos |
   | Inferencia/overlay | Siempre usan el dispositivo efectivo |

5. **COMPORTAMIENTO SIN DEVICE_SELECTOR.** La ausencia de `device.local.json` es normal. Detect y track usan CPU directamente, sin menú, warning de preferencia ausente, creación de archivo local ni cambio del JSON base. Continúan siendo necesarios PyTorch funcional, los pesos oficiales y una cámara/escritorio para los visores. Los avisos existentes de ByteTrack se conservan.

6. **COMPORTAMIENTO CON CPU SELECCIONADA.** El comando existente guarda `{"device": "cpu"}` localmente. Ambas aplicaciones recuerdan CPU entre ejecuciones, sin preguntar. Base y cámara permanecen intactas.

7. **COMPORTAMIENTO CON GPU SELECCIONADA.** PyTorch determina los dispositivos disponibles. La GPU elegida debe pasar disponibilidad, cantidad, índice, operación pequeña con tensor, sincronización y resultado. Se guarda su identificador exacto `cuda:N` localmente; ambas inferencias lo utilizan en siguientes ejecuciones si sigue siendo utilizable. No hay reglas por nombre RTX/GTX.

8. **FALLBACK GPU → CPU.** Una preferencia local CUDA no disponible, fuera de rango o que falla en la prueba ligera produce warning y CPU para esa sesión. El warning identifica la preferencia y sugiere `python -m src.device_selector`. No se reescribe la selección; si CUDA vuelve a funcionar, la próxima ejecución puede volver a usarla. Esto ocurre antes de cargar pesos. No se reintenta silenciosamente en CPU una inferencia que falla después de inicializarse. Una GPU colocada manualmente en la configuración base conserva validación estricta: el fallback solicitado se aplica a la preferencia personal.

9. **DEVICE.LOCAL.JSON.** Contiene únicamente `device`. Acepta UTF-8 y BOM. Ausencia es normal; JSON roto, campo ausente, formato/tipo incorrecto, campos extra o lectura inaccesible producen warning y uso de la base, conservando el archivo. El usuario puede repararlo explícitamente mediante el selector. No se incluye un archivo local activo ni un ejemplo activo en la entrega.

10. **DETECTION.JSON FINAL.** Único cambio: `cuda:0` → `cpu`. Se conservaron todos los demás valores y tipos del ZIP original:

    ```json
    {
      "model": "yolo26n.pt",
      "confidence_threshold": 0.65,
      "iou_threshold": 0.7,
      "image_size": 640,
      "device": "cpu",
      "person_class_id": 0,
      "show_confidence": true
    }
    ```

11. **.GITIGNORE.** Única línea nueva: `config/device.local.json`. No se ignoran `detection.json` ni `camera.json`. La exclusión evita agregar normalmente la preferencia personal; al armar ZIP también se filtra explícitamente porque `.gitignore` no filtra archivos ZIP por sí solo.

12. **DEVICE_SELECTOR.** Conserva `python -m src.device_selector`, opciones CPU/GPU, índices, nombres, cancelación, manejo de entrada y validación fuerte. Usa temporal en el mismo directorio, flush/fsync, validación, `os.replace()` y recarga del destino. Fallos previos al reemplazo conservan el archivo anterior y limpian temporales. Si falla el import de PyTorch, termina con mensaje controlado antes del menú y sin guardar. No instala dependencias ni cambia Windows.

13. **DIAGNOSTICS.** Distingue base, preferencia local, dispositivo efectivo, fallback, build CUDA, disponibilidad y cantidad/nombres GPU. Reutiliza el resolver y, para una GPU local, su prueba ligera, sin instanciar modelos ni cargar pesos. No guarda selecciones ni pregunta. Si PyTorch no importa, informa que el dispositivo efectivo no puede comprobarse y que CPU también requiere PyTorch funcional. Se conserva la inicialización de ajustes de Ultralytics que ya hacía el diagnóstico; esos ajustes generados se excluyen de la entrega.

14. **CAMERA_SELECTOR / REGRESIÓN.** `src/camera_selector.py`, `src/camera.py` y `config/camera.json` permanecen idénticos byte a byte. Todas sus pruebas pasan. Se conservan persistencia, índices y backends; no se creó `camera.local.json`, auto-first ni otro selector.

15. **SRC.MAIN / REGRESIÓN.** Archivo idéntico byte a byte. Sigue siendo cámara/OpenCV/preview, sin importar PyTorch, cargar YOLO/ByteTrack, leer preferencia de inferencia ni validar CUDA. Se verificaron imports ligeros y ejecución de su entrada con preview simulado.

16. **SRC.DETECT / REGRESIÓN.** Solo se cambió la lectura del dispositivo mostrado en consola y overlay para usar `detector.config` efectivo. Hito 2 conserva modelo, person, confianza, IoU, imgsz, cajas, métricas y recursos. El dispositivo que recibe `predict()` se resuelve en la carga compartida.

17. **SRC.TRACK / REGRESIÓN.** Solo se cambió la lectura del dispositivo mostrado en consola y overlay para usar `tracker.config` efectivo. En `src/tracker.py` únicamente se recibe la resolución del cargador compartido y se aplica a la copia de configuración. El algoritmo, llamada `model.track()`, ByteTrack, persistencia, IDs, trails, métricas y asociación permanecen intactos.

18. **ARCHIVOS NUEVOS.** `tests/test_device_optional.py` (28 casos nuevos) y este `REPORTE_DEVICE_OPCIONAL.md`. No hay otro selector ni configuración local distribuida.

19. **ARCHIVOS MODIFICADOS.** `.gitignore`, `config/detection.json`, `README.md`, `docs/seleccion_dispositivo.md`, `docs/resultados_pruebas.md`, `src/devices.py`, `src/device_selector.py`, `src/detector.py`, `src/diagnostics.py`, `src/detect.py`, `src/track.py`, `src/tracker.py`, `tests/test_device_selector.py`, `tests/test_hito2.py` y `tests/test_hito3.py`.

20. **ARCHIVOS DELIBERADAMENTE SIN MODIFICAR.** Requirements, cámara, selector de cámara, main, config.py, tracking.json, YAML ByteTrack, pruebas H1, pruebas de cámara, integración real ByteTrack, reportes H2/H3, documentos anteriores ajenos al dispositivo y ajustes VS Code. Se compararon bytes con el ZIP fuente. Ningún peso/modelo se cambió ni se incluye en el ZIP.

21. **README DIFF.** Cambios limitados a instalación CPU/GPU y selección de dispositivo: CPU sin pasos adicionales, wheels CPU explícitos opcionales, CUDA manual/opcional, preferencia local, fallback temporal y nota breve WinError 4551/App Control. No se reorganizó ni reformateó el README; se conservaron los finales de línea y se verificó el resto del documento intacto.

22. **REQUIREMENTS DIFF.** Vacío, comprobado byte a byte. Se conservaron `opencv-python==4.14.0.94`, `ultralytics==8.4.163`, `torch==2.14.0`, `torchvision==0.29.0` y `lap==0.5.12`. No se agregaron dependencias al proyecto.

23. **TESTS NUEVOS.** Cubren ausencia local, CPU, GPU válida, GPU ausente, índice inválido, fallo de tensor/kernel/sincronización/resultado, recuperación futura CUDA, archivo corrupto/campos/tipos/BOM/lectura, base estricta, resolver compartido, estado preferencia/efectivo, main independiente, guardado local inicial, base/cámara intactas, fallos de import/escritura, diagnóstico y exclusión Git. GPU y cámara se simulan; no se exigen físicamente para unit tests.

24. **TESTS ACTUALIZADOS.** Los casos previos de persistencia apuntan ahora al archivo local. Las expectativas de aborto por GPU local se sustituyeron por fallback con conservación del archivo y liberación de recursos. Se conserva el rechazo al guardar GPU no utilizable. Los fixtures H2/H3 ignoran la preferencia personal real del equipo para seguir probando sus pipelines CPU de manera aislada. No se eliminaron métodos de prueba anteriores.

25. **RESULTADO UNITTEST.** Antes de instalar dependencias faltaban cv2/Ultralytics/PyTorch: el intento inicial corrió 39 pruebas con 2 fallos y 6 errores de entorno. Tras instalar las dependencias exactas en un entorno aislado, el ZIP original pasó 149/149. La versión final pasó 177/177 en 4.055 s. Un intento intermedio se interrumpió por un fixture de import de PyTorch no adaptado al menú nuevo; se corrigió y la suite completa pasó. No queda un test fallido pendiente. ByteTrack real se verifica con cajas sintéticas en las cuatro pruebas de integración existentes.

26. **RESULTADO COMPILEALL.** `python -m compileall src tests`: código 0, antes y después de los cambios.

27. **RESULTADO PIP CHECK.** Código 0: `No broken requirements found.` en el entorno final aislado. El primer pip check también pasó, pero no certificaba instalación de paquetes que aún faltaban; por eso se instalaron y comprobaron después.

28. **RESULTADO DIAGNOSTICS.** Código 0: base CPU, local no configurada, efectivo CPU, fallback False; torch 2.14.0+cpu, torchvision 0.29.0+cpu, CUDA build None, disponibilidad False y 0 GPUs. Se comprobaron las versiones exactas restantes. También se ejecutó con preferencia local cuda:0 y PyTorch CPU real: código 0, fallback True, efectivo CPU y archivo intacto. El diagnóstico del ZIP original en ese mismo entorno devolvía 1 por su base cuda:0. Los seis imports solicitados devolvieron 0.

29. **VALIDACIÓN CPU REAL.** En una copia temporal sin selector ni archivo local se cargaron los pesos oficiales `yolo26n.pt`. `PersonDetector.detect()` y `PersonTracker.track()` ejecutaron inferencia real CPU sobre frame negro sintético 640×480 y no crearon preferencia local. Se repitieron con preferencia cuda:0 no disponible y con archivo local corrupto; ambos pipelines continuaron CPU y conservaron el archivo. El selector CPU se ejecutó con PyTorch real y conservó base/cámara. No fue una prueba de personas ni de webcam. Los comandos gráficos main/detect/track devolvieron 1 controlado por ausencia de sesión gráfica, antes de abrir cámara.

30. **VALIDACIÓN CUDA REAL.** No realizada. No hay GPU física CUDA disponible. Descubrimiento, selección, prueba fuerte, índice exacto y propagación GPU se comprobaron mediante mocks; no certifican una RTX 5060 ni GTX 1650.

31. **LIMITACIONES.** Verificación en Linux x86_64 / Python 3.12.14, no en Windows/Python 3.13.15. Sin escritorio ni webcam. No se certifican precisión, tracking de personas, FPS, drivers, políticas App Control ni memoria suficiente GPU para inferencia prolongada. Un PyTorch roto no puede repararse mediante fallback. La configuración base inválida conserva error. No se cambió el contrato de un fallo posterior de inferencia.

32. **PRUEBAS FÍSICAS PENDIENTES RTX 5060.** DEV-04: con import torch funcional, CUDA disponible y GPUs > 0, elegir GPU; comprobar preferencia local, diagnóstico efectivo CUDA y ambos visores en cuda:0, nuevas ejecuciones y liberación. La validación histórica informada por el usuario no sustituye esta prueba de la nueva entrega.

33. **PRUEBAS FÍSICAS PENDIENTES GTX 1650.** DEV-05: seguir el mismo flujo basado en disponibilidad real de PyTorch. No se marca OK hasta prueba física. No se creó una receta ni código diferente por modelo comercial.

34. **PRUEBA WINDOWS APP CONTROL.** El usuario informó WinError 4551 al importar el build CUDA cu132 por bloqueo de torch.dll y posterior import CPU 2.14.0+cpu funcional, sin CUDA. Se documentó como antecedente informado, sin reproducción local. Los mensajes controlados por fallo de import se probaron con errores simulados. DEV-07, detect/track con build CPU en ese notebook, permanece pendiente. No se tocaron mecanismos de seguridad, DLL externas ni políticas.

35. **CONTENIDO DEL ZIP.** `capstone-vision-device-opcional.zip` contiene la carpeta `capstone-vision/` completa: código, configuraciones compartidas, documentación, requisitos, pruebas, ajustes VS Code, `.gitignore`, `logs/.gitkeep` y este reporte. Total: 40 archivos. Se excluyen entornos, caches, bytecode, pesos, runs, ajustes Ultralytics generados, logs innecesarios y medios/temporales. Se comprobó integridad del ZIP y equivalencia byte a byte de cada archivo empaquetado con la versión validada.

36. **DEVICE.LOCAL.JSON NO ESTÁ EN EL ZIP.** Confirmado mediante inspección de todos los nombres del archivo. La exclusión es explícita y el directorio de entrega no contiene una preferencia local. `detection.json` empaquetado contiene CPU y el resto de los parámetros originales.

37. **ESTADO GIT.** No se hizo commit, push, cambio de branch, remote ni acción destructiva. El ZIP fuente no incluye `.git`, de modo que no se inventa un estado remoto. El usuario realizará sus operaciones con GitHub Desktop después de probar físicamente.

38. **COMANDOS EXACTOS PARA EL USUARIO.** Desde la carpeta `capstone-vision` de la entrega. Si el entorno existente funciona, se puede conservar junto a los pesos; el ZIP no los reemplaza. Para una instalación nueva:

    ```powershell
    py -3.13 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    python -m pip check
    ```

    Uso normal, un visor a la vez; cerrar con q/ESC antes del siguiente:

    ```powershell
    python -m src.main
    python -m src.detect
    python -m src.track
    ```

    Cámara, cuando necesites seleccionarla o cambiarla:

    ```powershell
    python -m src.camera_selector
    ```

    CPU/GPU opcional y diagnóstico:

    ```powershell
    python -m src.device_selector
    python -m src.diagnostics
    ```

    Comprobaciones:

    ```powershell
    python -m compileall src tests
    python -m pip check
    python -m unittest discover -s tests -v
    ```

    Wheels CPU explícitos opcionales, conservando las versiones del proyecto:

    ```powershell
    python -m pip install torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cpu
    python -m pip install -r requirements.txt
    python -m pip check
    ```

    CUDA opcional: procedimiento proporcionado y conservado; no ejecutado sobre NVIDIA en esta validación:

    ```powershell
    python -m pip uninstall torch torchvision -y
    python -m pip install torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cu132
    python -m pip check
    python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.device_count())"
    ```

    Solo después de que el import funcione, CUDA aparezca disponible y haya GPUs utilizables:

    ```powershell
    python -m src.device_selector
    ```

39. **SIGUIENTE PASO.** Aplicar esta entrega y completar DEV-01/02 con cámara real sin ejecutar el selector de dispositivo. Si el índice actual no corresponde a la cámara de ese computador, utilizar el camera_selector existente. Después comprobar selector CPU, fallback, RTX 5060 y GTX 1650 según corresponda, registrar resultados físicos y recién entonces hacer commit/push manual. Hito 4 sigue pendiente y no se adelantó.
