# Hito 1 — Entorno y webcam

## Objetivo y preparación

Demostrar que existe una estructura mantenible y un entorno aislado capaz de abrir, mostrar y liberar una webcam. Plataforma de aceptación: Windows 10/11 x64, PowerShell, VS Code, Python 3.13.15 x64 y opencv-python 4.14.0.94. La única dependencia directa está fijada en requirements.txt; pip resuelve NumPy transitivamente. No se instala NumPy manualmente ni paquetes de futuros hitos.

Para instalar desde cero sigue README.md: abrir la raíz del proyecto, verificar Python y arquitectura, crear `.venv`, activar o usar su ejecutable, actualizar pip, instalar requirements y elegir el intérprete en VS Code. No omitas la comprobación de versión antes de crear `.venv`. No reutilices el entorno del desarrollador ni uno de otro computador.

## Ejecución en PowerShell desde la raíz

```powershell
python -m src.diagnostics
python -m src.diagnostics --scan
python -m src.main
```

La primera orden informa versión, plataforma, arquitectura del proceso, ejecutable, entorno virtual, directorios, OpenCV y configuración, sin tocar hardware. La segunda prueba secuencialmente los índices 0 a 4. La tercera crea una ventana de video. Para verificar el código sin hardware:

```powershell
python -m compileall src tests
python -m unittest discover -s tests -v
python -m pip check
```

## Funcionamiento de OpenCV

`VideoCapture` comunica con el controlador usando un backend. Primero se solicita apertura, se comprueba `isOpened`, se solicitan dimensiones y FPS, y se exige un frame válido. Si falla el intento, se libera antes de intentar otro backend. Una vez elegida la captura, cualquier salida del consumidor libera el recurso mediante `finally`. El preview destruye las ventanas también ante errores. El diagnóstico no crea ventanas.

`camera_index` selecciona el dispositivo local; no es un identificador permanente y puede cambiar al reconectar webcams. El escaneo solo cubre 0 a 4; un índice mayor se puede escribir manualmente en configuración.

`backend=auto` en Windows sigue DSHOW → MSMF → CAP_ANY. Forzar `dshow` o `msmf` desactiva las alternativas. Un backend puede bloquear una llamada nativa mientras el controlador responde; este MVP no introduce procesos ni timeouts artificiales. Un fallo de lectura posterior al inicio cierra el preview con mensaje y código 1, sin reconexión automática.

`width` y `height` solicitan resolución; la superposición usa dimensiones reales del frame. `fps` solicita frecuencia. Las propiedades de captura son valores reportados por el controlador y pueden valer cero o no ser precisas. El indicador FPS aproximados mide el ritmo del bucle durante ventanas de aproximadamente un segundo, incluyendo lectura y visualización; no certifica la frecuencia exacta del sensor. No se acumula un historial de frames.

## Cambios y errores de configuración

El archivo se resuelve desde la ubicación de src/config.py, no desde el directorio actual. La ejecución como módulo sí necesita estar en la raíz para que Python encuentre `src`. JSON se lee como UTF-8 y admite BOM de editores Windows. Los campos requeridos son exactamente camera_index, width, height, fps y backend; parámetros inválidos producen ValueError con una explicación que la aplicación presenta en consola.

Modifica el JSON solo con el preview cerrado y reinícialo. Prueba temporalmente 640×480; compara solicitado, reportado y observado. Restaura 1280×720, 30 FPS, índice 0 y backend auto, salvo que tu cámara necesite otro índice confirmado; registra toda diferencia.

## Cierre y diagnóstico de fallos

Enfoca la ventana y pulsa q minúscula o ESC. También se atiende la X de la ventana y Ctrl+C en consola. Tras cada cierre vuelve a abrirla o usa Cámara de Windows, cerrando antes cualquier otra aplicación que ocupe la cámara.

Si una prueba falla, conserva el texto completo de consola, comando, versión, índice y backend. Revisa permisos, conexión y aplicaciones que usan la cámara; prueba otro índice o backend según README. No afirmes que otra app está ocupando el dispositivo sin comprobarlo: es una posible causa.

## Criterios de aceptación

Todas las pruebas A–K de resultados_pruebas.md deben completarse en el equipo objetivo. Se exige Python correcto, entorno aislado, OpenCV correcto, al menos un índice que entregue frames, preview estable ≥30 segundos, cierre con q y ESC, reutilización de webcam, cambios leídos del JSON y ausencia de archivos visuales. Evalúa memoria del proceso en el Administrador de tareas durante la prueba de estabilidad; no se exige un umbral arbitrario, sí registrar comportamiento anómalo.

Las pruebas simuladas cubren errores y liberación de recursos pero no validan drivers, FPS, teclas físicas ni estabilidad de hardware. No declarar aprobado el Hito 1 hasta recibir confirmación del usuario. Ante un fallo se diagnostica ese fallo antes de avanzar a detección.
