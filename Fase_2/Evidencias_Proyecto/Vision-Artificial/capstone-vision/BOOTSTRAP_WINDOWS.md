# Inicio portable Windows (Python, sin EXE)

Doble clic en `Iniciar_LimpIA.bat` desde capstone-vision. Usa %~dp0; no requiere activacion manual, administrador, PowerShell ni Git instalado. Para fijar un interprete externo configure LIMPIA_PYTHON con su python.exe, o use `Iniciar_LimpIA.bat --python "ruta\python.exe"`. Para comprobar sin abrir el menu: `Iniciar_LimpIA.bat --check --device cuda:0` (CPU: --device cpu).

## Auditoria y arquitectura

Entorno local inspeccionado: Python 3.13.15 x64; torch 2.14.0+cu132, torchvision 0.29.0+cu132, ultralytics 8.4.163, OpenCV 4.14.0.94, lap 0.5.12, numpy 2.5.2, Pillow 12.3.0, PyYAML 6.0.3. RTX5060, driver 610.88. Scipy no esta instalado ni es requisito del runtime Ultralytics actual. Las dependencias dev/export de los extras no son necesarias para este lanzador. No se instala PyInstaller.

El requirements estable se conserva: no distingue indice CPU/CUDA. El nuevo requirements-bootstrap-common.txt fija dependencias comunes principales; las dependencias transitivas siguen siendo resueltas por pip (no es un lock completo). Antes se instala torch/vision desde el indice oficial elegido y luego se impone una restriccion exacta +cpu o +cu132 al instalar comunes. No se sobrescribe la variante Torch por otra accidentalmente. No se modifica ningun paquete en un entorno reutilizado.

Fuentes verificadas: https://pytorch.org/get-started/previous-versions/ documenta torch2.14.0/torchvision0.29.0 e indices CPU/cu132. https://github.com/ultralytics/assets/releases/tag/v8.4.0 contiene la release YOLO26. La descarga solicita consentimiento, usa exclusivamente yolo26n.pt y comprueba el hash del manifiesto local SALA_VALIDADA.md antes de publicar sin sobrescribir. Consulte la licencia Ultralytics antes de redistribuir pesos; no se incluyen en Git.

## Descubrimiento

Prioridad: .venv local, --python/LIMPIA_PYTHON, ultimo entorno recordado, entorno original del worktree identificado mediante .git/commondir sin git.exe, ruta manual, crear entorno nuevo. No hay escaneo de disco. Sin Python compatible se indica instalar Python3.13 x64. El Batch necesita un Python que pueda arrancar (local, LIMPIA_PYTHON, py -3.13, python PATH); no instala Python global.

Se importan tkinter/OpenCV/Torch/torchvision/Ultralytics/lap/PIL/yaml, verifican versiones y arquitectura, NMS torchvision y operacion tensor CPU/CUDA real. pip check verifica dependencias. Al preparar un modelo/entorno diferente se hace carga e inferencia sintetica real, sin captura ni almacenamiento de imagenes. Las siguientes ejecuciones con igual huella omiten carga de YOLO; siguen verificando importaciones/tensores/pip check. La huella no sustituye una auditoria completa del contenido de todos los paquetes.

CPU/GPU no cambia silenciosamente. Para instalaciones nuevas este asistente ofrece CPU o cu132 con la pareja del entorno validado. cu132 requiere que nvidia-smi anuncie CUDA>=13.2 antes de descargar; despues exige operacion CUDA real. Esa condicion previa no garantiza que la arquitectura de GPU este soportada: la comprobacion final es obligatoria. No instala drivers, CUDA Toolkit ni herramientas del sistema. No implementa automaticamente variantes CUDA antiguas; equipos incompatibles deben elegir CPU o aportar un entorno compatible validado. No se acredita GPU Intel/AMD.

## Consentimiento, recuperacion y recursos

La reutilizacion externa se confirma la primera vez. Crear entorno requiere permiso y destino inexistente; no repara ni borra entornos existentes. Si .venv esta incompleto, se puede seleccionar otro interprete o crear en otra ruta nueva. Un fallo conserva el entorno parcial para diagnostico; no se registra como exitoso. La reparacion in situ no esta implementada. Para reintentar, seleccione otro destino nuevo o un entorno preparado externamente. Ctrl+C cancela el proceso de instalacion; no se reanuda automaticamente una instalacion parcial.

Los pesos se buscan en modulo actual, carpeta explicitada/variable, preferencias bootstrap/lanzador y ubicaciones del repositorio conocidas. Un SHA distinto exige consentimiento y no se declara equivalente al baseline. Un archivo corrupto debe superar carga/inferencia, o se rechaza. Descarga desde fuente oficial solo al elegir D y confirmar; un fallo de red no publica el destino. No se copian pesos externos.

Preferencias de bootstrap: %LOCALAPPDATA%/LimpIA/bootstrap.json, separadas de launcher.json. Logs: %LOCALAPPDATA%/LimpIA/logs/<uuid>.log. Se registran detalles tecnicos; usuario recibe mensajes en espa?ol. El entorno correcto se pasa directamente a ejecutable.py junto con dispositivo y carpeta de pesos, sin reestructurar la navegacion. Las rutas personales solo aparecen en preferencias locales, nunca en codigo.

## Evidencia y limites

Archivos nuevos: Iniciar_LimpIA.bat, instalar_limpia.py, requirements-bootstrap-common.txt, tests/test_bootstrap.py, este documento. README enlaza la guia. Se preservaron los cambios pendientes de autoguardado y navegacion. No hay cambios en vision, configuracion de deteccion, perfiles, videos, pesos, .venv original o baseline. Sin commit/push.

