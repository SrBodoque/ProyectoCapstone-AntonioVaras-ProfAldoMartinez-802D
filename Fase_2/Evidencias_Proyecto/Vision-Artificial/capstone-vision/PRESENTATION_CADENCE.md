# Cadencia ordenada del visualizador de presentación

Esta revisión sustituye el buzón MP4 de último estado por presentación ordenada.
Conserva el mismo worktree `feature/visualizador-presentacion` y no modifica módulos
protegidos ni configuraciones del baseline.

## Referencia real inspeccionada

El visualizador anterior es `src.view_count_results`, que compone anotaciones de
conteo sobre `src.view_results.play`. Se revisaron `Annotations.lines`,
`render_count_overlay`, `play_count`, `play`, `render_frame` y los contratos de
resultados guardados.

El reproductor anterior:

- Reproduce predicciones ya calculadas; no ejecuta YOLO durante la reproducción.
- Lee y presenta cada frame secuencialmente, sin buzón que sustituya frames.
- Usa un plazo por frame antes de dibujar y atender eventos con waitKey.
- Muestra índice/total, timestamp, tracks, estado, totales IN/OUT y último evento.
- Busca conteos por índice de frame; redibujar o pausar no suma eventos.

Se ejecutó su código real, sin editarlo, durante 600 frames sobre la grabación
validada y sus resultados existentes de H5.2, leídos exclusivamente:
`logs/presentation-technical-reference.json`. Mediana/p95 de intervalos de
presentación: **46,51 / 48,80 ms**, con 27,90 s para esos 600 frames y sin inferencia.
Su espera y dibujo hacen que no sea una referencia de reproducción exactamente
1×; sí es referencia de secuencia estable y coherencia entre imagen e indicadores.
No se copió ese retraso adicional como un cambio deliberado de velocidad.

## Problema comprobado en el nuevo

La duración total medida en revisiones anteriores ocultaba irregularidad visual.
Con ventana maximizada, los primeros 600 frames de la versión anterior del nuevo
visualizador tuvieron mediana/p95 **27,60 / 50,53 ms**, aun con promedio global ~1×.
Esa alternancia de intervalos cortos y largos explica los mini tirones y la
percepción de aceleración. El buzón de último estado también permitía que la UI
omitiera estados intermedios cuando el dibujo tardaba más que el trabajador.
Reporte: `logs/presentation-cadence-before.json`.

## Corrección

`src/presentation_playback.py` incorpora `DisplayQueue`, una FIFO de capacidad 4.
El trabajador procesa y precarga cuatro frames; cuando se llena la cola espera,
sin perder frames ni crecer indefinidamente. La UI extrae cada frame en orden y
utiliza los timestamps del archivo para mantener el plazo entre presentaciones.
El plazo pertenece a la interfaz que dibuja, siguiendo la separación del reproductor
anterior. Un retraso no genera ráfagas para recuperar tiempo.

La inferencia deja de decidir cuándo la UI presenta una imagen. Los contadores,
tracks, timestamp y último evento se toman del mismo estado que el frame mostrado,
sin adelantar conteos por el pequeño preprocesamiento en cola. EOF espera que la
UI dibuje y confirme el último frame antes de indicar Finalizado.

La pausa conserva los frames pendientes y detiene la extracción visual. Detener
cancela la cola y despierta al productor. La ventana espera liberación del trabajador.
El modo headless conserva su contrato para herramientas y pruebas independientes;
la ventana activa el buffer explícitamente.

En Windows se solicita temporalmente resolución de temporizador de 1 ms con
`timeBeginPeriod`, equilibrada mediante `timeEndPeriod` al destruir la ventana.
No hay busy-wait ni cambio permanente de configuración. Solo se actualizan widgets
cuando hay un estado o tamaño nuevo, evitando trabajo repetido entre frames.

Una comprobación inicial de 600 frames con la ventana maximizada dio mediana/p95
**33,82 / 36,59 ms**, máximo **40,51 ms**, cero saltos de índice y cero pausas >66,7 ms.
Reporte: `logs/presentation-cadence-after-2.json`. Es una medición inicial; las
validaciones completas por triplicado se documentan al final.

## Tarjeta y cámara

La tarjeta elimina la altura vacía fija: calcula su borde inferior a partir de las
líneas reales. Los avisos solo ocupan espacio cuando existen. El video conserva su
región y aspecto; la tarjeta no reserva una columna ni altera su geometría.

