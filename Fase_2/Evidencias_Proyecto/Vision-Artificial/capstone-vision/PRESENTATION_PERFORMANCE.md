> Revisión vigente: [PRESENTATION_CADENCE.md](PRESENTATION_CADENCE.md). Sustituye el buzón de último estado y la altura fija por presentación ordenada y tarjeta ajustada al contenido; incluye la comparación real con el reproductor anterior.

# Fluidez y tarjeta flotante — revisión del visualizador

Esta revisión reemplaza las descripciones anteriores del panel lateral y del
renderizado PPM en PRESENTATION.md. Conserva el mismo worktree y los motores
protegidos. No modifica YOLO, trackers, contador A/B ni zonas sala_v4.

## Diagnóstico reproducible

Se creó `tests/benchmark_presentation.py` para ejecutar la ventana real, inferencia
local y medir avance del medio frente a reloj de pared, costo de renderizado y
latencia desde lectura de cámara. No guarda imágenes ni video.

Medición inicial con CUDA, primeros 600 frames del video de sala (30 FPS):
19,933 s del medio requirieron 28,138 s de pared: **0,7084×**. Inferencia media
muestreada ~58,9 FPS, renderizado 22,16 ms de media y 25,01 ms p95.
Reporte: `logs/presentation-slowdown-before-2.json`.

Causas identificadas:

- Esperas relativas entre frames: cada exceso de espera/planificación del SO se
  sumaba al siguiente intervalo. Tener inferencia individual superior a 30 FPS
  no garantizaba una reproducción de 30 FPS.
- La UI esperaba 33 ms DESPUÉS de terminar un renderizado de ~22 ms. Eso limitaba
  la presentación visual a unos 18 frames/s, aunque el procesamiento fuera más rápido.
- Copia, polígonos y cajas a 1920×1080 antes de reducir la imagen; conversión PPM
  y reemplazo de recursos Tk en cada actualización.
- Cámara: lectura e inferencia secuenciales sin información sobre antigüedad del
  frame ni control de acumulación. A 60 FPS, una prueba con captura separada
  saturó la cola; se conserva el reporte de ese intento fallido, no se oculta.

## Correcciones

Reloj absoluto para MP4, anclado al primer frame procesado (excluye carga y warmup).
Cada espera se calcula contra el tiempo del archivo desde el origen, compensando
sobrepasos anteriores. La pausa desplaza el reloj sin procesar ni duplicar frames.
Si el hardware no alcanza la tasa del archivo, se conservan todos los frames y
se reconoce la limitación; no se falsifican velocidad ni contadores.

Renderizado: reducir únicamente la imagen de presentación, dibujar sobre esa
imagen y reutilizar el recurso PhotoImage del mismo tamaño mediante ImageTk.
Pillow 12.3.0 YA estaba instalado como dependencia del entorno; no se instaló ni
actualizó nada. El frame que recibe YOLO permanece íntegro y sin cambios.
La cadencia visual descuenta el trabajo de dibujo, con objetivo de hasta 60 Hz;
no se agrega una espera fija de 33 ms al costo de cada dibujo.

Cámara: trabajador de captura separado, timestamps monotónicos al finalizar
cada lectura y FIFO de 8 frames. No se sobrescriben frames pendientes. La saturación
produce error explícito y liberación en lugar de latencia creciente o descarte
silencioso. Se solicitan **30 FPS por defecto** para esta presentación: es una
política explícita y configurable de adquisición, sin cambios al detector ni al
tracker. `--camera-fps 60` permite solicitar 60 si el hardware puede sostenerlo;
no se promete esa capacidad en todos los equipos. El driver puede rechazar la
solicitud; sus FPS informados y la tasa observada no son equivalentes.

La primera inferencia puede tener warmup; el hilo de captura comienza tras ese
primer frame. La latencia medida usa timestamps de lectura del host: no incluye
retardos desconocidos del sensor, transporte, exposición ni buffers internos del driver.
No se afirma una medición óptica de extremo a extremo.

Estado disponible: read_ms, processing_ms, capture_fps, frame_age_ms y tasas de
procesamiento/entrega. Las tasas se distinguen de la fluidez de renderizado.

## Diseño

