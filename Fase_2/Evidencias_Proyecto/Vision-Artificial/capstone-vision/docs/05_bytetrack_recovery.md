# ByteTrack Recovery — experimento de baja confianza

Durante las pruebas físicas del usuario, ByteTrack y FastTracker cambiaron IDs
en ciertos cruces y oclusiones. El pipeline actual filtra YOLO a 0.65 antes del
tracker, por lo que no entrega candidatos débiles a su segunda asociación.
Recovery prueba si esos candidatos ayudan a mantener trayectorias activas,
exigiendo confianza alta para iniciar trayectorias nuevas. Es una hipótesis;
no demuestra mejora física, seguimiento perfecto ni precisión de conteo.

## Ejecución y comparación

Desde `capstone-vision`, con el entorno existente activo, cerrar cada visor antes
de abrir el siguiente:

```powershell
python -m src.track
python -m src.track_recovery
# Referencia adicional opcional:
python -m src.track_fast
```

Recovery reutiliza el loop y el cargador existentes. Su título es
`ByteTrack Recovery (Experimental)`. La consola muestra confianza efectiva,
confianza general y umbrales del tracker. No solicita ni guarda cámara/dispositivo.

| Parámetro | ByteTrack original | FastTracker original | Recovery |
| --- | --- | --- | --- |
| YAML | bytetrack_capstone.yaml | fasttrack_capstone.yaml | bytetrack_recovery_capstone.yaml |
| tracker_type | bytetrack | fasttrack | bytetrack |
| conf enviada a model.track | 0.65 | 0.65 | 0.10 |
| track_high_thresh | 0.25 | 0.25 | 0.65 |
| track_low_thresh | 0.10 | 0.10 | 0.10 |
| new_track_thresh | 0.25 | 0.25 | 0.65 |
| track_buffer | 30 | 30 | 30 |
| match_thresh | 0.80 | 0.80 | 0.80 |
| fuse_score / persist | true / true | true / true | true / true |

`detection.json` conserva 0.65. El override opcional se almacena por instancia en
`PersonTracker.tracking_confidence`, separado de `config["confidence_threshold"]`.
Se validan tipo numérico, finitud y rango [0, 1]; `None` significa usar el valor
general válido. Con override se exige `new_track_thresh >= track_high_thresh`;
el validador existente ya exige `track_low_thresh < track_high_thresh`.
Los JSON y YAML originales no se escriben.

Permanecen iguales YOLO26n, person 0, IoU 0.7, imgsz 640, cámara seleccionada,
resolución/FPS solicitados, CPU/GPU efectivo y fallback, trails de 30 puntos,
colores, métricas y cierres q/ESC/Ctrl+C. `main`, `detect`, ambos selectores,
FastTracker y las dependencias no se modifican.

## Asociación, riesgos y límites

El diseño separa detecciones altas (>=0.65) y débiles (>0.10 y <0.65).
Las débiles se destinan a la segunda asociación de tracks aún activos; no a
iniciar tracks. Un track ya perdido o sin confirmar no dispone de esa misma vía.
Una oclusión completa puede requerir una nueva detección alta y una asociación
geométrica válida; conservarlo en el buffer no garantiza recuperar su ID.

Una caja débil asociada puede mantener un ID, pero no prueba que sea una persona.
Falsos positivos altos todavía pueden iniciar tracks; candidatos débiles también
pueden asociarse incorrectamente. El visor conserva cajas sin ID que devuelve
la API: una caja visible sin ID no equivale a un track nuevo. No se ocultan
observaciones ni se agregan filtros de cama, tamaño, inmovilidad o posición.
Más candidatos podrían afectar FPS. Se mantienen las métricas para medirlo.

La [referencia oficial ByteTrack](https://docs.ultralytics.com/reference/trackers/byte_tracker/)
explica esta separación y sus estados. Es documentación actual, no una
verificación ejecutada de 8.4.163. En este entorno faltan OpenCV y las dependencias
IA; la red impidió preparar el entorno fijado. La ejecución del motor real queda
pendiente, con ocho tests específicos listos en `test_recovery_integration.py`.
No se modificó código interno de Ultralytics ni se incorporó otra implementación.

Se conserva procesamiento local, frames en memoria e IDs temporales. Sin ReID,
grabaciones, fotos, audio, datos personales persistidos, cloud, zonas, FSM o IN/OUT.

## Pruebas físicas pendientes

Primero ejecutar la suite completa en el entorno funcional del usuario. Luego
comparar ByteTrack original y Recovery con cámara, posición, dispositivo,
personas, iluminación, resolución y movimientos equivalentes. Cerrar cada sesión.
Registrar el dispositivo efectivo y las propiedades reales de cámara; los 60 FPS
configurados son solicitados, no una medición de rendimiento.

| Caso | Escenario | Registro esperado | Estado |
| --- | --- | --- | --- |
| REC-01 | Una persona caminando | Continuidad de ID | Pendiente |
| REC-02 | Dos personas sin cruzarse | IDs independientes | Pendiente |
| REC-03 | Cruce rápido | IDs antes/después | Pendiente |
| REC-04 | Cruce lento | IDs antes/después | Pendiente |
| REC-05 | Persona detrás de otra | ID y duración de oclusión | Pendiente |
| REC-06 | Oclusión parcial prolongada | Confianza e ID durante el cruce | Pendiente |
| REC-07 | Oclusión completa | Pérdida/recuperación, sin asumir éxito | Pendiente |
| REC-08 | Falsos positivos conocidos | Cajas sin ID y tracks falsos por separado | Pendiente |
| REC-09 | Rendimiento | FPS pipeline, YOLO ms, YOLO + tracking ms | Pendiente |
| REC-10 | Idealmente 10 repeticiones por caso crítico | Totales, conserva/cambia ID y tracks falsos | Pendiente |

Copiar una fila por escenario y modo. Todos los resultados quedan vacíos:

| Caso / modo | Repeticiones | Mantiene ID | Cambia ID | Intercambios de ID | Tracks falsos | FPS / YOLO ms / total ms | Observaciones |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ____ / ByteTrack | ____ | ____ | ____ | ____ | ____ | ____ | ____ |
| ____ / Recovery | ____ | ____ | ____ | ____ | ____ | ____ | ____ |
| ____ / FastTracker opcional | ____ | ____ | ____ | ____ | ____ | ____ | ____ |

Equipo/dispositivo: ____  Cámara/backend/resolución: ____  Fecha/luz: ____
Separar asignación de un ID nuevo e intercambio de IDs entre dos personas.
Las métricas de continuidad no son precisión de conteo: IN/OUT aún no existe.
No es necesario grabar personas para completar estas observaciones.