Datos visibles: fuente, tracker/dispositivo, frame/total, timestamp, tracks presentes,
FPS declarados de fuente y FPS visuales observados, IN/OUT y último evento confirmado.
No se muestra capacidad de inferencia como si fuera la velocidad de reproducción.
Tracks presentes no equivale a ocupación ni identidad personal.

La cámara mantiene FPS nativos y la política autorizada previamente: en tracking-only
muestra el estado más reciente y contabiliza los frames no inferidos; sin contador.
El conteo calibrado conserva FIFO sin descarte silencioso. No se aplican perfiles
MP4 automáticamente a una webcam ni se afirma validación física del conteo.

## Ejecución y reproducción de evidencia

Los comandos de `PRESENTATION_PERFORMANCE.md` siguen vigentes, sin controles de
velocidad. Cerrar instancias anteriores y volver a ejecutar desde el worktree.

```powershell
& $python -B -m src.view_presentation --source video `
  --video "$original\videos_testing\nuevo_angulo\video_03.mp4" `
  --zones config/baselines/sala_v4.json --tracker bytetrack `
  --device cuda:0 --weights-dir "$original"

& $python -B -m src.view_presentation --source camera --camera-index 0 `
  --camera-backend msmf --tracking-only --device cuda:0 --weights-dir "$original"

& $python -B tests/validate_presentation_performance.py --resources "$original" --runs 3
```

La validación actual exige además: todos los 5.732 frames realmente dibujados,
cero saltos de índice, p95 de intervalo <45 ms y máximo <100 ms, junto a 21 IN / 20 OUT,
ausencia de error y velocidad compatible con el archivo. Se utiliza ventana
maximizada en cada ensayo. Los intervalos se miden al completar el dibujo, no al
actualizar un contador interno. No se guarda video ni imágenes.

`tests/benchmark_technical_reference.py` permite repetir la referencia anterior,
con rutas explícitas a video, conteo guardado, perfil y predicciones. Valida sus
hashes por `load_view` y verifica que permanezcan intactos al cerrar.

Las pruebas agregan reloj con retraso artificial, prebuffer para clips cortos,
contrapresión y cancelación, y GUI real que verifica todos los índices y contadores
alineados con la imagen. Se corrigió la limpieza de ciclos de objetos Tk en las
pruebas para recolectarlos en el hilo principal antes de crear otros trabajadores.

## Estabilización adicional de cámara

La primera medición maximizada de cámara todavía mostró p95 de 49,19 ms; no se
considera evidencia final de fluidez corregida. La ventana también usa ahora
DisplayQueue para cámara, con dos estados de prebuffer en lugar de cuatro.
Su plazo utiliza los FPS informados por el driver, sin set(CAP_PROP_FPS), y no
confunde la duración variable de inferencia con el periodo del dispositivo.
Se compensa únicamente el pequeño error de planificación del temporizador; una
pérdida de más de un periodo rebasa el reloj y no reproduce una ráfaga atrasada.

Se omite de presentación el frame inicial de cámara si envejeció más de 250 ms
durante el warmup. Ese frame sí se procesa y su estado de conteo no se descarta.
Esto evita enseñar una imagen antigua seguida de un salto hasta el presente.
Los estados restantes se dibujan en orden. La política de captura tracking-only
ya descrita sigue registrando frames intermedios no inferidos cuando corresponda.

La segunda medición de desarrollo de cámara dio mediana/p95 **33,31 / 35,89 ms**,
sin pausas >66,7 ms. La latencia p95 desde lectura hasta dibujo fue **83,85 ms**:
el buffer de dos frames tiene un costo de latencia explícito a cambio de cadencia
más regular. No se presenta la latencia lectura→procesamiento (~25 ms) como si
fuera el retardo visual completo, ni se incluye la latencia óptica desconocida.

Después de este último ajuste se repiten tres procesos nuevos de regresión y tres
sesiones físicas nuevas de cámara. Se conservan por separado los tres MP4 completos
con inferencia del mismo camino de presentación de archivo (sin cambios en su
lógica durante el ajuste exclusivo de cámara). El comando específico es:

```powershell
& $python -B tests/validate_presentation_performance.py --resources "$original" --runs 3 --sources camera
```

Esta revisión añade `src/presentation_playback.py`, amplía pruebas e instrumentos,
y ajusta exclusivamente módulos nuevos de presentación; no modifica el reproductor
anterior ni modelos, zonas o motores del baseline.

## Resultados finales

Todos los ensayos se hicieron con la ventana maximizada, usando el entorno local
existente y CUDA real en la RTX 5060. Sin instalaciones, descargas ni cambios de pesos.