Video ocupa el ancho de la ventana con relación de aspecto y bandas conservadas.
Tarjeta oscura flotante superpuesta en la esquina superior derecha, con LimpIA,
entradas/salidas en paralelo, estado, último evento confirmado y fuente/dispositivo.
Los controles siguen accesibles debajo del viewport. La tarjeta no reserva una
columna ni cambia el tamaño del video al cambiar contadores o mensajes.
No se muestra ocupación ni otras métricas que no se puedan verificar.

## Cámara sin calibrar

Por instrucción del usuario, se permite validar captura, inferencia y tracking
sin afirmar un conteo de personas validado:

```powershell
# Desde el capstone-vision del worktree de presentación.
$original = 'C:\Users\juanc\Downloads\ProyectoCapstone-AntonioVaras-ProfAldoMartinez-802D\Fase_2\Evidencias_Proyecto\Vision-Artificial\capstone-vision'
$python = Join-Path $original '.venv\Scripts\python.exe'
& $python -B -m src.view_presentation --source camera --camera-index 0 `
  --camera-backend msmf --camera-fps 30 --tracking-only `
  --device cuda:0 --weights-dir "$original"
```

Los contadores aparecen deshabilitados; no hay contador A/B en ese modo. Para
habilitarlo, quitar `--tracking-only`, seleccionar `--zones RUTA_PERFIL.json` y
confirmar el encuadre mediante `--confirm-camera-zones`. Se sigue exigiendo índice
y dimensiones exactos. El perfil sala_v4 acredita únicamente la grabación de sala;
no se declara válido para la webcam física utilizada en estas pruebas.

MP4 con nueva inferencia, mismos parámetros y comandos anteriores:

```powershell
& $python -B -m src.view_presentation --source video `
  --video "$original\videos_testing\nuevo_angulo\video_03.mp4" `
  --zones config/baselines/sala_v4.json --tracker bytetrack `
  --device cuda:0 --weights-dir "$original"
