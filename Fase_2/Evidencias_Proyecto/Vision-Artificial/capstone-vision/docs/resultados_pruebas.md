# Pruebas de aceptación — equipo del usuario

Fecha: 17-09-2026
Equipo: Windows 10, versión 10.0.19045, AMD64
Webcam: celular mediante DroidCam por Wi‑Fi
Python: 3.13.15 x64
OpenCV: opencv-python 4.14.0.94
Configuración final: índice 0, 1280×720, 30 FPS, MSMF

Todas las pruebas están PENDIENTES. No equivalen a las pruebas simuladas del desarrollador. Ejecutar en PowerShell desde la raíz, tras instalar y activar .venv según README. Ejecutar una línea a la vez. Si hay un fallo, conservar el error completo y diagnosticar antes de avanzar.

## PRUEBA A — Versión Python

```powershell
python --version
python -c "import struct; print(struct.calcsize('P') * 8)"
```

Resultado esperado: Python 3.13.15 y arquitectura de proceso 64 bits.

Resultado obtenido: ****\_\_****

Estado: OK

Observaciones: ****\_\_****

## PRUEBA B — Entorno virtual

```powershell
python -c "import sys; print(sys.executable); print(sys.prefix != sys.base_prefix)"
```

Resultado esperado: Ruta del ejecutable dentro de .venv\Scripts\python.exe y True; mismo intérprete seleccionado en VS Code.

Resultado obtenido: ****\_\_****

Estado: OK

Observaciones: ****\_\_****

## PRUEBA C — OpenCV

```powershell
python -m src.diagnostics
python -m pip check
```

Resultado esperado: cv2 4.14.0; distribución opencv-python 4.14.0.94; configuración cargada y sin dependencias rotas.

Resultado obtenido: ****\_\_****

Estado: OK

Observaciones: ****\_\_****

## PRUEBA D — Índices de webcam

```powershell
python -m src.diagnostics --scan
```

Resultado esperado: Al menos un índice DISPONIBLE que entregue un frame. Configurar ese índice en camera.json si no es 0.

Resultado obtenido: ****\_\_****

Estado: OK

Observaciones: ****\_\_****

## PRUEBA E — Preview

```powershell
python -m src.main
```

Resultado esperado: Ventana con video en vivo, resolución real, FPS aproximados, índice y backend. Enfocar y cerrar con q.

Resultado obtenido: ****\_\_****

Estado: OK

Observaciones: ****\_\_****

## PRUEBA F — Estabilidad ≥30 segundos

```powershell
python -m src.main
```

Resultado esperado: Mantener ≥30 s. Imagen continua sin cierre ni congelamiento permanente. Revisar memoria del proceso en Administrador de tareas; registrar duración, FPS y memoria inicial/final. Cerrar con q.

Resultado obtenido: ****\_\_****

Estado: OK

Observaciones: ****\_\_****

## PRUEBA G — Cierre con q

```powershell
python -m src.main
```

Resultado esperado: Enfocar ventana y pulsar q minúscula. Retorno a PowerShell, ventana cerrada y mensaje de cámara liberada.

Resultado obtenido: ****\_\_****

Estado: OK

Observaciones: ****\_\_****

## PRUEBA H — Cierre con ESC

```powershell
python -m src.main
```

Resultado esperado: Enfocar ventana y pulsar ESC. Retorno a PowerShell y ventana cerrada.

Resultado obtenido: ****\_\_****

Estado: OK

Observaciones: ****\_\_****

## PRUEBA I — Liberación de webcam

```powershell
python -m src.main
```

Resultado esperado: Después de cada cierre, volver a abrir y cerrar; luego abrir Cámara de Windows desde Inicio. Imagen disponible. Cerrar Cámara de Windows antes de seguir.

Resultado obtenido: ****\_\_****

Estado: OK

Observaciones: ****\_\_****

## PRUEBA J — Cambios de configuración

