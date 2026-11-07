# Hito 5.1 — Entradas y salidas con dos zonas

Convención definitiva del contador: **A exterior del baño**, **B junto a la puerta**.
La primera presencia estable solo establece un origen. Un cambio estable A → B
confirma IN; B → A confirma OUT. No se exige cruzar una línea, salir de B,
un ángulo, una velocidad ni completar el recorrido dentro de un plazo fijo.
Los totales son acumulados por sesión; no representan ocupación ni personas únicas.
No hay envío a Django, persistencia de eventos ni grabación de imágenes.

## Diagnóstico del comportamiento anterior

Se compararon los commits f6a1f1e y 895c911. H4 (f6a1f1e) dibujaba zonas y
transiciones observadas, con la etiqueta "sin conteo IN/OUT"; no tenía acumuladores.
No hay evidencia en ese commit de una versión anterior del mismo contador que
sumara entradas. El recuerdo de funcionamiento de H4 puede corresponder a sus
transiciones visuales, no acredita conteo.

El primer H5.1 (895c911) exigía A estable, salida frontal de A, B estable,
salida frontal de B y permanencia fuera de B. Además imponía convexidad,
corredor y ángulos de 45°, margen espacial, velocidad máxima de 4 D/s,
retroceso acumulado máximo de dos márgenes, gap de 0,5 s y episodio de 12 s.
Esperar en una zona, girar, cruzar un borde lateral, perder un ID o no poder
observar el espacio posterior a B podía impedir la confirmación. Una persona
que llegaba correctamente a B aún no se contaba.

"FUERA" en H4 significa fuera de ambos polígonos, no fuera de la imagen ni
desaparición del ID. El motor anterior también rechazaba puntos normalizados
fuera de [0,1], deteniendo ese frame mediante excepción. Ahora se distinguen
esos casos y se invalida solamente la historia del ID con punto defectuoso,
sin recortar sus coordenadas para inventar una transición.

No se localizaron logs ni el perfil exacto de la sesión física con cero entradas:
estas son causas comprobables en el código, no una atribución definitiva de cada
rechazo observado. La aceptación física de la corrección sigue pendiente.

## Orientación explícita y compatibilidad H4

La guía H4 asignaba A a la puerta y B al exterior. Sus archivos se preservan.
El contador requiere una confirmación humana vinculada al SHA-256 del perfil
activo, incluyendo nombre, cámara, resolución y polígonos. No adivina orientación.

Localizar el perfil de la prueba en la copia de capstone-vision usada allí:

- config/zones/active.json contiene la copia completa activa.
- config/zones/<nombre>.json contiene el perfil guardado.
- El calibrador permite revisar o seleccionar perfiles; no hay que editar su JSON.

Desde capstone-vision, con el Python existente y sin recrear el entorno:

~~~powershell
& .\.venv\Scripts\python.exe -m src.zone_calibrator
~~~

Revise físicamente exterior y puerta. Cierre el calibrador. Si su H4 A ya es
exterior, cree una confirmación nueva:

~~~powershell
& .\.venv\Scripts\python.exe -m src.count_orientation --h4-a-role exterior --reviewer "Nombre del responsable" --confirm-exterior-door
& .\.venv\Scripts\python.exe -m src.track_count
~~~

Si el perfil antiguo tiene H4 A en la puerta, use --h4-a-role puerta. El contador
mapea explícitamente H4 B a Conteo A exterior y H4 A a Conteo B puerta, solo en
memoria. La consola anuncia el mapa y la ventana dibuja las letras del conteo.
Los comandos H4 y sus archivos siguen usando sus letras originales.

La confirmación por defecto es config/counting.local.json, ignorada por Git.
No se sobrescribe. Si cambia o recalibra el perfil, cree una confirmación nueva:

