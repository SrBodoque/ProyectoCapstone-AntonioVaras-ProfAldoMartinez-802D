# Contexto del módulo de visión

CAPSTONE: sistema inteligente de gestión de limpieza de servicios higiénicos basado en demanda real. La webcam observa exclusivamente el acceso, nunca el interior del servicio higiénico.

Arquitectura futura prevista: webcam → detección de personas → tracking con IDs temporales → trayectoria y zonas virtuales → máquina de estados → eventos IN/OUT → HTTP/API hacia Django. Django será la fuente de verdad operacional del contador. La visión producirá eventos, sin identificar personas.

Conceptualmente, desde el pasillo una entrada requerirá B → A → cruce de línea hacia el interior. Una salida requerirá cruce desde el interior → A → B. B → A → B no contará. Esta lógica es contexto futuro: ninguna zona, línea, estado o evento está implementado en este hito.

Hito 1: proyecto base, entorno, configuración, diagnóstico y preview de webcam. No incluye YOLO, tracking, modelos, Django, persistencia ni transmisión. La aceptación requiere pruebas físicas en el equipo del usuario.

Privacidad: frames solamente en memoria durante visualización o comprobación puntual; sin grabación, fotos, audio, reconocimiento facial, identificación ni servicios externos. Los mensajes son técnicos. Instalar dependencias sí utiliza Internet; ejecutar la aplicación no necesita red.

Responsabilidades: configuración valida parámetros; cámara controla hardware y recursos; preview presenta imágenes efímeras; diagnóstico informa condiciones del entorno. No se deriva información operacional de las imágenes en Hito 1.