```powershell
notepad .\config\camera.json
python -m src.main
```

Resultado esperado: Con app cerrada, cambiar resolución a 640×480 o índice si hay otra cámara. Consola muestra la nueva solicitud; registrar valor real, que puede diferir. Cerrar, restaurar configuración válida y repetir ejecución.

Resultado obtenido: ****\_\_****

Estado: OK

Observaciones: ****\_\_****

## PRUEBA K — Privacidad

```powershell
Get-ChildItem -Recurse -File | Where-Object { $_.FullName -notmatch "[\\/]\.venv[\\/]|[\\/]\.git[\\/]" -and $_.Extension -in ".jpg", ".jpeg", ".png", ".mp4", ".avi", ".mov", ".bmp", ".webp", ".npy" }
```

Resultado esperado: Ningún archivo visual generado por la aplicación. Ejecutar antes y después de las pruebas para comparar. Los paquetes instalados se excluyen. Revisar también que no aparezcan directorios de frames o dumps.

Resultado obtenido: ****\_\_****

Estado: OK

Observaciones: ****\_\_****

## Aprobación

Hito 1 aprobado explícitamente por el usuario: OK

Enviar salida completa del diagnóstico, pip check, índice/backend, resolución/FPS observados, duración y memoria de la prueba F, resultados G/H/I, cambio J y verificación K. No enviar imágenes del acceso ni de personas: bastan resultados técnicos.

## Comentarios

DroidCam fue detectada en el índice 0. DirectShow no consiguió abrir la
cámara virtual, pero MSMF funcionó correctamente. Se configuró MSMF de
forma explícita para evitar intentos y advertencias innecesarios.

El preview funcionó a 1280×720 y aproximadamente 30 FPS, sin marca de
agua. La aplicación permaneció estable, cerró correctamente con q y ESC,
liberó la cámara y permitió reaperturas inmediatas.

No se generaron imágenes, videos, capturas, frames almacenados ni logs
técnicos adicionales.

---

# HITO 2 - DETECCIÓN DE PERSONAS

Estado: **PENDIENTE DE PRUEBA FÍSICA DEL USUARIO**.

Los resultados anteriores pertenecen al Hito 1 y se conservan. Su frase inicial «Todas las pruebas están PENDIENTES» quedó desactualizada: las pruebas A–K figuran OK y el usuario aprobó el Hito 1. Esta nueva sección sí permanece pendiente; ninguna prueba simulada sustituye estos resultados.

Fecha: ****\_\_****
Equipo: ****\_\_****
CPU: ****\_\_****
GPU: ****\_\_****
Python: ****\_\_****
OpenCV: ****\_\_****
Ultralytics: ****\_\_****
PyTorch: ****\_\_****
torchvision: ****\_\_****
Modelo: yolo26n.pt
Resolución: ****\_\_****
Configuración detection.json: ****\_\_****
Cámara/backend y conexión: ****\_\_****

Ejecutar desde la raíz del módulo, con .venv activado y requirements actualizado. En caso de fallo conservar consola completa y no marcar aprobado. Copiar esta ficha para el segundo equipo.

## PRUEBA A — Regresión webcam sin IA

```powershell
python -m src.main
```

Resultado esperado: Mismo preview del Hito 1; cierre y reapertura normales.

Resultado obtenido: ****\_\_****

Estado: OK

Observaciones: ****\_\_****

## PRUEBA B — Diagnóstico IA

```powershell
python -m src.diagnostics
```

Resultado esperado: Versiones fijadas, configuración y CPU; CUDA informativa. Complementar con python -m pip check.

Resultado obtenido: ****\_\_****

Estado: OK

Observaciones: ****\_\_****

## PRUEBA C — Carga del modelo

```powershell
python -m src.detect
```

Resultado esperado: Descarga oficial si falta el checkpoint, carga una vez y apertura del visor. Tras descargarlo, cerrar y repetir sin Internet para comprobar carga/inferencia local.