~~~powershell
& .\.venv\Scripts\python.exe -m src.count_orientation --h4-a-role exterior --reviewer "Nombre del responsable" --confirm-exterior-door --output config/counting.habitacion-v2.local.json
& .\.venv\Scripts\python.exe -m src.track_count --orientation config/counting.habitacion-v2.local.json
~~~

Sin confirmación, o si no coincide su hash, el contador se detiene antes de cámara
y modelos. La confirmación registra revisión humana; no identifica por sí misma
la puerta física ni reemplaza revisar el encuadre. No copie registros de otra
calibración para saltarse esta comprobación.

## Entorno, modelos y tracker

No hay dependencias nuevas. Use el .venv existente; un worktree no incluye el
entorno, los pesos ni los perfiles locales de otra copia. Puede invocar el Python
existente por ruta absoluta estando en el directorio del worktree. Prepare o
referencie recursos locales mediante un procedimiento autorizado, conservando
originales; no copie la carpeta de datos completa ni recree entornos.

config/counting.json conserva la selección explícita de los cuatro trackers.
El predeterminado sigue siendo botsort_reid. El baseline de YOLO/ByteTrack y las
confianzas originales no se cambian. Para elegir bytetrack u otro backend, siga
docs/cambiar_tracker_hito5.md; no se cambia de tracker automáticamente.

Antes de abrir cámara se exigen pesos locales no vacíos. Todos necesitan
yolo26n.pt; BoT-SORT/ReID con YOLO26 auto también requiere yolo26n-cls.pt.
Si faltan, aparece un error sin iniciar una descarga. No instale ni descargue
para saltarse esa condición sin autorización. CPU/GPU conserva el selector y
fallback con advertencia existentes; compruebe el dispositivo efectivo en pantalla.

## Estabilidad, pérdidas y rearme

config/counting.json contiene solo cuatro umbrales del contador:

| Parámetro | Inicial | Finalidad |
| --- | ---: | --- |
| zone_dwell_seconds | 0.12 | Tiempo mínimo continuo para confirmar una zona; admite 0 si se necesita menor latencia. |
| min_observations | 2 | Observaciones mínimas además del tiempo; evita contar una sola detección. |
| max_gap_seconds | 2.0 | Máxima discontinuidad para conservar el origen del mismo ID. |
| state_ttl_seconds | 30.0 | Limpieza de estados de IDs ausentes; no borra totales. |

Permanecer en una zona no repite eventos. Cada destino confirmado pasa a ser el
origen del próximo recorrido: IN, OUT y otro IN son posibles con el mismo ID.
No se exige volver fuera de A para rearmar. FUERA intermedio conserva el origen
si el track sigue observado, pero reinicia la candidatura de destino.

Una ausencia breve conserva el origen del mismo ID y reinicia el tiempo de
estabilidad pendiente. Al reaparecer, la zona destino debe adquirir nuevamente
estabilidad. Una pérdida/intervalo mayor que max_gap_seconds borra el origen:
reaparecer en B no inventa una entrada. Un ID nuevo nunca hereda otro recorrido.
Los saltos plausibles o IDs duplicados del tracker no pueden resolverse como
identidad personal por este contador; deben medirse separadamente.

Motivos visibles y en consola: origen_estable, misma_zona,
estabilidad_insuficiente, fuera_de_zonas, perdida_breve, perdida_prolongada,
intervalo_excesivo, punto_invalido_del_tracker, fuera_de_imagen y confirmado_IN/OUT.
El motivo de reinicio se conserva en el diagnóstico del frame aunque la nueva
observación pase inmediatamente a confirmar otra zona. estado_expirado indica
que se eliminó la historia antigua del ID por ausencia superior al TTL.
FUERA de zonas no es una cancelación. Las confirmaciones incluyen ID, sentido y
timestamp. q, Escape, X o Ctrl+C liberan cámara/ventanas. Cada apertura inicia cero.
La consola informa al iniciar el tiempo y número mínimo de observaciones, y al
cerrar muestra ambos totales IN/OUT.

## Prueba corta de aceptación física

