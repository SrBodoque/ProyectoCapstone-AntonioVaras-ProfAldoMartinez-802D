# LimpIA — Normas de desarrollo de capstone-vision

## 1. Alcance y autoridad

Estas instrucciones se aplican a este directorio y sus descendientes.

Toda tarea debe respetar el alcance y las autorizaciones explícitas del equipo.
Una solicitud de análisis, diagnóstico o planificación no autoriza modificaciones.

No comenzar a programar hasta que el equipo apruebe el plan correspondiente.
Una autorización ya concedida cubre el alcance aprobado; no autoriza ampliaciones.

Las decisiones arquitectónicas importantes deben presentarse al equipo para
su revisión con Astra. No atribuirle revisiones ni aprobaciones no recibidas.

Si aparecen otras instrucciones aplicables, leerlas y conservar sus reglas.
No sobrescribir instrucciones existentes ni resolver contradicciones mediante
suposiciones: identificar el conflicto y solicitar aclaración.

## 2. Fuente de verdad técnica

- El código real del repositorio es la fuente de verdad de la implementación.
- Inspeccionar archivos, configuración, interfaces y pruebas antes de proponer cambios.
- Diferenciar implementación comprobada, comportamiento observado, documentación
  histórica e hipótesis.
- No asumir funcionalidades por nombres de archivos, informes o planes anteriores.
- No reconstruir hitos ni recuperar versiones antiguas por suposiciones.
- Consultar historial o restaurar contenido únicamente cuando la tarea lo justifique
  y exista autorización para cualquier modificación.
- No afirmar que algo funciona en el equipo actual sin evidencia de ejecución.

## 3. Arquitectura existente que debe preservarse

Confirmar este mapa contra el código al comenzar cada tarea:

- `src/camera.py`: apertura, consulta y liberación de cámara.
- `src/main.py`: preview de cámara.
- `src/detector.py`: carga del modelo y detección sobre frames en memoria.
- `src/detect.py`: ejecución y visualización de detección con cámara.
- `src/tracker.py`: detección y asociación integradas, resultados e historial visual.
- `src/track.py`: ejecución y visualización del tracking con cámara.
- `src/track_fast.py`, `src/track_recovery.py` y `src/track_botsort_reid.py`:
  puntos de entrada experimentales.
- `src/reid_diagnostics.py`: comprobaciones específicas del experimento ReID.
- `src/devices.py` y `src/device_selector.py`: resolución y selección CPU/CUDA.
- `src/camera_selector.py`: selección de cámara.
- `src/config.py`: carga y validación de configuración.
- `tests/`: pruebas unitarias e integraciones existentes.

Preservar los contratos de `PersonDetector`, `PersonTracker`,
`FrameDetections`, `FrameTracks`, `Track` y `TrackHistory`.

`PersonTracker.track()` ya incluye detección: no agregar una llamada previa a
`PersonDetector.detect()` al mismo flujo sin justificación técnica y aprobación.

Los IDs son temporales. `TrackHistory` sirve para visualización y no demuestra
conteo ni identidad personal.

No asumir que existen calibración espacial, máquina de estados IN/OUT,
procesamiento MP4 o integración con Django: comprobar su implementación real.

## 4. Protección de funcionalidades y modularidad

- No romper funcionalidades existentes.
- Preservar cámara, detección, tracking, selección de cámara y selección CPU/GPU.
- Considerar protegidos los módulos existentes, sus interfaces y configuraciones.
- No modificarlos salvo necesidad técnica demostrable.
- Antes de intervenirlos, explicar el motivo, las alternativas, el impacto y las
  pruebas de regresión; solicitar autorización explícita.
- Desarrollar funcionalidades nuevas preferentemente en módulos independientes.
- Reutilizar clases e interfaces existentes y separar responsabilidades.
- Evitar duplicar captura, inferencia, asociación, validación o resolución de dispositivo.
- No introducir dependencias innecesarias ni actualizar versiones por conveniencia.
- No realizar refactorizaciones generales, cambios cosméticos masivos ni cambios
  ajenos a la tarea.
- No editar paquetes instalados ni archivos de terceros.
- No eliminar pruebas ni debilitar expectativas para obtener un resultado aprobado.
  Los ajustes legítimos de pruebas deben corresponder a contratos aprobados.

## 5. Flujo obligatorio de trabajo

1. Inspeccionar las instrucciones, la rama, el estado del árbol y los cambios previos.
2. Revisar el código real y las dependencias implicadas.
3. Identificar archivos afectados, interfaces protegidas y riesgos de regresión.
4. Inspeccionar las pruebas existentes y sus posibles efectos secundarios.
5. Cuando el alcance lo permita, ejecutar las pruebas pertinentes como baseline.
   Si solo se autorizó análisis, no ejecutarlas y declarar el baseline pendiente.