```

Cerrar cualquier ventana anterior y ejecutar de nuevo para cargar esta revisión.
No se necesita reinstalar el entorno ni copiar pesos.

## Validación final reproducible

```powershell
& $python -B tests/validate_presentation_performance.py --resources "$original" --camera-index 0
```

El validador crea un prefijo único de informes y ejecuta de forma secuencial,
sin interferencia entre procesos GPU:

1. Regresión completa en proceso nuevo.
2. Los 5.732 frames del MP4 con GUI, reloj real, ByteTrack y CUDA. Exige 21 IN,
   20 OUT, Finalizado, sin error y velocidad entre 0,96× y 1,04×.
3. Al menos 600 frames de cámara física con GUI, tracking real CUDA, adquisición
   solicitada 30 FPS y conteo deshabilitado. Exige ausencia de errores y p95 de
   lectura-a-fin-de-procesamiento inferior a 150 ms.
4. Repite el ciclo tres veces; si falla, interrumpe y conserva las evidencias.

Las 27 pruebas del visualizador incluyen ahora regresión de sobrepasos de espera,
warmup, cola FIFO acotada con error de sobrecarga, ausencia de contador en tracking-only,
tarjeta superpuesta y reutilización de PhotoImage, además de las pruebas previas.
Las tres omisiones heredadas siguen documentadas en PRESENTATION.md.

Los resultados definitivos se incorporan después de completar los tres ciclos.
La calibración y aceptación física del conteo de cámara se mantienen pendientes
por decisión explícita del usuario. Pruebas de CPU de precisión y rendimiento
sostenido de 60 FPS no se afirman como realizadas.

## Resultados definitivos de las tres validaciones

Serie: `logs/presentation-cards-cfa6b2a0-summary.json`. Todos los seis ensayos
físicos terminaron aceptados; el proceso orquestador terminó con código 0.

| Ejecución | MP4: pared para 191,033 s | Velocidad MP4 | Conteo MP4 | Cámara: frames | Captura observada | Latencia p95 lectura→fin de procesamiento |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 191,073 s | 0,999794× | 21 IN / 20 OUT | 600 | 29,996 FPS | 22,285 ms |
| 2 | 191,058 s | 0,999871× | 21 IN / 20 OUT | 601 | 29,824 FPS | 23,148 ms |
| 3 | 191,022 s | 1,000058× | 21 IN / 20 OUT | 600 | 30,011 FPS | 22,529 ms |

Cada MP4 procesó **5.732 frames**, estado Finalizado y ningún error. Cada cámara
utilizó **captura física MSMF y tracking real en cuda:0**, sin resultados simulados,
sin errores y con los contadores deshabilitados. Las sesiones se cerraron entre
procesos; se reabrió el mismo dispositivo en cada repetición.

Renderizado medio MP4: 11,43 / 11,21 / 11,27 ms frente a 22,16 ms iniciales.
La velocidad inicial 0,7084× pasó a aproximadamente 1×. La cantidad de actualizaciones
visuales puede ser inferior al número de frames procesados; no se eliminan frames
del contador para conseguir este resultado.

Regresión general en tres procesos nuevos:

| Ejecución | Pruebas | Duración unittest | Resultado |
| --- | --- | --- | --- |
| 1 | 612 | 15,731 s | OK, 3 omisiones heredadas |
| 2 | 612 | 15,374 s | OK, 3 omisiones heredadas |
| 3 | 612 | 15,262 s | OK, 3 omisiones heredadas |

27 pruebas del visualizador por ejecución. Las omisiones corresponden a los casos
heredados que buscan pesos en la raíz del worktree y a symlinks Windows; no se
presentan como aprobadas. La inferencia MP4 y de cámara de esta revisión sí se
comprobó con pesos externos locales y CUDA real. `pip check`: sin requisitos rotos.

Se corrigieron también dos problemas del instrumento de medición: cierre de la
ventana antes de escribir el informe y agregación duplicada de una clave del JSON.
La medición estable de cámara excluye sus primeras 30 muestras para separar warmup
(y exposición inicial) de la entrega sostenida. Se conservaron intentos y reportes
previos; no se cambiaron umbrales del producto para forzar el conteo. La primera
pasada MP4 válida y su regresión se reutilizaron al reanudar el orquestador, pues
el código del producto permaneció idéntico; no se contabilizaron como una pasada
adicional. Las otras dos pasadas MP4 son procesos independientes nuevos.

Archivos de esta revisión: los cuatro módulos `src/presentation_*.py` /
`src/view_presentation.py`, `tests/test_presentation.py`, nuevos
`tests/benchmark_presentation.py`, `tests/validate_presentation_performance.py`,
esta guía y enlace en README. La guía PRESENTATION.md conserva la evidencia de la
primera implementación y enlaza esta actualización.

Sin modificaciones en baseline congelado, motores protegidos, modelos, videos o
configuración personal. Sin commit, push ni PR. Recomendación: revisar la tarjeta
en el equipo de presentación; autorizar commit solo tras esa revisión. La aceptación
física del conteo con la cámara instalada sigue pendiente de calibración, conforme
a la instrucción del usuario; la fluidez, captura, tracking y liberación sí se
validaron con hardware real en las tres ejecuciones indicadas.

## Actualización vigente: tamaño de tarjeta y velocidad nativa

Esta sección sustituye la solicitud de 30 FPS y los controles de velocidad de las
versiones anteriores. La tarjeta mide ahora **308×478 px**; la información de sesión
y los avisos tienen cinco líneas reservadas, sin superposición ni recorte de la
última línea observada en la captura del usuario. Las pruebas verifican sus límites
geométricos dentro de la tarjeta. La cifra de FPS de procesamiento se identifica
como **Inferencia (capacidad)**: no es la velocidad a la que se reproduce el video.

La CLI de presentación ya no ofrece `--camera-fps` ni `--unpaced`. El MP4 utiliza
sus timestamps a 1×; la inferencia se realiza antes de esperar la presentación.
Un retraso superior al intervalo de un frame desplaza el reloj en lugar de acelerar
los siguientes frames para recuperar tiempo. No se modifican ni remuestrean archivos.

La cámara no recibe llamadas `set(CAP_PROP_FPS, ...)`. El adaptador aditivo
`native_camera_session` reutiliza la selección de backends existente y conserva la
tasa entregada por el driver; el módulo protegido camera.py permanece intacto.
Mantiene la negociación espacial existente necesaria para los perfiles de zonas.

En `--tracking-only`, la cola conserva el frame más reciente y registra el número
de frames intermedios que no llegaron a inferencia. Esta política mantiene la vista
actual de la cámara cuando la capacidad de inferencia es menor que la adquisición;
no representa una aceleración ni un cambio de FPS del dispositivo. No se ejecuta
el contador en ese modo. El conteo con perfil mantiene FIFO de 8 frames y error
explícito si no puede sostener el flujo; no descarta observaciones silenciosamente.

Se comprobó el origen del material disponible:

| Archivo | Frames | FPS declarados | Duración |
| --- | --- | --- | --- |
| video_03.mp4 | 5.732 | 30 | 191,067 s |
| video_03_original.mp4 | 7.451 | 29,996779 | 248,393 s |

`video_03.mp4` ya contiene la versión acelerada 1,3×, según la especificación del
usuario. Reproducir ese archivo a 1× conserva esa aceleración incorporada al material;
la aplicación no agrega otra. No se aplicó un factor inverso ni se sustituyó la
fuente seleccionada. El perfil sala_v4 sigue vinculado por hash al MP4 acelerado;
no se aplica automáticamente al archivo original de otro hash.

Comandos actualizados, desde el worktree de presentación, con las variables de
entorno de los ejemplos anteriores:

```powershell
& $python -B -m src.view_presentation --source video `
  --video "$original\videos_testing\nuevo_angulo\video_03.mp4" `
  --zones config/baselines/sala_v4.json --tracker bytetrack `
  --device cuda:0 --weights-dir "$original"

& $python -B -m src.view_presentation --source camera --camera-index 0 `
  --camera-backend msmf --tracking-only --device cuda:0 --weights-dir "$original"

