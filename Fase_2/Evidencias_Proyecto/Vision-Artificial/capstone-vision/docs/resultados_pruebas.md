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

Resultado obtenido: __________

Estado: OK

Observaciones: __________

## PRUEBA B — Entorno virtual

```powershell
python -c "import sys; print(sys.executable); print(sys.prefix != sys.base_prefix)"
```

Resultado esperado: Ruta del ejecutable dentro de .venv\Scripts\python.exe y True; mismo intérprete seleccionado en VS Code.

Resultado obtenido: __________

Estado: OK

Observaciones: __________

## PRUEBA C — OpenCV

```powershell
python -m src.diagnostics
python -m pip check
```

Resultado esperado: cv2 4.14.0; distribución opencv-python 4.14.0.94; configuración cargada y sin dependencias rotas.

Resultado obtenido: __________

Estado: OK

Observaciones: __________

## PRUEBA D — Índices de webcam

```powershell
python -m src.diagnostics --scan
```

Resultado esperado: Al menos un índice DISPONIBLE que entregue un frame. Configurar ese índice en camera.json si no es 0.

Resultado obtenido: __________

Estado: OK

Observaciones: __________

## PRUEBA E — Preview

```powershell
python -m src.main
```

Resultado esperado: Ventana con video en vivo, resolución real, FPS aproximados, índice y backend. Enfocar y cerrar con q.

Resultado obtenido: __________

Estado: OK

Observaciones: __________

## PRUEBA F — Estabilidad ≥30 segundos

```powershell
python -m src.main
```

Resultado esperado: Mantener ≥30 s. Imagen continua sin cierre ni congelamiento permanente. Revisar memoria del proceso en Administrador de tareas; registrar duración, FPS y memoria inicial/final. Cerrar con q.

Resultado obtenido: __________

Estado: OK

Observaciones: __________

## PRUEBA G — Cierre con q

```powershell
python -m src.main
```

Resultado esperado: Enfocar ventana y pulsar q minúscula. Retorno a PowerShell, ventana cerrada y mensaje de cámara liberada.

Resultado obtenido: __________

Estado: OK

Observaciones: __________

## PRUEBA H — Cierre con ESC

```powershell
python -m src.main
```

Resultado esperado: Enfocar ventana y pulsar ESC. Retorno a PowerShell y ventana cerrada.

Resultado obtenido: __________

Estado: OK

Observaciones: __________

## PRUEBA I — Liberación de webcam

```powershell
python -m src.main
```

Resultado esperado: Después de cada cierre, volver a abrir y cerrar; luego abrir Cámara de Windows desde Inicio. Imagen disponible. Cerrar Cámara de Windows antes de seguir.

Resultado obtenido: __________

Estado: OK

Observaciones: __________

## PRUEBA J — Cambios de configuración

```powershell
notepad .\config\camera.json
python -m src.main
```

Resultado esperado: Con app cerrada, cambiar resolución a 640×480 o índice si hay otra cámara. Consola muestra la nueva solicitud; registrar valor real, que puede diferir. Cerrar, restaurar configuración válida y repetir ejecución.

Resultado obtenido: __________

Estado: OK

Observaciones: __________

## PRUEBA K — Privacidad

```powershell
Get-ChildItem -Recurse -File | Where-Object { $_.FullName -notmatch "[\\/]\.venv[\\/]|[\\/]\.git[\\/]" -and $_.Extension -in ".jpg", ".jpeg", ".png", ".mp4", ".avi", ".mov", ".bmp", ".webp", ".npy" }
```

Resultado esperado: Ningún archivo visual generado por la aplicación. Ejecutar antes y después de las pruebas para comparar. Los paquetes instalados se excluyen. Revisar también que no aparezcan directorios de frames o dumps.

Resultado obtenido: __________

Estado: OK

Observaciones: __________

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

Fecha: __________
Equipo: __________
CPU: __________
GPU: __________
Python: __________
OpenCV: __________
Ultralytics: __________
PyTorch: __________
torchvision: __________
Modelo: yolo26n.pt
Resolución: __________
Configuración detection.json: __________
Cámara/backend y conexión: __________

Ejecutar desde la raíz del módulo, con .venv activado y requirements actualizado. En caso de fallo conservar consola completa y no marcar aprobado. Copiar esta ficha para el segundo equipo.

## PRUEBA A — Regresión webcam sin IA

```powershell
python -m src.main
```

Resultado esperado: Mismo preview del Hito 1; cierre y reapertura normales.

Resultado obtenido: __________

Estado: **PENDIENTE**

Observaciones: __________

## PRUEBA B — Diagnóstico IA

```powershell
python -m src.diagnostics
```

Resultado esperado: Versiones fijadas, configuración y CPU; CUDA informativa. Complementar con python -m pip check.

Resultado obtenido: __________

Estado: **PENDIENTE**

Observaciones: __________

## PRUEBA C — Carga del modelo

```powershell
python -m src.detect
```