Resultado obtenido: ****\_\_****

Estado: **PENDIENTE**

Observaciones: ****\_\_****

## PRUEBA D — Escena vacía

```powershell
python -m src.detect
```

Resultado esperado: 0 personas/frame en condiciones normales; registrar cualquier falso positivo.

Resultado obtenido: Coloque un ventilador con una toalla encima y lo detecta pero si no hay nada no registar nada

Estado: OK

Observaciones: Coloque un ventilador con una toalla encima y lo detecta

## PRUEBA E — Una persona

```powershell
python -m src.detect
```

Resultado esperado: Una caja person y confianza cuando una persona sea suficientemente visible.

Resultado obtenido: ****\_\_****

Estado: OK

Observaciones: ****\_\_****

## PRUEBA F — Movimiento

```powershell
python -m src.detect
```

Resultado esperado: Caminar lentamente por diferentes partes del campo visual: cajas por frame sin ID ni trayectoria.

Resultado obtenido: ****\_\_****

Estado: OK

Observaciones: ****\_\_****

## PRUEBA G — Distancia

```powershell
python -m src.detect
```

Resultado esperado: Probar cerca, distancia media y lo más lejos que permita la habitación. Registrar detecciones/omisiones, sin asumir perfección.

Resultado obtenido: reconoce hasta casi cuando desapareces del rango

Estado: OK

Observaciones: de lejos la confianza baja casi a la mitad y cuando estas muy cerca no pasa de los 0.94

## PRUEBA H — Orientación

```powershell
python -m src.detect
```

Resultado esperado: Probar frente, perfil y espalda; registrar cambios de confianza y omisiones.

Resultado obtenido: De perfil tiene 0.94, de espalda entre 80 y 90 y de frente no pasa los 93

Estado: OK

Observaciones: ****\_\_****

## PRUEBA I — Detección parcial

```powershell
python -m src.detect
```

Resultado esperado: Probar medio cuerpo y entrada/salida lateral del frame; registrar el comportamiento sin exigir todos los casos perfectos.

Resultado obtenido: La cabeza esta entre 30 y 50, medio cuerpo 89 aveces baja un poco a 79 pero no pasa de ese rango

Estado: OK

Observaciones: ****\_\_****

## PRUEBA J — Dos personas

```powershell
python -m src.detect
```

Resultado esperado: Si es posible, dos cajas cuando ambas personas sean suficientemente visibles; si no puede hacerse mantener pendiente.

Resultado obtenido: ****\_\_****

Estado: OK

Observaciones: ****\_\_****

## PRUEBA K — Falso positivo

```powershell
python -m src.detect
```

Resultado esperado: Escena sin personas con sillas, ropa y muebles. Registrar si aparece alguna caja person.

Resultado obtenido: ****\_\_****

Estado: OK

Observaciones: reconoce un ventilador con una toalla encima cuando no existe una persona cerca

## PRUEBA L — Rendimiento >=60 segundos

```powershell
python -m src.detect
```

Resultado esperado: Mantener >=60 s; registrar duración, FPS pipeline, inferencia ms y estabilidad. Separar inicialización. Sin umbral obligatorio de 30 FPS.

Resultado obtenido: ****\_\_****

Estado: **PENDIENTE**

Observaciones: ****\_\_****

## PRUEBA M — Cierre q

```powershell
python -m src.detect
```

Resultado esperado: Enfocar ventana, q minúscula; ventana cerrada, retorno a PowerShell y cámara liberada.

Resultado obtenido: ****\_\_****

Estado: OK

Observaciones: ****\_\_****

## PRUEBA N — Cierre ESC

```powershell
python -m src.detect
```

Resultado esperado: Enfocar ventana, ESC; ventana cerrada, retorno a PowerShell y cámara liberada. Repetir también X y Ctrl+C.

Resultado obtenido: ****\_\_****

Estado: OK