### MP4 completo: tres procesos independientes

Fuente `video_03.mp4`, sala_v4, ByteTrack, conf. 0.65, imgsz 640.
Reportes `logs/presentation-cards-a83d009f-video-1.json`, `-2.json`, `-3.json`:

| Pasada | Frames procesados y dibujados | Saltos de índice | Conteo | Intervalo mediano | Intervalo p95 | Intervalo máximo | Pausas >66,7 ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 5.732 / 5.732 | 0 | 21 IN / 20 OUT | 33,867 ms | 36,961 ms | 52,459 ms | 0 |
| 2 | 5.732 / 5.732 | 0 | 21 IN / 20 OUT | 33,858 ms | 37,669 ms | 56,302 ms | 0 |
| 3 | 5.732 / 5.732 | 0 | 21 IN / 20 OUT | 33,874 ms | 37,758 ms | 52,030 ms | 0 |

Tiempos de presentación: 194,43 / 194,56 / 194,54 s para 191,03 s entre primer y
último timestamp del archivo: ~0,982×, sin aceleración intencional ni recuperación
en ráfagas. El pequeño exceso corresponde a los plazos por frame y planificación
real de ventana; no se afirma sincronización de tiempo real duro sin jitter.
Persisten outliers aislados de 50–56 ms (5 / 4 / 1 por pasada), registrados en los
JSON. No se esconden ni se afirma que cada intervalo sea exactamente 33,333 ms.
La variación habitual bajó de p95 50,53 a 36,96–37,76 ms.

### Cámara física: tres sesiones nuevas después del último ajuste

Reportes definitivos `logs/presentation-cards-f185fae7-camera-1.json`, `-2.json`,
`-3.json`; resumen `logs/presentation-cards-f185fae7-summary.json`.
Estas sesiones reemplazan las mediciones de desarrollo de cámara de la serie a83d009f.

| Sesión | Frames inferidos | Dibujados | Captura observada | Intervalo visual mediano / p95 | Máximo | Lectura→dibujo p95 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 602 | 599 | 29,988 FPS | 33,349 / 35,911 ms | 46,714 ms | 86,210 ms |
| 2 | 602 | 599 | 29,989 FPS | 33,311 / 36,133 ms | 42,450 ms | 86,635 ms |
| 3 | 603 | 599 | 29,992 FPS | 33,335 / 35,791 ms | 43,192 ms | 105,699 ms |

Sin errores, pausas >66,7 ms ni cambios de FPS del driver. Se excluye de pantalla
el frame obsoleto de warmup; al detener se cancelan estados pendientes, por eso
los frames procesados y mostrados no coinciden en estas sesiones acotadas. En el
tercer ensayo se registró un frame de captura no inferido en tracking-only, según
la política explícita de conservar actualidad con el conteo deshabilitado. No se
presenta esa sesión como validación física de conteo. Las tres sesiones reabrieron
y liberaron el mismo dispositivo MSMF en procesos separados.

### Regresión final después del último cambio funcional y de pruebas

Los logs definitivos son `logs/presentation-cards-f185fae7-unit-1.txt`, `-2.txt`,
`-3.txt`:

| Ejecución | Resultado | Duración |
| --- | --- | --- |
| 1 | 622 pruebas, OK, 3 omisiones heredadas | 21,044 s |
| 2 | 622 pruebas, OK, 3 omisiones heredadas | 21,146 s |
| 3 | 622 pruebas, OK, 3 omisiones heredadas | 20,723 s |

37 pruebas de presentación por ejecución. Las tres omisiones heredadas siguen
siendo las integraciones que esperan pesos en la raíz del worktree y los symlinks
Windows; no se cuentan como aprobadas. No hay advertencias de recolección Tk en
estos tres logs finales. El aviso de un intento anterior de desarrollo quedó
conservado y se corrigió recolectando los ciclos de Tk en el hilo principal.

`pip check`: sin requisitos rotos. `git diff --check`: sin errores. Área preparada
vacía. Baseline, módulos de captura/conteo/tracking anteriores, perfiles, videos,
modelos y resultados de H5.2 intactos; sin commit, push ni PR.

La calibración y aceptación física del conteo en cámara sigue pendiente conforme
a la instrucción del usuario. No se afirma precisión general de 100%, rendimiento
CPU sostenido ni ausencia de jitter en otras cargas o equipos. La aceptación
visual en el proyector corresponde a revisión humana con la instancia actualizada.