Esta aceptación la realiza el equipo con cámara. Las pruebas unitarias y sus
resultados no la sustituyen ni permiten declarar solucionado el fallo físico.

1. Revise el perfil en el calibrador, compruebe exterior/puerta y confirme su
   orientación como se explica arriba. El punto inferior central de la caja,
   no solo la cabeza o una parte del cuerpo, debe entrar claramente en cada zona.
2. Compruebe el tracker y dispositivo efectivo. Anote perfil/hash y umbrales.
   Inicie una sesión nueva y deje que un solo participante establezca su ID en A.
3. Realice la secuencia siguiente sin oclusiones y comprobando que el ID se
   conserva. Los totales indicados son acumulados desde esa sesión nueva:

| Paso | Movimiento | IN / OUT esperado |
| --- | --- | --- |
| 1 | Aparecer y permanecer estable en A | 0 / 0 |
| 2 | A → B y quedarse dentro de B | 1 / 0 |
| 3 | Permanecer en B | 1 / 0 |
| 4 | B → A | 1 / 1 |
| 5 | Desde A aproximarse por FUERA y volver a A, sin confirmar B | 1 / 1 |
| 6 | Reingresar A → B | 2 / 1 |

Un retroceso antes de confirmar la zona contraria no produce evento. Si B ya se
confirmó, la entrada ya ocurrió según este contrato: volver establemente a A
confirma OUT; no elimina ni resta el IN anterior. No hace falta salir de A ni
cruzar otro borde para permitir el siguiente reingreso.

4. Repita en sesiones nuevas a velocidad normal, rápida y lenta. Después pruebe
   dos personas consecutivas, cruces y pérdidas de ID, usando la tabla completa
   de abajo. No cambie umbrales entre intentos sin registrar el cambio.
5. Registre por intento: recorrido real, ID observado, conteos antes/después,
   mensaje de diagnóstico y resultado correcto/omitido/falso/duplicado. Cierre
   con q/Escape para revisar también los dos totales en consola.

### Cómo interpretar los mensajes

| Mensaje | Significado para la prueba |
| --- | --- |
| origen_estable | Se reconoce la primera zona; todavía no hay recorrido entre zonas. |
| estabilidad_insuficiente | Está esperando tiempo y/o observaciones; no es una confirmación ni un rechazo definitivo. |
| misma_zona | No se repite el evento por permanecer allí. |
| fuera_de_zonas | El punto está en la imagen, fuera de A/B; espera el destino sin sumar. |
| confirmado_IN / confirmado_OUT | El mismo ID pasó entre zonas estables; se suma una sola vez. |
| perdida_breve | Conserva el origen del mismo ID, pero reinicia la estabilidad pendiente. |
| perdida_prolongada / intervalo_excesivo / estado_expirado | Descarta historia; reaparecer en el destino no permite inventar el recorrido. |
| fuera_de_imagen / punto_invalido_del_tracker | Descarta la historia de ese ID por datos inválidos, sin recortar puntos ni detener otros IDs. |

Ejemplo de formato de confirmación (no es evidencia de una prueba física):

~~~text
Evento 1 | IN | ID 7 | A -> B | t=0.750
Evento 2 | OUT | ID 7 | B -> A | t=2.100
Totales de sesion | IN=1 | OUT=1
~~~

Si el punto y el mismo ID permanecen válidos y estables en ambas zonas pero el
evento falta, registre un fallo del contador. Si cambió el ID, faltó la caja o
el punto nunca entró en la zona, registre un fallo o limitación del tracking.
Un ID nuevo no demuestra que sea una persona nueva ni hereda el recorrido anterior.

## Interfaz para futuras trayectorias guardadas

El motor no abre cámara, videos, archivos de predicciones, ventanas ni modelos.
Recibe un perfil semántico A exterior/B puerta y, por cada frame completo:

~~~python
from src.count_engine import TransitionCounter, Observation