Observaciones: ****\_\_****

## PRUEBA O — Liberación cámara

```powershell
python -m src.main
```

Resultado esperado: Después de cerrar src.detect, abrir src.main inmediatamente; la cámara está disponible.

Resultado obtenido: ****\_\_****

Estado: OK

Observaciones: ****\_\_****

## PRUEBA P — Privacidad

```powershell
Get-ChildItem -Recurse -File | Where-Object {
    $_.FullName -notmatch '[\\/]\.venv[\\/]|[\\/]\.git[\\/]' -and
    $_.Extension -in '.jpg', '.jpeg', '.png', '.bmp', '.webp', '.mp4', '.avi', '.mov', '.mkv', '.npy'
} | Select-Object FullName
Test-Path .\runs
```

Resultado esperado: Comparar inventario antes/después: no hay imágenes, videos, labels ni runs generados. Los pesos y ajustes técnicos no son grabaciones.

Resultado obtenido: ****\_\_****

Estado: **PENDIENTE**

Observaciones: ****\_\_****

## PRUEBA Q — Reinicio

```powershell
python -m src.detect
```

Resultado esperado: Cerrar y abrir detección varias veces; pesos locales reutilizados y recursos liberados en cada ejecución.

Resultado obtenido: ****\_\_****

Estado: OK

Observaciones: ****\_\_****

## Aprobación Hito 2

PENDIENTE. Devolver salidas completas de diagnóstico, pip check y unittest; configuración utilizada; CPU/equipo; métricas de L; resultados M/N/O/Q; falsos positivos y omisiones por escenario; inventario P. No es necesario enviar imágenes o videos de personas.


---

# HITO 3 — BYTETRACK

Estado: **PENDIENTE DE PRUEBAS FÍSICAS DEL USUARIO**. Los resultados previos H1/H2 se conservan íntegros, incluidos sus estados históricos. El encargo adjunto informa que H1/H2 fueron físicamente probados; no se reescriben aquí las casillas previas pendientes como si se hubieran vuelto a medir.

Referencia H2 informada en el encargo: 20–24 FPS, 27–31 ms, confianza habitual 0.86–0.92. El ZIP recibido tiene `confidence_threshold=0.65` y `backend=auto`; se conservan. La cama puede generar falsos person de 0.67–0.80 dependientes del ángulo. No son mediciones nuevas de esta entrega.

Fecha/equipo/CPU/webcam/conexión: ____
Python/OpenCV/Ultralytics/torch/torchvision/lap: ____
Configuraciones utilizadas y cualquier cambio: ____

Instalar requirements, ejecutar tests y diagnostics según README. Todas las pruebas siguientes son PENDIENTES: los tests con mocks o cajas sintéticas no completan estas fichas. Registrar únicamente datos técnicos; no se requieren fotografías ni videos de personas.

Para cada escenario registrar: personas reales presentes, cajas observadas (incluidas sin ID), tracks activos, IDs antes/después, confidence, cambios/ID switches, tracks perdidos/recuperados, duración, FPS pipeline, inferencia YOLO, procesamiento YOLO + tracking y observaciones. Las cajas observadas son la salida disponible de la API, no todas las propuestas crudas del detector. No calcular métricas académicas sin ground truth.

## A. Regresión H1

Procedimiento: Ejecutar `python -m src.main`; observar webcam normal sin IA. Cerrar y reabrir.

Esperado: Preview, q/ESC y reapertura normales.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## B. Regresión H2

Procedimiento: Ejecutar `python -m src.detect`; observar cajas y confianza durante al menos 30 s.

Esperado: YOLO sin IDs persistentes ni trails.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## C. Inicio H3

Procedimiento: Ejecutar `python -m src.track`; revisar consola, YAML, CPU y overlay.

Esperado: ByteTrack explícito, sin reinstalaciones automáticas, IDs temporales.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## D. Una persona quieta

