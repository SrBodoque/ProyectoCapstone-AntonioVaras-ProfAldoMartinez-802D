# Hito 4 — Calibrador visual y zonas A/B

El Hito 4 permite dibujar dos zonas para cada ubicación, guardarlas y observar la posición de cada persona con el BoT-SORT + ReID existente. **A** corresponde al espacio cercano al umbral o puerta; **B**, al exterior o aproximación. No hay una tercera línea de cruce. Una observación B → A no confirma una entrada.

Implementación y pruebas unitarias disponibles. La aceptación con cámara, interfaz OpenCV real, inferencia y GPU queda pendiente de las pruebas físicas ZON-01 a ZON-17.

## Inicio

Desde la raíz `capstone-vision`, con el entorno Python que ya utiliza el proyecto:

```powershell
python -m src.zone_calibrator
```

Se abre la cámara previamente seleccionada. No se ejecuta el selector ni se modifica su configuración. Si necesita cambiarla, cierre primero los otros programas que usan la webcam y ejecute voluntariamente el selector existente:

```powershell
python -m src.camera_selector
```

El calibrador usa OpenCV y NumPy ya requeridos por el proyecto; no carga YOLO, PyTorch ni Ultralytics. No instala paquetes. No guarda fotos: Espacio conserva temporalmente el frame mostrado en memoria, y la cámara continúa entregando frames.

## Dibujar, editar y guardar

1. Pulse **A**. Con clic izquierdo, coloque entre 3 y 16 vértices alrededor del espacio cercano al umbral, en orden alrededor del contorno. No repita el primero al terminar.
2. Cierre el polígono con **Enter** o clic derecho. Debe tener área y no cruzarse consigo mismo.
3. Pulse **B** y dibuje la aproximación exterior del mismo modo. Puede dejar un espacio entre ambas zonas. Sus interiores no pueden superponerse; sus bordes sí pueden tocarse.
4. Use **Espacio** para congelar/reanudar la imagen. Puede arrastrar los vértices de la zona seleccionada, incluso después de cerrarla. **U** quita el último vértice y reabre el contorno; **R** borra la zona seleccionada para redibujarla.
5. Pulse **S**. Se validan las dos zonas antes de solicitar el nombre. Escriba, por ejemplo, `habitacion_pruebas` y confirme con **Enter**. Ese ejemplo no viene precalibrado.
6. Si el nombre ya existe, confirme explícitamente la sobrescritura con **Y**, o vuelva con **N/Esc**. Al guardar correctamente, el perfil también queda activo.
7. Pulse **Q/Esc** para cerrar. Si hay cambios pendientes, **Y** los descarta y sale; **N/Esc** vuelve a la edición. La calibración guardada anterior permanece intacta cuando cancela.

La ventana tiene una vista reducida, como máximo 960 × 480, y ayuda debajo; las coordenadas del mouse se convierten proporcionalmente al frame. Los clics sobre la ayuda o fuera de la imagen no agregan puntos. Use las teclas con la ventana enfocada. La cercanía de selección de un vértice es de 10 píxeles en la vista previa.