6. Proponer un plan mínimo con archivos, comportamiento, pruebas y aceptación.
7. Solicitar autorización antes de implementar.
8. Implementar exclusivamente el alcance aprobado.
9. Ejecutar pruebas, corregir errores y repetir verificaciones.
10. Completar las tres validaciones finales establecidas en este documento.
11. Inspeccionar el estado y el diff final, incluidos cambios preparados y archivos nuevos.
12. Entregar un informe técnico con evidencia y limitaciones.

Si aparece la necesidad de ampliar el alcance o intervenir un módulo protegido
no incluido en la aprobación, detener esa parte y solicitar autorización adicional.

Preservar cambios previos del usuario. No revertirlos, sobrescribirlos ni incluirlos
como trabajo propio.

## 6. Pruebas y validación obligatorias

Toda funcionalidad nueva debe contar con pruebas reproducibles que cubran:

- Casos normales.
- Casos límite.
- Errores esperables.
- Liberación de recursos cuando corresponda.
- Regresión de las funcionalidades existentes relacionadas.

Usar las convenciones actuales de `unittest`, salvo cambio aprobado.
No introducir otro framework sin necesidad justificada y autorización.

Antes de implementar, definir qué batería será relevante y qué regresiones
deberán ejecutarse. La suite existente es la referencia de regresión; cualquier
exclusión debe quedar identificada y justificada.

### Tres validaciones finales

Después del último cambio en código, pruebas o configuración que pueda afectar
el comportamiento:

- Ejecutar la batería relevante al menos tres veces de forma independiente.
- Usar un proceso nuevo por ejecución y evitar estado residual entre pruebas.
- Registrar comando, intérprete, entorno, resultado, fallos, errores y omisiones.
- Exigir tres ejecuciones satisfactorias después de la última corrección.
- Reiniciar la serie si un nuevo cambio puede afectar los resultados.
- No ejecutar pruebas GPU concurrentes si ello introduce interferencias.

Las tres repeticiones no sustituyen cobertura: la batería también debe incluir
escenarios distintos y significativos.

### Interpretación de resultados

- No contar pruebas omitidas, no ejecutadas o resultados inventados como aprobados.
- Una ejecución con omisiones no acredita los requisitos omitidos.
- Los mocks validan contratos y comportamiento simulado; informarlos como tales.
- Cajas sintéticas con un tracker real validan esa integración, no la precisión
  visual sobre personas reales.
- Una simulación CUDA no acredita ejecución en GPU.
- Una inferencia aislada no acredita rendimiento sostenido ni robustez.
- Separar evidencia unitaria, integración real y aceptación física.
- No confundir checks de sintaxis o dependencias con pruebas funcionales.
- Corregir los errores detectados antes de declarar terminada la tarea.
- Si existe un fallo previo, documentarlo; no atribuirlo a la tarea sin evidencia
  ni ocultarlo como aprobado.
- Si un requisito no puede comprobarse, declararlo pendiente.
- Si persiste un bloqueo, explicar causa, evidencia e intervención necesaria.
  No instalar, descargar ni cambiar el entorno para resolverlo sin autorización.

## 7. Entorno local, GPU y privacidad

- Utilizar el entorno Python local existente y comprobar el intérprete utilizado.
- No recrear, actualizar, modificar ni versionar `.venv` sin autorización.
- No instalar ni desinstalar dependencias, actualizar requisitos o descargar modelos
  sin autorización explícita.
- Comprobar recursos locales antes de ejecutar rutas que puedan descargar pesos.
  No asumir que `YOLO_OFFLINE` impide todas las descargas.
- Aprovechar CUDA cuando corresponda y esté disponible; comprobar su funcionamiento
  real antes de declararlo validado.
- Registrar dispositivo solicitado y efectivo en pruebas de inferencia y rendimiento.
- No introducir fallback silencioso de GPU a CPU.
- Preservar el fallback existente con warning de `resolve_effective_device()`;
  cambiar ese contrato requiere aprobación.
- No presentar una ejecución CPU como validación GPU.
- No enviar videos, imágenes, fotogramas ni características de apariencia a
  servicios externos.
- Mantener inferencia y evaluación de material visual en el computador local.
- No activar guardado de imágenes, video, audio o vectores de apariencia sin
  autorización específica.
- No leer ni exponer credenciales innecesarias para la tarea.
- No modificar ni versionar credenciales o configuración personal, incluido
  `config/device.local.json`, sin autorización específica.
- No ejecutar selectores que guarden preferencias durante pruebas automatizadas.

Las pruebas pueden generar cachés y artefactos técnicos locales ignorados por Git
cuando el alcance permita su ejecución. Esto no autoriza modificar paquetes,
preferencias personales ni archivos funcionales. Revisar los efectos secundarios
de importaciones y herramientas antes de ejecutarlas.

Durante tareas de solo análisis, limitarse a operaciones de lectura.

## 8. Control de cambios y ramas