Procedimiento: Permanecer visible 30–60 s; registrar ID inicial/final, confidence, FPS y cambios.

Esperado: ID razonablemente estable; no descartar inmovilidad.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## E. Una persona en movimiento

Procedimiento: Caminar izquierda/derecha, adelante/atrás y diagonal; registrar IDs y tiempos de cambio.

Esperado: Continuidad razonable; anotar fragmentaciones.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## F. Acercarse

Procedimiento: Acercarse gradualmente; observar crecimiento de caja, confianza e ID.

Esperado: Registrar estabilidad o cambios sin exigir perfección.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## G. Alejarse

Procedimiento: Alejarse gradualmente; registrar distancia aproximada, confidence, pérdida y recuperación.

Esperado: Caracterizar límite de detección y continuidad.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## H. Perfil

Procedimiento: Girar lateralmente y caminar de perfil; registrar ID antes/después.

Esperado: Anotar omisiones y cambios.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## I. Espalda

Procedimiento: Dar la espalda y alejarse; registrar confianza e IDs.

Esperado: Caracterizar continuidad sin reconocimiento personal.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## J. Oclusión breve

Procedimiento: Ocultarse parcialmente 0.5–1 s; registrar ID antes/después, duración y FPS.

Esperado: Puede recuperar ID; no es garantía.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## K. Oclusión media

Procedimiento: Repetir con 1–2 s; registrar ID antes/después, pérdidas y recuperaciones.

Esperado: Relacionar con buffer en frames, no prometer duración fija.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## L. Salida parcial

Procedimiento: Salir parcialmente del frame y volver varias veces.

Esperado: Registrar pérdidas y cambios de ID.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## M. Salida completa y reentrada

Procedimiento: Salir completamente 0.5 s, 1 s, 2 s y más tiempo; volver en cada caso.

Esperado: Registrar cuándo se recupera ID y cuándo aparece otro.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## N. Dos personas separadas

Procedimiento: Dos personas visibles simultáneamente, separadas; anotar IDs y confidence por caja.

Esperado: Dos IDs distintos cuando ambas detecciones estén confirmadas.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## O. Dos personas moviéndose

Procedimiento: Movimiento simultáneo; registrar continuidad de cada trayectoria.

Esperado: Caracterizar estabilidad.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## P. Cruce de trayectorias

Procedimiento: Cruzar dos personas; registrar IDs antes, durante y después sin usar nombres.

Esperado: Buscar e informar intercambios de ID.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## Q. Una detrás de otra

Procedimiento: Provocar oclusión parcial entre dos personas.

Esperado: Registrar pérdidas, recuperaciones e ID switches.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## R. Distancias diferentes

Procedimiento: Una persona cerca y otra lejos; intercambiar posiciones.

Esperado: Registrar confianza y continuidad por trayectoria.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## S. Falso positivo cama

Procedimiento: Reproducir el ángulo conocido de la esquina de cama; mover ligeramente la cámara y volver. Registrar confidence, ID, duración, posición fija y nuevo ID al reaparecer.

Esperado: Caracterizar sin ignorar por coordenadas o inmovilidad; no atribuir automáticamente al tracker.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## T. Persona + cama

Procedimiento: Mantener falso positivo y caminar en la escena. Registrar ID persona e ID cama falsa, duración y posibles interferencias.

Esperado: Observar si se afectan; no ocultar el falso track.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## U. Mochila

Procedimiento: Intentar reproducir el falso positivo; anotar confidence, creación de ID y duración.

Esperado: Registrar también si no se logra reproducir.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## V. Persona usando mochila

Procedimiento: Caminar con la mochila problemática. Observar si existe un único track o una segunda detección/track falso.

Esperado: Medir sin implementar correcciones específicas.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## W. Dos personas + oclusión

Procedimiento: Combinar movimiento y oclusiones; registrar IDs y secuencia de cambios.

Esperado: Caracterizar escenarios difíciles sin exigir cero ID switches.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## X. Ejecución prolongada