15 pruebas bootstrap agrupan ejecucion real Batch desde carpeta con espacios y otro directorio, prioridades y preferencias, clon sin entorno/cancelacion, entorno incompatible, instalacion nueva CPU/GPU simulada, restricciones Torch, deteccion/driver, comprobaciones tensor/imports/NMS, pesos coincidentes/distintos/ausentes, descarga autorizada/rechazada y fallos de red simulados, segunda ejecucion sin reinstalar. Esta cobertura no equivale a probar fisicamente los 32 escenarios del pedido: Python totalmente ausente/alias Store, Ctrl+C durante descarga/pip y una instalacion nueva GPU siguen sin verificarse integralmente. La instalacion CPU real se verifico posteriormente.

Prueba local real Batch --check --device cuda:0: exit0, entorno externo reutilizado, hash/carga/inferencia reales, sin pip install ni descarga. Prueba Batch normal: menu Tk real observado mediante callback de prueba, cierre por protocolo X normal, exit0, stderr vacio. Artefacto logs/bootstrap-menu-<uuid>/result.json. Solo se automatizo el cierre del menu; no se simularon Torch ni modelo. Las preferencias de esta prueba se aislaron en LOCALAPPDATA de pruebas. No se prueba inferencia GPU concurrente a otra inferencia.

Instalacion nueva CPU: ejecutada realmente con autorizacion posterior del usuario; ver evidencia al final. Instalacion nueva GPU y los escenarios negativos pendientes no se consideran acreditados por la prueba CPU. El entorno funcional original permanece intacto.

## Tres regresiones generales independientes

Comando: entorno existente `python -B -m unittest discover -s tests -v`.

- 1: Ran 710 tests in 33.168s; OK (skipped=3). Log logs/bootstrap-final-1.txt.
- 2: Ran 710 tests in 31.015s; OK (skipped=3). Log logs/bootstrap-final-2.txt.
- 3: Ran 710 tests in 30.600s; OK (skipped=3). Log logs/bootstrap-final-3.txt.

Tres omisiones heredadas: integracion ReID, integracion MP4 optativa y symlink sin permisos. Ninguna nueva prueba bootstrap omitida. Las instalaciones/descargas en unit tests fueron simuladas; el Batch desde rutas con espacios y la reutilizacion CUDA/menu se ejecutaron realmente.


## Prueba nueva CPU autorizada ? 2026-11-14

Se ejecuto realmente `instalar_limpia.install(..., cpu, <directorio-nuevo>)`, confirmando el permiso ya concedido por el usuario. Se creo un venv nuevo con Python 3.13.15 x64, `include-system-site-packages=false`, dentro de `logs/bootstrap-clean-cpu-8989f5b0970f408fb928a8237ae03010/environment`. Se instalaron paquetes oficiales desde cero, incluyendo descarga de Torch CPU. No se reutilizaron paquetes del entorno estable; pip pudo reutilizar archivos de su cache. La fase comun ajusto NumPy/Pillow en este entorno NUEVO y conservo Torch/vision +cpu mediante restricciones.

Resultado: torch 2.14.0+cpu, torchvision 0.29.0+cpu, torch.version.cuda=None. Se verificaron tensor CPU, NMS torchvision, importaciones, versiones, pip check y carga/inferencia sintetica real con los pesos oficiales externos existentes. No se descargaron ni copiaron pesos. `pip check`: No broken requirements found.

El Batch se ejecuto dos veces con LIMPIA_PYTHON apuntando exclusivamente al entorno CPU nuevo y LOCALAPPDATA aislado. En ambas abrio el menu Tk real y termino por su protocolo de cierre normal con codigo0 y stderr vacio. La segunda no solicito reutilizacion ni ejecuto instalacion alguna. El cierre del menu fue automatizado mediante un callback Tk de prueba; el modelo, interprete y dependencias fueron reales.

Preservacion: pip freeze del entorno estable identico antes/despues; hashes de detection.json y sala_v4.json identicos. Las preferencias usadas en la prueba se aislaron. El nuevo entorno se conserva sin borrar para reproducir/inspeccionar; no se agrega a Git.

Evidencia en el mismo directorio de prueba: install.txt, manifest.json, validation.json, cpu-freeze.txt, pip-check.txt, validate_menu.py, menu-1.txt, menu-2.txt y regression-N.txt. El manifiesto contiene las rutas locales necesarias para repetir, sin codificarlas en el bootstrap portable.

Para repetir solo la comprobacion sin reinstalar, desde capstone-vision use `Iniciar_LimpIA.bat --python "<directorio-prueba>/environment/Scripts/python.exe" --device cpu --check`. Para abrir el menu quite --check. No reutilizar install() sobre el directorio ya existente: su proteccion rechaza sobrescribirlo.

Tres regresiones generales independientes usando el Python CPU recien instalado (no el entorno estable):

- Ronda 1: Ran 710 tests in 33.274s; OK (skipped=3); avisos Tk: [].
- Ronda 2: Ran 710 tests in 33.679s; OK (skipped=3); avisos Tk: [].
- Ronda 3: Ran 710 tests in 33.062s; OK (skipped=3); avisos Tk: [].

Las 3 omisiones heredadas son ReID real, MP4 optativo y symlink sin permisos. No hay pruebas bootstrap omitidas. La comparacion del entorno estable y hashes se repitio despues de las tres regresiones y sigue siendo identica. No hubo cambios funcionales en esta validacion, solo evidencia y documentacion.