- Trabajar únicamente sobre la rama asignada y verificarla al comenzar.
- No modificar `main` ni `VisionArtificial`.
- Si la rama actual no es la asignada, detener las modificaciones y consultar.
- No realizar commits, push, merge, rebase, cambios de rama, restauraciones
  destructivas ni limpieza de archivos sin autorización explícita.
- No crear ramas o worktrees por iniciativa propia.
- Mantener los cambios limitados al alcance aprobado.
- Respetar los patrones existentes de `.gitignore`.
- No agregar pesos, datasets, videos, entornos, credenciales o preferencias locales
  a Git sin autorización específica.
- Inspeccionar `git diff`, el diff preparado y los archivos nuevos antes de entregar.
- Si Git no está disponible, informar la limitación; no afirmar que se revisó el diff.

Comandos de inspección habituales, desde la raíz del repositorio:

    git --no-optional-locks branch --show-current
    git --no-optional-locks status --short
    git --no-optional-locks diff
    git --no-optional-locks diff --cached
    git --no-optional-locks ls-files --others --exclude-standard

Inspeccionar también el contenido de los archivos nuevos relevantes:
`git diff` no muestra por sí solo archivos sin seguimiento.

## 9. Convenciones de pruebas del proyecto

Desde `capstone-vision`, utilizando el intérprete de `.venv` existente:

    .\.venv\Scripts\python.exe -m unittest discover -s tests -v
    .\.venv\Scripts\python.exe -m pip check

Confirmar primero que esa ruta existe; no crear el entorno si falta.
Si el entorno local está en otra ubicación, registrar y utilizar su ruta real.

El README también utiliza:

    .\.venv\Scripts\python.exe -m compileall src tests

`compileall` puede escribir bytecode. No ejecutarlo durante una auditoría de
solo lectura. Su resultado no sustituye pruebas funcionales.

Antes de ejecutar la suite completa, comprobar dependencias, pesos y efectos
secundarios de las integraciones. No descargar recursos para conseguir que pase.

Los comandos concretos y escenarios adicionales de cada tarea deben quedar
incluidos en el plan aprobado y en el informe final.

## 10. Criterios de entrega

Informar siempre, indicando “no aplica” o “no ejecutado” cuando corresponda:

1. Qué se implementó o qué se analizó.
2. Qué archivos se crearon y modificaron.
3. Qué módulos funcionales protegidos permanecieron intactos.
4. Qué pruebas se ejecutaron realmente y cuáles utilizaron simulaciones.
5. Los resultados individuales de las tres validaciones finales.
6. La evidencia de regresión.
7. Fallos, omisiones, bloqueos y requisitos pendientes.
8. Las limitaciones de la verificación y el hardware realmente utilizado.
9. Los comandos y recursos necesarios para reproducir las pruebas.
10. El resultado de la inspección final del estado y del diff.

No presentar resultados históricos como obtenidos durante la tarea actual.
No declarar la tarea completamente validada si quedan criterios obligatorios
sin comprobar.

En tareas documentales o de análisis, explicar por qué las pruebas funcionales
y las tres ejecuciones no aplican; no ejecutar inferencias innecesarias.

## 11. Control de hitos

- No comenzar un hito posterior sin autorización.
- No ampliar el alcance por iniciativa propia.
- No implementar anticipadamente MP4, lotes, informes, conteo o integración
  con Django por aparecer mencionados en una propuesta.
- No declarar completado un hito con criterios de aceptación incumplidos.
- Distinguir implementación terminada, validación automatizada y aceptación
  física pendiente.
- Ante dudas de alcance o decisiones arquitectónicas importantes, presentar
  evidencia y alternativas al equipo antes de modificar.

## 12. Cierre accionable y documentación

Terminar cada etapa con un informe breve, entendible y accionable que incluya:

1. Qué se implementó, en lenguaje sencillo.
2. Archivos exactos creados o modificados.
3. Comandos exactos para ejecutar lo desarrollado desde su directorio de trabajo.
4. Cómo comprobar visual o funcionalmente que funciona.
5. Resultados reales de pruebas automatizadas, incluidas las tres validaciones.
6. Limitaciones, omisiones y pruebas pendientes, separando aceptación humana.
7. Estado de Git y recomendación explícita de commit/push, sin ejecutarlos.

Cuando cambien comandos o funcionalidades, actualizar el README correspondiente.
Estas reglas complementan los criterios de entrega anteriores; no los sustituyen.

## 13. Protección permanente de datos locales

- Nunca eliminar ni sobrescribir videos, resultados, pesos, datasets, anotaciones,
  logs, calibraciones, configuraciones privadas o respaldos sin autorización explícita.
- No interpretar que un archivo es prescindible únicamente porque está ignorado
  por Git. `.gitignore` no respalda los datos.
- No ejecutar operaciones destructivas como `git clean`, `git reset --hard` o
  limpiezas masivas sin autorización expresa.
- Crear fixtures temporales exclusivos para pruebas y limitar su limpieza a los
  archivos que la propia prueba creó, preservando todos los recursos preexistentes.