counter = TransitionCounter(perfil_orientado)
events = counter.update(
    timestamp_segundos,
    [Observation(track_id=7, point=(x_normalizado, y_normalizado))]
)
~~~

El punto es el bottom-center dividido por el ancho/alto del frame; un frame sin
tracks se notifica con una lista vacía. El timestamp debe crecer estrictamente.
Cada evento devuelto incluye IN/OUT, ID, episodio y timestamp, y el motor conserva
los totales de la sesión. No depende de la velocidad de ejecución de una GUI.

Un adaptador futuro podrá leer MP4 y trayectorias guardadas por frame_index,
aplicar su perfil JSON/orientación y usar el tiempo del video, no el reloj del
procesamiento. Después se podrán contrastar los eventos con anotaciones reales.
Ese lector, la comparación, las métricas y su informe automatizado no se
implementan en esta corrección. La aprobación MOT17-04 no se usa como aceptación
de conteo en el acceso al baño.

## Validación y aceptación en cámara

~~~powershell
& .\.venv\Scripts\python.exe -B -m unittest discover -s tests -p 'test_count*.py' -v
& .\.venv\Scripts\python.exe -B -m unittest discover -s tests -p 'test_track_count.py' -v
& .\.venv\Scripts\python.exe -B -m unittest discover -s tests -p 'test*.py' -v
~~~

La batería del contador usa geometría real y trayectorias sintéticas; cámara,
modelo y GUI se simulan en las pruebas del loop. No acredita inferencia ni
precisión física. Repetir la batería relevante tres veces en procesos nuevos
después del último cambio funcional. Las omisiones no son aprobaciones.

Comprobación automatizada de esta corrección: tres procesos independientes con
63/63 pruebas relevantes cada uno, sin omisiones. Regresión general: 405 casos
descubiertos; unittest registra 402, con cero fallos y errores. Quedan cuatro
casos sin acreditar: tres de la clase de inferencia ReID por pesos ausentes y
uno de enlaces simbólicos por permisos de Windows (dos entradas de omisión).
Los logs nuevos se conservan dentro del worktree aislado, no en la rama de
pruebas automatizadas. No se ejecutó nueva inferencia ni aceptación física.

La aceptación en cámara queda a cargo del equipo. Antes de probar, anote el
perfil y su hash, orientación, tracker, dispositivo efectivo y cuatro umbrales.
Mantenga visibles bottom-center e IDs y anote totales antes/después de cada caso:

| Caso | Esperado |
| --- | --- |
| A estable → B estable, sin salir de B | IN +1; OUT sin cambio |
| B estable → A estable | OUT +1; IN sin cambio |
| A → FUERA sin B | Ningún evento |
| Aparece o permanece solo en A o B | Ningún evento |
| Entrada seguida de salida y otra entrada | IN +2, OUT +1 |
| Dos ingresos consecutivos | IN +2 si ambos IDs tienen recorrido completo |
| Dos personas cruzándose en sentidos opuestos | IN +1, OUT +1 si sus IDs se conservan |
| Pérdida breve del mismo ID | Sin evento por pérdida; se exige estabilidad al volver |
| ID nuevo o pérdida prolongada | Sin herencia de historia ni evento por reaparición |
| Recorridos rápidos y lentos | Mismo sentido correcto si hay tiempo/observaciones configurados |

Si falta un evento, revise primero si el tracker produjo el mismo ID y puntos
dentro de ambas zonas. Si esos datos son válidos y estables pero no hay evento,
es un fallo del contador: conserve mensajes, timestamps, ajustes y el perfil
exacto para reproducirlo. Si cambió/perdió el ID o no hubo caja utilizable, registre
el fallo del tracker por separado. No cambie varios umbrales a la vez para ocultarlo.

No recomendar el merge ni declarar aceptación final mientras recorridos
representativos sigan produciendo cero entradas. El total correcto por sí solo
no demuestra ausencia de falsos positivos, omisiones o intercambios de identidad.
