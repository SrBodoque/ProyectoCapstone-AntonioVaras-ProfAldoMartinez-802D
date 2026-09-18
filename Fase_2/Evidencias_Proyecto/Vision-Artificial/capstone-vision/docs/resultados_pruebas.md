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