Resultado esperado: Descarga oficial si falta el checkpoint, carga una vez y apertura del visor. Tras descargarlo, cerrar y repetir sin Internet para comprobar carga/inferencia local.

Resultado obtenido: __________

Estado: **PENDIENTE**

Observaciones: __________

## PRUEBA D — Escena vacía

```powershell
python -m src.detect
```

Resultado esperado: 0 personas/frame en condiciones normales; registrar cualquier falso positivo.

Resultado obtenido: __________

Estado: **PENDIENTE**

Observaciones: __________

## PRUEBA E — Una persona

```powershell
python -m src.detect
```

Resultado esperado: Una caja person y confianza cuando una persona sea suficientemente visible.

Resultado obtenido: __________

Estado: **PENDIENTE**

Observaciones: __________

## PRUEBA F — Movimiento

```powershell
python -m src.detect
```

Resultado esperado: Caminar lentamente por diferentes partes del campo visual: cajas por frame sin ID ni trayectoria.

Resultado obtenido: __________

Estado: **PENDIENTE**

Observaciones: __________

## PRUEBA G — Distancia

```powershell
python -m src.detect
```

Resultado esperado: Probar cerca, distancia media y lo más lejos que permita la habitación. Registrar detecciones/omisiones, sin asumir perfección.

Resultado obtenido: __________

Estado: **PENDIENTE**

Observaciones: __________

## PRUEBA H — Orientación

```powershell
python -m src.detect
```

Resultado esperado: Probar frente, perfil y espalda; registrar cambios de confianza y omisiones.

Resultado obtenido: __________

Estado: **PENDIENTE**

Observaciones: __________

## PRUEBA I — Detección parcial

```powershell
python -m src.detect
```

Resultado esperado: Probar medio cuerpo y entrada/salida lateral del frame; registrar el comportamiento sin exigir todos los casos perfectos.

Resultado obtenido: __________

Estado: **PENDIENTE**

Observaciones: __________

## PRUEBA J — Dos personas

```powershell
python -m src.detect
```

Resultado esperado: Si es posible, dos cajas cuando ambas personas sean suficientemente visibles; si no puede hacerse mantener pendiente.

Resultado obtenido: __________

Estado: **PENDIENTE**

Observaciones: __________

## PRUEBA K — Falso positivo

```powershell
python -m src.detect
```

Resultado esperado: Escena sin personas con sillas, ropa y muebles. Registrar si aparece alguna caja person.

Resultado obtenido: __________

Estado: **PENDIENTE**

Observaciones: __________

## PRUEBA L — Rendimiento >=60 segundos

```powershell
python -m src.detect
```

Resultado esperado: Mantener >=60 s; registrar duración, FPS pipeline, inferencia ms y estabilidad. Separar inicialización. Sin umbral obligatorio de 30 FPS.

Resultado obtenido: __________

Estado: **PENDIENTE**

Observaciones: __________

## PRUEBA M — Cierre q

```powershell
python -m src.detect
```

Resultado esperado: Enfocar ventana, q minúscula; ventana cerrada, retorno a PowerShell y cámara liberada.

Resultado obtenido: __________

Estado: **PENDIENTE**

Observaciones: __________

## PRUEBA N — Cierre ESC

```powershell
python -m src.detect
```

Resultado esperado: Enfocar ventana, ESC; ventana cerrada, retorno a PowerShell y cámara liberada. Repetir también X y Ctrl+C.

Resultado obtenido: __________

Estado: **PENDIENTE**

Observaciones: __________

## PRUEBA O — Liberación cámara

```powershell
python -m src.main
```

Resultado esperado: Después de cerrar src.detect, abrir src.main inmediatamente; la cámara está disponible.

Resultado obtenido: __________

Estado: **PENDIENTE**

Observaciones: __________

## PRUEBA P — Privacidad

```powershell
Get-ChildItem -Recurse -File | Where-Object {
    $_.FullName -notmatch '[\\/]\.venv[\\/]|[\\/]\.git[\\/]' -and
    $_.Extension -in '.jpg', '.jpeg', '.png', '.bmp', '.webp', '.mp4', '.avi', '.mov', '.mkv', '.npy'
} | Select-Object FullName
Test-Path .\runs
```

Resultado esperado: Comparar inventario antes/después: no hay imágenes, videos, labels ni runs generados. Los pesos y ajustes técnicos no son grabaciones.

Resultado obtenido: __________

Estado: **PENDIENTE**

Observaciones: __________

## PRUEBA Q — Reinicio

```powershell
python -m src.detect
```

Resultado esperado: Cerrar y abrir detección varias veces; pesos locales reutilizados y recursos liberados en cada ejecución.

Resultado obtenido: __________

Estado: **PENDIENTE**

Observaciones: __________

## Aprobación Hito 2

PENDIENTE. Devolver salidas completas de diagnóstico, pip check y unittest; configuración utilizada; CPU/equipo; métricas de L; resultados M/N/O/Q; falsos positivos y omisiones por escenario; inventario P. No es necesario enviar imágenes o videos de personas.
