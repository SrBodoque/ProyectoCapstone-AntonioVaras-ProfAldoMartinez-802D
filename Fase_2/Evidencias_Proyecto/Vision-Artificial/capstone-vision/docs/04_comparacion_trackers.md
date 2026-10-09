# Comparación experimental ByteTrack / FastTracker

Objetivo: comprobar continuidad de IDs durante cruces y oclusiones, especialmente
cuando una persona pasa detrás de otra. ByteTrack sigue siendo el baseline estable;
FastTracker es una alternativa experimental. No se elige un ganador todavía.

## Condiciones y comandos

Desde la misma carpeta y entorno, cerrar un visor antes de iniciar el siguiente:

```powershell
python -m src.track
python -m src.track_fast
```

Solo cambia el tracker y su pequeña etiqueta en el visor. Ambos usan el mismo
loop, cámara/selector, YOLO26n, clase person, confianza **0.65**, IoU **0.7**, imgsz
**640**, dispositivo efectivo y fallback CPU/GPU. Persistencia **true**, trails
**30**, colores, cierres y métricas se conservan. No se cambia tracking.json ni
el YAML ByteTrack. Cada comando crea su propia sesión y modelo, sin transportar
tracks entre procesos. No hay selector persistente de tracker.

La configuración de cámara actual solicita 1280×720, 60 FPS, backend auto; son
valores solicitados, no FPS garantizados. Para la comparación mantener cámara,
ubicación, ángulo, iluminación, hardware, entorno y dispositivo efectivos iguales.
Registrar cualquier diferencia. La confianza 0.65 se conserva aunque filtre
candidatos inferiores a los umbrales de asociación; no se hace tuning del detector.

## Configuración comprobada en Ultralytics 8.4.163

Se utiliza `config/fasttrack_capstone.yaml`, con `tracker_type: fasttrack`, mediante
el FastTracker integrado. Se verificaron su registro en la API y su inicialización
real, sin instalar trackers externos ni modificar requirements. La documentación
general puede describir versiones posteriores: los valores provienen del archivo
`ultralytics/cfg/trackers/fasttrack.yaml` de **8.4.163 instalado**.

| Parámetro compartido | ByteTrack y FastTracker |
| --- | --- |
| track_high_thresh | 0.25 |
| track_low_thresh | 0.10 |
| new_track_thresh | 0.25 |
| track_buffer | 30 |
| match_thresh | 0.80 |
| fuse_score | true |

| Parámetro específico FastTracker | Default oficial utilizado |
| --- | --- |
| reset_velocity_offset_occ | 5 |
| reset_pos_offset_occ | 3 |
| enlarge_bbox_occ | 1.1 |
| dampen_motion_occ | 0.5 |
| active_occ_to_lost_thresh | 10 |
| init_iou_suppress | 0.7 |
| occ_cover_thresh | 0.7 |
| occ_reappear_window | 40 |

No se optimizaron estos valores. La implementación FastTracker seleccionada no
utiliza ReID, encoder de apariencia ni reconocimiento facial. Mantiene IDs
temporales y procesamiento local; el proyecto no guarda imágenes/video/audio.
Las diferencias en manejo de oclusión son parte de la variable tracker.

## Registro físico pendiente

Equipo/dispositivo efectivo: ____  Cámara/backend/resolución real: ____
Fecha/luz/ubicación: ____  Versiones Python/Ultralytics/PyTorch: ____

| Caso | Escenario | Qué registrar | Estado / resultado |
| --- | --- | --- | --- |
| FT-01 | Una persona caminando | ID inicial/final y estabilidad | PENDIENTE: ____ |
| FT-02 | Dos personas sin cruzarse | Dos IDs y continuidad | PENDIENTE: ____ |
| FT-03 | Cruce rápido | IDs de ambas trayectorias antes/después | PENDIENTE: ____ |
| FT-04 | Cruce lento | IDs de ambas trayectorias antes/después | PENDIENTE: ____ |
| FT-05 | Una persona detrás de otra | Recupera mismo ID, duración y pérdida | PENDIENTE: ____ |
| FT-06 | Oclusión parcial | Continuidad y cambios de ID | PENDIENTE: ____ |
| FT-07 | Oclusión completa corta | Duración, frames aproximados e ID recuperado | PENDIENTE: ____ |
| FT-08 | Repetir casos críticos idealmente 10 veces por tracker | Repeticiones, mantiene/cambia ID, ID switches | PENDIENTE: ____ |

| Escenario | ByteTrack mantiene ID | FastTracker mantiene ID |
| --- | --- | --- |
| Cruce rápido | Usuario completa: ____ / ____ | Usuario completa: ____ / ____ |
| Cruce lento | Usuario completa: ____ / ____ | Usuario completa: ____ / ____ |
| Detrás de persona | Usuario completa: ____ / ____ | Usuario completa: ____ / ____ |
| Oclusión parcial | Usuario completa: ____ / ____ | Usuario completa: ____ / ____ |
| Oclusión completa corta | Usuario completa: ____ / ____ | Usuario completa: ____ / ____ |

Para cada ejecución anotar FPS pipeline, inferencia YOLO ms, YOLO + tracking ms,
tracks activos, cajas sin ID, duración y fallos/cierres. Separar pérdida/cambio de
ID de un intercambio entre personas; no contar una desaparición deliberada fuera
del frame como oclusión equivalente. Ninguna tabla contiene mediciones inventadas.
No grabar personas: bastan observaciones y datos técnicos escritos.

Las pruebas automáticas con mocks/cajas sintéticas comprueban integración y
regresión; no prueban superioridad ni sustituyen estos escenarios físicos.

Validación técnica (2026-10-09): baseline 177/177; final 201/201, incluidos cinco
tests del FastTracker real con cajas sintéticas. Compileall, pip check, diagnostics
e imports pasaron. El checkpoint adjunto ejecutó YOLO en CPU con ByteTrack y
FastTracker sobre dos cuadros negros por sesión; se confirmó el backend explícito,
estado separado, confianza 0.65 y ausencia de encoder ReID. Esos cuadros no
contienen personas. El entorno Linux/Python 3.12.14 no tiene GPU CUDA ni sesión
gráfica; Windows/Python 3.13.15, cámara y cruces físicos quedan por verificar.

Referencias primarias: [tracking oficial](https://docs.ultralytics.com/modes/track/)
y [API FastTracker](https://docs.ultralytics.com/reference/trackers/fast_tracker/).