| Control | Acción |
| --- | --- |
| A / B | Seleccionar la zona |
| Clic izquierdo en el contorno abierto | Agregar un vértice |
| Arrastrar un vértice de la zona seleccionada | Moverlo; ajustar posición, tamaño o forma |
| Enter / clic derecho | Validar y cerrar el contorno seleccionado |
| U / Retroceso | Quitar el último vértice y reabrir |
| R | Borrar y redibujar la zona seleccionada; con perfil incompatible, borra ambas para recalibrar |
| Espacio | Congelar/reanudar el frame en memoria |
| S | Validar, solicitar nombre, guardar y activar |
| P | Mostrar perfiles existentes |
| J / K o ] / [ | Siguiente/anterior perfil en la lista |
| Enter en la lista | Cargar el perfil para revisarlo |
| G | Activar el perfil revisado, compatible y sin cambios pendientes |
| N | Comenzar un perfil nuevo; confirma antes de descartar cambios |
| Q / Esc en edición | Solicitar salida |
| Esc en nombre/lista | Cancelar esa operación y volver |
| Y / N en confirmación | Confirmar / cancelar |
| X de la ventana / Ctrl+C durante la edición | Solicitar salida; si hay cambios, mostrar confirmación |

Para guardar con otro nombre cuando se muestra el actual, bórrelo con Retroceso y escriba el nuevo. El perfil anterior permanece disponible. Al editar un polígono cerrado puede mover vértices; para añadir más, use U para reabrirlo, agregue los puntos restantes y vuelva a cerrar.

Los errores fatales de cámara o interfaz liberan los recursos y salen sin guardar cambios pendientes. La confirmación protege el cierre solicitado por el usuario; no puede conservar una sesión frente a una desconexión, terminación forzada o corte eléctrico.

## Seleccionar otro perfil y volver a editar

Al abrir el calibrador se muestra la última calibración activa si es válida. Para otra ubicación, **P**, seleccione con **J/K**, **Enter** para cargar y revise visualmente la alineación. **G** la activa. Cargar para revisar no cambia por sí mismo el perfil activo. Si hay cambios pendientes al cargar otro perfil, se solicita confirmación para descartarlos.

Puede editar y guardar con S, o usar N para un perfil nuevo. Existe una sola calibración activa. Si el archivo cambió en disco desde su revisión, G exige volver a cargarlo; no activa silenciosamente una geometría distinta.

## Persistencia y archivos locales

La ruta se resuelve respecto a la raíz del proyecto, no respecto al directorio de la terminal:

- `config/zones/<nombre>.json`: perfil de una ubicación.
- `config/zones/active.json`: nombre y **copia completa de la última calibración activada**.
- `config/zones/.gitignore`: excluye todo lo generado en ese directorio y conserva únicamente este `.gitignore`.

La copia de `active.json` es la fuente de verdad del visualizador. No es solo un enlace al perfil por nombre: si falla la activación después de guardar un perfil, continúa vigente la copia activa anterior, incluso si el perfil nombrado ya se actualizó. Si se modifica o elimina manualmente el perfil nombrado, la copia activa conserva la última activación; vuelva a cargar y activar desde el calibrador para cambiarla. No necesita editar JSON.

Cada archivo se escribe en un temporal del mismo directorio, se vacía con `flush`/`fsync` y se reemplaza con `os.replace`. El guardado del perfil y su activación son **dos reemplazos atómicos separados**, no una transacción de dos archivos. Si falla el segundo, se informa que el perfil se guardó pero no se activó; el activo anterior no se sustituye por contenido parcial. Un corte eléctrico y las garantías del sistema de archivos quedan fuera de la prueba automática.

Un directorio temporal `.write-lock` evita dos escrituras simultáneas desde los programas. Tras una terminación forzada podría quedar ese bloqueo: cierre todos los calibradores, compruebe que nadie está guardando y solo entonces elimine ese directorio vacío para reintentar. Los archivos `.pending-*` que dejara un corte pueden retirarse en esas mismas condiciones; no son perfiles. El programa limpia sus temporales ante errores normales.

Nombres: 1–48 caracteres ASCII, primera letra minúscula, luego letras minúsculas, números, `_` o `-`. Se rechazan rutas, puntos, nombres reservados de Windows y `active`. No se siguen enlaces simbólicos para leer o reemplazar perfiles. No se admiten archivos mayores de 64 KiB ni JSON con claves duplicadas.

Los JSON contienen exclusivamente geometría y metadatos. No hay imágenes, recortes, IDs de personas, trayectorias, nombres personales ni embeddings. La persistencia funciona al reiniciar Python o el computador siempre que se conserve esta carpeta y haya permisos de escritura. No copie perfiles de una ubicación al ZIP de distribución como si fueran calibraciones universales.

## Formato y geometría

El perfil tiene `schema_version: 1`, `profile_name`, `camera_index`, `reference_size: [ancho, alto]`, `aspect_ratio` y `zones`, con listas de puntos para A y B. `active.json` contiene `active_profile` y `calibration`, donde esta última es el perfil completo. No se incluyen perfiles de ejemplo en la distribución.

Cada punto se guarda como `[x / ancho, y / alto]`, con números finitos entre 0 y 1. Se usa el plano continuo del frame: los extremos geométricos son 0 y ancho/alto; al dibujar, el píxel se limita a ancho−1/alto−1. La vista previa aplica la misma convención. No se usa el centro del bounding box para clasificar personas.

Validación al cerrar cada contorno y al guardar/cargar el conjunto:

- Entre 3 y 16 puntos por zona, sin duplicados ni repetición del inicial.
- Coordenadas numéricas finitas en rango; rechaza booleanos, NaN e infinitos.
- Área normalizada mayor que `1e-6`; sin retrocesos, autointersecciones ni contactos del polígono consigo mismo.
- Permite polígonos simples convexos o cóncavos, en cualquiera de las orientaciones, adecuados para trapecios y perspectiva.
- Rechaza intersección de interiores A/B, incluida contención completa o polígonos idénticos. Permite separación, borde o punto compartido.
- Incluye los bordes de cada zona; en un borde compartido tiene prioridad **A**. La tolerancia geométrica es `1e-9` en coordenadas normalizadas.

La pertenencia se calcula sobre los lados del polígono. La validación de solapamiento triangula la geometría al cargar/guardar; no rasteriza toda la imagen para decidir la zona de cada persona.

Si falta el activo, está corrupto o es inválido, `track_zones` muestra el problema y termina antes de cargar IA. No inventa zonas ni usa silenciosamente otro perfil. El calibrador permite dibujar nuevamente o seleccionar otro perfil válido.

## Cámara y resolución

Los perfiles guardan el índice de cámara, la resolución efectiva y la relación de aspecto de referencia. Un índice diferente o una relación de aspecto incompatible **bloquean** la aplicación del perfil. El calibrador explica el problema: R borra ambas zonas en el editor y permite recalibrar con la cámara actual; no sobrescribe los archivos hasta guardar y confirmar.

Un cambio proporcional de resolución escala los puntos normalizados. Se tolera hasta un 0,5 % relativo de diferencia de relación de aspecto para redondeos. Se comprueba también cada frame durante el tracking. Si cambia la relación de aspecto durante la calibración, se sale sin guardar y se solicita volver a abrirla.

**El mismo índice no garantiza la misma cámara física ni perspectiva.** Mover, girar o cambiar el zoom, recorte o modo de sensor puede invalidar la geometría incluso conservando índice y resolución. Revise las zonas en pantalla y recalibre después de cualquiera de esos cambios. El programa no puede detectarlos automáticamente.

## Visualizar personas y zonas

Después de guardar/activar:

```powershell
python -m src.track_zones
```

Se carga automáticamente `active.json`. Se reutilizan la cámara seleccionada, `PersonTracker`, su resolución de dispositivo CPU/GPU y el YAML existente `config/botsort_reid_capstone.yaml`. No se cambia el detector, la confianza, la resolución ni los parámetros BoT-SORT/ReID. El modelo se instancia una vez y se llama una vez por frame, antes de dibujar cualquier superposición.

A es azul/celeste y B naranja, con relleno al 20 %, borde y nombre. Las cajas, confianza, IDs y trails reutilizan su representación anterior. Los trails conservan el punto que ya usa `TrackHistory` (centro de caja); la clasificación de zonas usa exclusivamente el nuevo punto inferior central:

```python
person_x = (x1 + x2) / 2
person_y = y2
```

Las cajas entregadas por el tracker están en coordenadas del frame original. Se dibuja ese punto en blanco y se muestra `ID n | ZONA A`, `ZONA B` o `FUERA`. FUERA significa fuera de ambas regiones, incluso en el espacio entre ellas; no se asigna la zona más cercana. Las detecciones sin ID pueden mostrar su zona, pero no generan transiciones por identidad.

La zona actual es geométrica e inmediata. Para mostrar una transición reciente, el mismo ID debe acumular tres observaciones consecutivas en una zona y luego tres en otra. La transición se muestra durante 30 frames procesados. Si el ID deja de aparecer en un frame, se elimina su continuidad; un ID nuevo empieza desde cero. No se conectan fragmentos ni se corrigen intercambios de ID de BoT-SORT. Un intercambio sin desaparición puede producir una observación equivocada: esto no confirma identidad ni un cruce real.

Se muestran FPS del pipeline, inferencia YOLO en ms y **YOLO + tracking** en ms, además de tracks activos, detecciones sin ID, dispositivo y perfil. El último tiempo es el que proporciona el tracker existente, no un tiempo de asociación aislado ni el costo total de dibujar. Los FPS se estabilizan después del inicio y dependen de resolución, GPU, escena y ReID; no hay una promesa de rendimiento sin medirlo.

Q/Esc, X y Ctrl+C cierran el visualizador y liberan la cámara. Para cambiar perfiles, cierre el visualizador, ejecute el calibrador y vuelva a abrirlo; el perfil se carga al iniciar, no se recarga en caliente.

## Pruebas automatizadas

Comandos normales del proyecto, usando su entorno existente:

```powershell
python -m compileall src tests
python -m pip check
python -m unittest discover -s tests -v
python -m src.diagnostics
python -c "import src.zones; import src.zone_calibrator; import src.track_zones"
```

Los nuevos tests se pueden ejecutar por separado:

```powershell
python -m unittest discover -s tests -p test_zones.py -v
python -m unittest discover -s tests -p test_zone_calibrator.py -v
python -m unittest discover -s tests -p test_track_zones.py -v
```

Hay 59 tests nuevos: 29 de geometría/persistencia/observaciones, 19 del editor y 11 del visualizador. Usan geometría real y simulaciones de cámara, GUI e inferencia; no sustituyen pruebas físicas. Incluyen guardado entre procesos, corrupción de JSON, fallos de escritura, cancelación, compatibilidad, liberación de cámara y 300 casos deterministas de solapamiento de rectángulos con un resultado analítico independiente.

Para repetir la regresión auxiliar usada en el entorno sin OpenCV/IA:

```powershell
python tests/hito4_simulated_regression.py
```

Este arnés inyecta OpenCV simulado solo en su proceso, mantiene intactos los tests anteriores, evita 56 invocaciones duplicadas del cargador preexistente y excluye 31 tests que necesitan componentes reales. Ejecuta 345 tests únicos: 286 anteriores y 59 nuevos. Puede recibir una ruta de JSON como único argumento para registrar el resumen y los 31 nombres excluidos. Las exclusiones no cuentan como aprobadas. Ejecute la suite normal en el equipo completo para comprobar los componentes reales.

## Pruebas físicas — todas pendientes

Use una habitación con acceso simulado y después el pasillo. La cámara debe observar solo el acceso y las áreas necesarias, nunca el interior del baño. Anote fecha, cámara/posición, resolución efectiva, perfil, dispositivo efectivo, resultado y observaciones; no necesita grabar personas.

| Caso | Procedimiento y criterio esperado | Estado |
| --- | --- | --- |
| ZON-01 | Dibujar A y B con mouse, cerrar contornos y revisar su alineación. | Pendiente |
| ZON-02 | Guardar con nombre, cerrar y verificar que los JSON permanecen. | Pendiente |
| ZON-03 | Abrir track_zones sin calibrar otra vez; repetir tras reiniciar Python/Windows. | Pendiente |
| ZON-04 | Persona en B: punto inferior central y etiqueta B correctos. | Pendiente |
| ZON-05 | Persona en A: punto inferior central y etiqueta A correctos. | Pendiente |
| ZON-06 | Persona fuera o en el espacio entre zonas: FUERA. | Pendiente |
| ZON-07 | Movimiento B → A con ID continuo: transición observada, sin conteo. | Pendiente |
| ZON-08 | Movimiento A → B con ID continuo: transición observada, sin conteo. | Pendiente |
| ZON-09 | Persona quieta: no generar cambios constantes por oscilaciones breves. | Pendiente |
| ZON-10 | Dos personas en regiones distintas: cada ID tiene su clasificación. | Pendiente |
| ZON-11 | Cruce/oclusión entre personas: documentar intercambios del tracker, sin corregirlos. | Pendiente |
| ZON-12 | Pérdida/cambio de ID: clasificar el track nuevo y descartar continuidad perdida. | Pendiente |
| ZON-13 | Arrastrar, deshacer y redibujar; guardar sobre el perfil con confirmación. | Pendiente |
| ZON-14 | Crear otro perfil, cargar con P, revisar y activar con G; comprobarlo al reiniciar tracking. | Pendiente |
| ZON-15 | Probar otra cámara y aspecto: bloquear geometría incompatible; revisar escalado proporcional. | Pendiente |
| ZON-16 | Editar, Q/X y cancelar; luego salir descartando. El activo anterior debe conservarse. | Pendiente |
| ZON-17 | Comparar track_botsort_reid y track_zones secuencialmente con misma escena, resolución y dispositivo. | Pendiente |

En ZON-17 deje estabilizar el inicio, observe al menos 60 segundos por modo y anote FPS y tiempos mostrados; no atribuya diferencias a las zonas si cambió el dispositivo o la escena. Pruebe CPU y, en el equipo que ya tenga CUDA operativo, GPU. No ejecute simultáneamente dos programas con la webcam.

## Alcance pendiente

No se implementan IN/OUT, FSM de acceso, ocupación, eventos, identidad persistente, recuperación entre IDs, base de datos, API ni integración con Django. No se exportan imágenes ni embeddings. El Hito 5 deberá definir cómo convertir observaciones inciertas en eventos de conteo y cómo tratar las pérdidas/intercambios de ID.