Procedimiento: Mantener 5–10 min o registrar duración real; anotar FPS, inferencia, procesamiento, tracks, errores y memoria inicial/intermedia/final en Administrador de tareas.

Esperado: Sin acumulación sostenida evidente ni crashes; registrar cualquier anomalía.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## Y. Cierre con q

Procedimiento: Con ventana enfocada pulsar q minúscula.

Esperado: Retorno a PowerShell y ventana cerrada.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## Z. Cierre con ESC

Procedimiento: Volver a abrir y pulsar ESC. Repetir además X y Ctrl+C.

Esperado: Cierre limpio y sin procesos reteniendo cámara.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## AA. Liberación de webcam

Procedimiento: Cerrar H3 y ejecutar inmediatamente `python -m src.main`; repetir tras varios cierres.

Esperado: Webcam disponible; cerrar H1 antes del siguiente intento.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____

## AB. Privacidad

Procedimiento: Comparar inventario antes/después y ejecutar los comandos de privacidad indicados debajo.

Esperado: Sin imágenes/videos/frames/labels ni runs generados por la aplicación.

Resultado obtenido: ____

Estado: **PENDIENTE**

Métricas y observaciones: ____


## Comprobación de privacidad antes y después

```powershell
Get-ChildItem -Recurse -File | Where-Object {
    $_.FullName -notmatch '[\\/]\.venv[\\/]|[\\/]\.git[\\/]' -and
    $_.Extension -in '.jpg', '.jpeg', '.png', '.bmp', '.webp', '.mp4', '.avi', '.mov', '.mkv', '.npy'
} | Select-Object FullName
Test-Path .\runs
Test-Path .\videos
Test-Path .\screenshots
Test-Path .\labels
```

## Aceptación H3

**PENDIENTE**. Deben funcionar H1/H2/H3, existir IDs distintos y razonablemente estables en condiciones normales, caracterizar oclusiones y falsos positivos, y comprobar recursos/privacidad. No se exige tracking perfecto ni 30 FPS. Devuelve salidas de tests/diagnostics/pip check y las fichas; incluye FPS H3, tiempos, persona quieta/movimiento, oclusiones, salida/reentrada, dos personas/cruce/ID switches, cama/mochila/persona+cama/persona con mochila, duración, crashes y liberación de webcam.

---

## Mejora de infraestructura — Selección multicámara

**Todas las pruebas físicas siguientes están PENDIENTES.** Esta sección amplía el historial anterior sin cambiar sus resultados. La ejecución automática se documenta por separado en `validacion_tecnica.md`. Fecha de preparación: 2026-09-27.

Usar Windows, entorno virtual activado y `camera_index: "auto"`, salvo indicación. Cada cámara se prueba en una ejecución separada; no abrir dos comandos simultáneamente. Registrar el índice observado, sin suponer que integrada=0 o DroidCam=1. Cerrar otras aplicaciones de cámara.

