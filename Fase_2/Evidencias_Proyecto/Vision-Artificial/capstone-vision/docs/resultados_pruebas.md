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

Resultado obtenido: \***\*\_\_\*\***

Estado: OK

Observaciones: \***\*\_\_\*\***

## PRUEBA B — Entorno virtual

```powershell
python -c "import sys; print(sys.executable); print(sys.prefix != sys.base_prefix)"
```

Resultado esperado: Ruta del ejecutable dentro de .venv\Scripts\python.exe y True; mismo intérprete seleccionado en VS Code.

Resultado obtenido: \***\*\_\_\*\***

Estado: OK

Observaciones: \***\*\_\_\*\***

## PRUEBA C — OpenCV

```powershell
python -m src.diagnostics
python -m pip check
```

Resultado esperado: cv2 4.14.0; distribución opencv-python 4.14.0.94; configuración cargada y sin dependencias rotas.

Resultado obtenido: \***\*\_\_\*\***

Estado: OK

Observaciones: \***\*\_\_\*\***

## PRUEBA D — Índices de webcam

```powershell
python -m src.diagnostics --scan
```

Resultado esperado: Al menos un índice DISPONIBLE que entregue un frame. Configurar ese índice en camera.json si no es 0.

Resultado obtenido: \***\*\_\_\*\***

Estado: OK

Observaciones: \***\*\_\_\*\***

## PRUEBA E — Preview

```powershell
python -m src.main
```

Resultado esperado: Ventana con video en vivo, resolución real, FPS aproximados, índice y backend. Enfocar y cerrar con q.

Resultado obtenido: \***\*\_\_\*\***

Estado: OK

Observaciones: \***\*\_\_\*\***

## PRUEBA F — Estabilidad ≥30 segundos

```powershell
python -m src.main
```

Resultado esperado: Mantener ≥30 s. Imagen continua sin cierre ni congelamiento permanente. Revisar memoria del proceso en Administrador de tareas; registrar duración, FPS y memoria inicial/final. Cerrar con q.

Resultado obtenido: \***\*\_\_\*\***

Estado: OK

Observaciones: \***\*\_\_\*\***

## PRUEBA G — Cierre con q

```powershell
python -m src.main
```

Resultado esperado: Enfocar ventana y pulsar q minúscula. Retorno a PowerShell, ventana cerrada y mensaje de cámara liberada.

Resultado obtenido: \***\*\_\_\*\***

Estado: OK

Observaciones: \***\*\_\_\*\***

## PRUEBA H — Cierre con ESC

```powershell
python -m src.main
```

Resultado esperado: Enfocar ventana y pulsar ESC. Retorno a PowerShell y ventana cerrada.

Resultado obtenido: \***\*\_\_\*\***

Estado: OK

Observaciones: \***\*\_\_\*\***

## PRUEBA I — Liberación de webcam

```powershell
python -m src.main
```

Resultado esperado: Después de cada cierre, volver a abrir y cerrar; luego abrir Cámara de Windows desde Inicio. Imagen disponible. Cerrar Cámara de Windows antes de seguir.

Resultado obtenido: \***\*\_\_\*\***

Estado: OK

Observaciones: \***\*\_\_\*\***

## PRUEBA J — Cambios de configuración

```powershell
notepad .\config\camera.json
python -m src.main
```

Resultado esperado: Con app cerrada, cambiar resolución a 640×480 o índice si hay otra cámara. Consola muestra la nueva solicitud; registrar valor real, que puede diferir. Cerrar, restaurar configuración válida y repetir ejecución.

Resultado obtenido: \***\*\_\_\*\***

Estado: OK

Observaciones: \***\*\_\_\*\***

## PRUEBA K — Privacidad

```powershell
Get-ChildItem -Recurse -File | Where-Object { $_.FullName -notmatch "[\\/]\.venv[\\/]|[\\/]\.git[\\/]" -and $_.Extension -in ".jpg", ".jpeg", ".png", ".mp4", ".avi", ".mov", ".bmp", ".webp", ".npy" }
```