& $python -B tests/validate_presentation_performance.py --resources "$original" --runs 2
```

Cerrar instancias anteriores antes de volver a ejecutar. Los resultados de esta
revisión se registran a continuación al completar los dos ciclos nuevos solicitados.

### Dos validaciones finales de velocidad nativa y tarjeta

Serie nueva: `logs/presentation-cards-1975c7ce-summary.json`.
Dos ciclos independientes completos, después del último cambio funcional:

| Ciclo | Regresión | MP4: 5.732 frames | Duración medida MP4 | Cámara física sin fijar FPS | Latencia host p95 |
| --- | --- | --- | --- | --- | --- |
| 1 | 617 pruebas, OK (3 omisiones heredadas), 16,380 s | 21 IN / 20 OUT, Finalizado | 191,018 s para 191,033 s de timestamps | 601 frames procesados; 30,004 FPS observados | 22,103 ms |
| 2 | 617 pruebas, OK (3 omisiones heredadas), 15,809 s | 21 IN / 20 OUT, Finalizado | 191,235 s para 191,033 s de timestamps | 601 frames procesados; 30,022 FPS observados | 21,912 ms |

Velocidades medidas MP4: 1,000082× y 0,998945×, sin factor de reproducción
configurado ni frames omitidos del procesamiento MP4. La pequeña diferencia
corresponde a planificación y muestreo de presentación. Los cuatro ensayos físicos
terminaron sin errores; el orquestador salió con código 0 y ALL ACCEPTED.

La cámara negoció aproximadamente 30 FPS por sí misma: la aplicación no solicitó
30 ni 60. En tracking-only se registraron 2 frames intermedios no procesados en el
primer ciclo y 0 en el segundo, manteniendo el frame más reciente y sin activar
conteo. Esto no certifica precisión de tracking ni conteo físico sobre personas.
La latencia indicada es lectura del host a fin de procesamiento; no incluye
latencia óptica desconocida del sensor. Se abrieron y cerraron sesiones separadas.

32 pruebas nuevas/de presentación por ciclo, incluidas geometría de metadatos y
avisos dentro de la tarjeta, rechazo de controles públicos de velocidad, ausencia
de set(CAP_PROP_FPS), preservación de índices/timestamps en cámara y ausencia de
ráfagas posteriores a un bloqueo de inferencia. Se mantienen las tres omisiones
heredadas descritas previamente; no se cuentan como aprobadas.

`pip check`: No broken requirements found. `git diff --check`: sin errores.
Sin cambios en camera.py, contador, trackers, zonas, visualizador técnico o baseline.
Sin commit ni push. El conteo de cámara permanece pendiente de calibración formal.