| ID | Procedimiento | Resultado esperado | Estado |
| --- | --- | --- | --- |
| MC-01 | PC con una cámara; ejecutar `python -m src.main` | Una cámara detectada y seleccionada automáticamente, sin input, imagen correcta | PENDIENTE |
| MC-02 | Laptop con integrada y DroidCam activo; modo auto | Ambas disponibles, selector y posibilidad de elegir DroidCam | PENDIENTE |
| MC-03 | Misma laptop; elegir índice de integrada | Se abre la integrada | PENDIENTE |
| MC-04 | Nueva ejecución; elegir índice de DroidCam | Se muestra la imagen del teléfono | PENDIENTE |
| MC-05 | `python -m src.main`; probar ambas por separado | Preview correcto en ambas | PENDIENTE |
| MC-06 | `python -m src.detect`; seleccionar DroidCam | YOLO detecta personas como en H2, sin IDs persistentes | PENDIENTE |
| MC-07 | `python -m src.track`; seleccionar DroidCam | YOLO + ByteTrack funcionan como en H3 | PENDIENTE |
| MC-08 | Configurar índice fijo 1 si está disponible; ejecutar | Sin scan ni selector, apertura directa de 1; si no existe, error sin cambiar a 0 | PENDIENTE |
| MC-09 | Configurar índice 0; `python -m src.track --camera 1` con 1 disponible | Abre 1; JSON conserva índice 0 | PENDIENTE |
| MC-10 | Auto con varias cámaras; introducir 99 y luego un índice válido | Mensaje de selección inválida, vuelve a pedir sin reescanear | PENDIENTE |
| MC-11 | Apagar/desactivar DroidCam; auto con integrada | Si solo la integrada entrega frames, se elige automáticamente | PENDIENTE |
| MC-12 | `python -m src.diagnostics --scan`; después abrir Cámara de Windows | Dispositivos liberados; no selector en diagnóstico | PENDIENTE |
| MC-13 | En main/detect/track, cerrar con q y con ESC en sesiones separadas; cancelar selector con q | Cierre limpio y cámaras liberadas; cancelación sin iniciar modelo | PENDIENTE |
| MC-14 | Cámara elegida, persona en movimiento y salida/reentrada como pruebas H3 | IDs temporales conservan comportamiento previo; registrar cambios de ID y FPS | PENDIENTE |
| MC-15 | Revisar árbol antes/después de scan, preview, detección y tracking | Sin imágenes, videos, screenshots ni runs generados | PENDIENTE |

Al terminar MC-08/MC-09, restaurar `"camera_index": "auto"`. Si DroidCam apagado sigue entregando un cartel o imagen congelada, OpenCV puede considerarlo funcional: registrar ese comportamiento del driver.

### Ficha para devolver resultados

```text
Fecha / equipo / Windows / versión Python:
MC-ID / comando / camera_index configurado:
Cámaras detectadas (índice, resolución real, backend, FPS informados):
Selección automática sí/no / selector apareció sí/no:
Índice elegido / cámara física observada / correcta sí/no:
MAIN ambas cámaras sí/no:
DETECT DroidCam + YOLO sí/no:
TRACK DroidCam + ByteTrack sí/no / observaciones de IDs:
Override --camera N funciona sí/no / JSON sin cambios sí/no:
Índice fijo evita scan y selector sí/no:
Cámaras liberadas sí/no (incluye Cámara de Windows):
FPS aproximados H3 tras selección / duración y escena:
Crash sí/no / traceback sí/no / mensaje completo:
Archivos visuales o runs creados sí/no:
Resultado APROBADO / FALLIDO / BLOQUEADO / PENDIENTE:
Observaciones:
```

Adjuntar también las salidas de `compileall`, `unittest`, `pip check`, `diagnostics` y `diagnostics --scan`. No se necesitan imágenes de personas para informar estas pruebas.

---

## Separación modo directo / modo selector

Preparado el 2026-09-27 (Chile). **CAM-01–CAM-09: PENDIENTES de prueba física.** El historial anterior permanece intacto. En los casos MC anteriores que solicitan preview con selección, el comando actual es `python -m src.main_seleccionar_camera`.

La configuración adjunta conserva `"camera_index": "auto"` para detect/track. Para CAM-01, configurar un entero que corresponda a la cámara disponible (por ejemplo 0). `src.main` con auto y sin override debe terminar con un mensaje claro, sin scan ni selector. Como alternativa temporal: `python -m src.main --camera N`.