Resultado esperado: Ningún archivo visual generado por la aplicación. Ejecutar antes y después de las pruebas para comparar. Los paquetes instalados se excluyen. Revisar también que no aparezcan directorios de frames o dumps.

Resultado obtenido: \***\*\_\_\*\***

Estado: OK

Observaciones: \***\*\_\_\*\***

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

Fecha: \***\*\_\_\*\***
Equipo: \***\*\_\_\*\***
CPU: \***\*\_\_\*\***
GPU: \***\*\_\_\*\***
Python: \***\*\_\_\*\***
OpenCV: \***\*\_\_\*\***
Ultralytics: \***\*\_\_\*\***
PyTorch: \***\*\_\_\*\***
torchvision: \***\*\_\_\*\***
Modelo: yolo26n.pt
Resolución: \***\*\_\_\*\***
Configuración detection.json: \***\*\_\_\*\***
Cámara/backend y conexión: \***\*\_\_\*\***

Ejecutar desde la raíz del módulo, con .venv activado y requirements actualizado. En caso de fallo conservar consola completa y no marcar aprobado. Copiar esta ficha para el segundo equipo.

## PRUEBA A — Regresión webcam sin IA

```powershell
python -m src.main
```

Resultado esperado: Mismo preview del Hito 1; cierre y reapertura normales.

Resultado obtenido: \***\*\_\_\*\***

Estado: OK

Observaciones: \***\*\_\_\*\***

## PRUEBA B — Diagnóstico IA

```powershell
python -m src.diagnostics
```

Resultado esperado: Versiones fijadas, configuración y CPU; CUDA informativa. Complementar con python -m pip check.

Resultado obtenido: \***\*\_\_\*\***

Estado: OK

Observaciones: \***\*\_\_\*\***

## PRUEBA C — Carga del modelo

```powershell
python -m src.detect
```

Resultado esperado: Descarga oficial si falta el checkpoint, carga una vez y apertura del visor. Tras descargarlo, cerrar y repetir sin Internet para comprobar carga/inferencia local.

Resultado obtenido: \***\*\_\_\*\***

Estado: **PENDIENTE**

Observaciones: \***\*\_\_\*\***

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

Resultado obtenido: \***\*\_\_\*\***

Estado: OK

Observaciones: \***\*\_\_\*\***

## PRUEBA F — Movimiento

```powershell
python -m src.detect
```

Resultado esperado: Caminar lentamente por diferentes partes del campo visual: cajas por frame sin ID ni trayectoria.

Resultado obtenido: \***\*\_\_\*\***

Estado: OK

Observaciones: \***\*\_\_\*\***

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

Observaciones: \***\*\_\_\*\***

## PRUEBA I — Detección parcial

```powershell
python -m src.detect
```

Resultado esperado: Probar medio cuerpo y entrada/salida lateral del frame; registrar el comportamiento sin exigir todos los casos perfectos.

Resultado obtenido: La cabeza esta entre 30 y 50, medio cuerpo 89 aveces baja un poco a 79 pero no pasa de ese rango

Estado: OK

Observaciones: \***\*\_\_\*\***

## PRUEBA J — Dos personas

```powershell
python -m src.detect
```

Resultado esperado: Si es posible, dos cajas cuando ambas personas sean suficientemente visibles; si no puede hacerse mantener pendiente.

Resultado obtenido: \***\*\_\_\*\***

Estado: OK

Observaciones: \***\*\_\_\*\***

## PRUEBA K — Falso positivo

```powershell
python -m src.detect
```

Resultado esperado: Escena sin personas con sillas, ropa y muebles. Registrar si aparece alguna caja person.

Resultado obtenido: \***\*\_\_\*\***

Estado: OK

Observaciones: reconoce un ventilador con una toalla encima cuando no existe una persona cerca

## PRUEBA L — Rendimiento >=60 segundos

```powershell
python -m src.detect
```

Resultado esperado: Mantener >=60 s; registrar duración, FPS pipeline, inferencia ms y estabilidad. Separar inicialización. Sin umbral obligatorio de 30 FPS.

