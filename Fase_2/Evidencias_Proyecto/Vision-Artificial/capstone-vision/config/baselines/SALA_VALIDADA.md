# LimpIA - Baseline funcional validado

Fecha: 2026-11-13
Rama de origen: feature/h52-mp4-trackers
Commit de origen: a8d366e

## Configuracion

- Detector: YOLO26n
- Pesos: yolo26n.pt
- Confianza: 0.65
- Resolucion de inferencia: 640
- Tracker principal: ByteTrack
- Alternativa validada: BoT-SORT sin ReID
- Zonas: sala_v4.json
- Equipo probado: RTX 5060
- Dispositivo de ejecucion: cuda:0

## Grabacion validada

- Video: video_03.mp4
- Version: acelerada a 1.3x
- Fotogramas: 5732
- Entradas reales: 21
- Entradas detectadas: 21
- Salidas reales: 20
- Salidas detectadas: 20
- Eventos correctos: 41/41
- Errores observados: 0
- Validacion: revision visual completa del video

## SHA256

Video acelerado:
2C172090C5CA856079BF98D4772F0DCE803AB038E27521E522CFF876C4B44155

Video original:
C0BD951EC7828DC63524C7F169DF21E0B496F38117B05199C6566CE4A3178EC7

Modelo:
9B09CC8BF347F0FC8A5F7657480587F25DB09B34BF33B0652110FB03A8AD4FEF

Perfil de zonas:
46BF13867EF5443F0C24318239CBE1DB433415B0FC03C44981BBD66B908B2AD5

Configuracion detection.json:
E644C2A8DE517EAB7ABBB55B46D17DC4CA3782773809533923058F28879F56DB

## Alcance

Los 41 eventos fueron correctamente contabilizados
en la grabacion validada.

Este resultado no implica precision general del 100%.

Pendientes:
- Prueba con camara en vivo.
- Validacion con nuevas grabaciones independientes.
- Integracion final y pruebas de regresion.