| ID | Procedimiento | Esperado | Estado |
| --- | --- | --- | --- |
| CAM-01 | `python -m src.main` con índice entero configurado | Abre directamente ese índice, sin lista, scan ni input | PENDIENTE |
| CAM-02 | `python -m src.main_seleccionar_camera` en PC con una cámara | Detecta una, la selecciona automáticamente y abre preview | PENDIENTE |
| CAM-03 | Mismo comando en laptop con integrada + DroidCam | Lista ambas y permite elegir; probar también con entero en el JSON | PENDIENTE |
| CAM-04 | Elegir índice de integrada | Abre la integrada | PENDIENTE |
| CAM-05 | Nueva ejecución; elegir DroidCam | Abre DroidCam | PENDIENTE |
| CAM-06 | Cerrar cada modo de preview con q; probar q en selector | Libera cámara; cancelar selector no abre ventana | PENDIENTE |
| CAM-07 | Cerrar cada preview con ESC; comprobar también cierre de ventana y Ctrl+C | Libera cámara y ventanas; otro programa puede usarla después | PENDIENTE |
| CAM-08 | Restaurar auto; `python -m src.detect` | Selección/detección sin regresión | PENDIENTE |
| CAM-09 | `python -m src.track` | Selección/tracking sin regresión | PENDIENTE |

Registrar por caso: equipo/Python, configuración, comando, índices encontrados, cámara elegida/observada, aparición del selector sí/no, errores completos, cierre/liberación y resultado. Confirmar que la selección no cambia `config/camera.json` y que no se crean imágenes/videos. Con varias cámaras, probar también entrada inválida (99) seguida de un índice válido. No dar por hecho que DroidCam corresponde al índice 1.

---

## Corrección AUTO-FIRST / FORCED / INTERACTIVE

Preparado el 2026-09-27 (Chile). **AF-01–AF-08: PENDIENTES.** Esta corrección sustituye la exigencia anterior de configurar un entero para ejecutar `src.main`; los registros MC/CAM se conservan como historial de esas versiones.

Mantener `"camera_index": "auto"` para las pruebas normales. `src.main` sin override busca la primera funcional incluso si el JSON contiene un entero. El selector conserva el escaneo completo. No asumir que integrada=0 o DroidCam=1; identificar los índices reales del equipo.

| ID | Procedimiento | Resultado esperado | Estado |
| --- | --- | --- | --- |
| AF-01 | PC con una cámara, JSON auto: `python -m src.main` | Abre automáticamente, sin selector ni input, sin editar JSON | PENDIENTE |
| AF-02 | Laptop con integrada + DroidCam: `python -m src.main` | Abre la primera funcional por orden de índices; no pregunta ni prueba índices posteriores al primer éxito | PENDIENTE |
| AF-03 | Mismo equipo: `python -m src.main_seleccionar_camera` | Lista ambas; permite elegir integrada o DroidCam en ejecuciones separadas y reintenta entradas inválidas | PENDIENTE |
| AF-04 | `python -m src.main --camera 1`, si 1 corresponde a DroidCam | Abre 1 directamente, sin búsqueda previa; JSON intacto | PENDIENTE |
| AF-05 | `python -m src.main --camera 99`, con ese índice ausente | Error del índice 99; no abre otra cámara | PENDIENTE |
| AF-06 | Sin cámaras disponibles: `python -m src.main` | Error controlado que sugiere diagnostics --scan, sin traceback Python | PENDIENTE |
| AF-07 | Ambos previews: cerrar con q, ESC, ventana y Ctrl+C en ejecuciones separadas | Cámara liberada; otra aplicación puede abrirla; no se generan imágenes/videos | PENDIENTE |
| AF-08 | Ejecutar detect y track después de los previews | Selección, YOLO y ByteTrack conservan comportamiento anterior | PENDIENTE |

Registrar comando, camera_index del JSON, dispositivos/índices, cámara observada, si apareció input, cierre/liberación, errores completos y resultado. Si puedes disponer de un índice 0 no funcional y 1 funcional, comprobar que AUTO-FIRST abre 1. Para comparar con configuración histórica, repetir sin override con un entero en JSON: también debe elegir la primera funcional, no necesariamente ese entero. Restablecer auto al terminar para conservar el uso habitual de detect/track.