Resultado obtenido: \***\*\_\_\*\***

Estado: **PENDIENTE**

Observaciones: \***\*\_\_\*\***

## PRUEBA M — Cierre q

```powershell
python -m src.detect
```

Resultado esperado: Enfocar ventana, q minúscula; ventana cerrada, retorno a PowerShell y cámara liberada.

Resultado obtenido: \***\*\_\_\*\***

Estado: OK

Observaciones: \***\*\_\_\*\***

## PRUEBA N — Cierre ESC

```powershell
python -m src.detect
```

Resultado esperado: Enfocar ventana, ESC; ventana cerrada, retorno a PowerShell y cámara liberada. Repetir también X y Ctrl+C.

Resultado obtenido: \***\*\_\_\*\***

Estado: OK

Observaciones: \***\*\_\_\*\***

## PRUEBA O — Liberación cámara

```powershell
python -m src.main
```

Resultado esperado: Después de cerrar src.detect, abrir src.main inmediatamente; la cámara está disponible.

Resultado obtenido: \***\*\_\_\*\***

Estado: OK

Observaciones: \***\*\_\_\*\***

## PRUEBA P — Privacidad

```powershell
Get-ChildItem -Recurse -File | Where-Object {
    $_.FullName -notmatch '[\\/]\.venv[\\/]|[\\/]\.git[\\/]' -and
    $_.Extension -in '.jpg', '.jpeg', '.png', '.bmp', '.webp', '.mp4', '.avi', '.mov', '.mkv', '.npy'
} | Select-Object FullName
Test-Path .\runs
```

Resultado esperado: Comparar inventario antes/después: no hay imágenes, videos, labels ni runs generados. Los pesos y ajustes técnicos no son grabaciones.

Resultado obtenido: \***\*\_\_\*\***

Estado: **PENDIENTE**

Observaciones: \***\*\_\_\*\***

## PRUEBA Q — Reinicio

```powershell
python -m src.detect
```

Resultado esperado: Cerrar y abrir detección varias veces; pesos locales reutilizados y recursos liberados en cada ejecución.

Resultado obtenido: \***\*\_\_\*\***

Estado: OK

Observaciones: \***\*\_\_\*\***

## Aprobación Hito 2

PENDIENTE. Devolver salidas completas de diagnóstico, pip check y unittest; configuración utilizada; CPU/equipo; métricas de L; resultados M/N/O/Q; falsos positivos y omisiones por escenario; inventario P. No es necesario enviar imágenes o videos de personas.

### Conclusión Hito 2

La detección de personas mediante YOLO26n presentó un comportamiento estable durante las pruebas controladas realizadas.

Las personas reales fueron detectadas de forma consistente tanto individualmente como en escenarios con dos personas simultáneas, distintas distancias, movimiento y solapamiento parcial.

El pipeline mantuvo aproximadamente 20–24 FPS sobre CPU y tiempos de inferencia cercanos a 27–31 ms, sin observarse problemas de estabilidad durante ejecuciones prolongadas.

Se identificaron falsos positivos asociados a determinados objetos y perspectivas del entorno. Una mochila generó detecciones breves y una esquina específica de una cama pudo alcanzar niveles altos de confianza en determinadas condiciones visuales.

El aumento del umbral de confianza hasta 0.65 no eliminó completamente el falso positivo asociado a la esquina de la cama, por lo que se concluye que incrementar agresivamente el threshold no constituye una solución adecuada por sí sola y podría perjudicar detecciones reales en condiciones más exigentes.

Estos falsos positivos quedan registrados como una limitación conocida del detector base y serán evaluados en las siguientes capas del sistema mediante tracking temporal, delimitación de zonas operativas y validación de trayectoria mediante máquina de estados.

El Hito 2 se considera funcionalmente aprobado para continuar con el desarrollo de tracking, manteniendo pendientes pruebas posteriores en el ambiente real de piloto.

Configuración baseline recomendada:
confidence_threshold = 0.50

El valor podrá recalibrarse durante las pruebas del acceso real.
