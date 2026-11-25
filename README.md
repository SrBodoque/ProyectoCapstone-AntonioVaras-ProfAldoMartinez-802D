# LimpIA

**Sistema inteligente de gestión de limpieza de servicios higiénicos basado en demanda real.**

## Descripción del proyecto

LimpIA es un sistema desarrollado en el contexto de la asignatura Capstone de Ingeniería en Informática de Duoc UC, sede Antonio Varas.

La solución integra visión artificial y una plataforma web para contabilizar entradas y salidas de personas, generar alertas de limpieza según umbrales configurables y mantener un registro de las intervenciones realizadas.

Está dirigida principalmente a supervisores de Servicios Generales y Mantención y trabajadores de limpieza, beneficiando indirectamente a los usuarios de los servicios higiénicos.

El proyecto busca complementar la planificación de limpieza basada en horarios preestablecidos mediante información sobre la demanda real de utilización, facilitando la priorización de las intervenciones y mejorando su trazabilidad.

El procesamiento de video se realiza localmente, sin reconocimiento facial ni identificación personal de los usuarios.

## Tecnologías utilizadas

### Visión artificial

- Python: lenguaje de programación.
- OpenCV: captura y procesamiento de video.
- YOLO26n: detección de personas.
- ByteTrack y BoT-SORT: seguimiento temporal de personas.
- PyTorch: ejecución del modelo de detección.
- SQLite: almacenamiento local de eventos pendientes de transmisión.
- Tkinter: interfaz gráfica del lanzador operativo.

### Backend y base de datos

- Django: framework web, autenticación y lógica de negocio.
- PostgreSQL: base de datos relacional.
- API HTTP con JSON: comunicación entre visión artificial y Django.

### Frontend

- HTML5.
- CSS3.
- JavaScript.
- Django Templates.

### Herramientas de desarrollo

- Visual Studio Code.
- Git y GitHub.
- Draw.io.

### Infraestructura y despliegue

Actualmente, el sistema funciona en un entorno local de desarrollo. Se contempla su despliegue en un servidor personal mediante Docker y Docker Compose, con acceso remoto a través de un dominio propio y conexiones HTTPS.

La integración del entorno de producción se encuentra en proceso de implementación.

## Instalación, configuración y ejecución local

Las siguientes instrucciones describen la preparación y ejecución de LimpIA en un entorno local Windows utilizando PowerShell.

El proyecto está compuesto por dos módulos principales:

- **HigieneSmart**: plataforma web desarrollada en Django.
- **capstone-vision**: módulo de visión artificial.

Cada módulo utiliza su propio entorno virtual de Python.

### 1. Requisitos previos

| Herramienta | Requisito |
|---|---|
| Sistema operativo | Windows |
| Python | Python 3.13 de 64 bits |
| PostgreSQL | Versión 18.6 utilizada durante el desarrollo |
| Git | Descarga y control de versiones del repositorio |
| Visual Studio Code | Editor recomendado |
| Cámara | Webcam o fuente de video compatible con OpenCV |
| Procesamiento | CPU o GPU NVIDIA compatible con CUDA |
| Navegador | Chrome, Edge, Firefox u otro navegador moderno |

### 2. Descargar el repositorio

```powershell
git clone https://github.com/SrBodoque/ProyectoCapstone-AntonioVaras-ProfAldoMartinez-802D.git
cd ProyectoCapstone-AntonioVaras-ProfAldoMartinez-802D
code .
```

### 3. Plataforma web (HigieneSmart)

Desde la raíz del repositorio:

```powershell
cd .\Fase_2\Evidencias_Proyecto\HigieneSmart
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
```

Configura PostgreSQL y el archivo `.env` (usa `.env.example` como referencia), aplica migraciones y crea el superusuario:

```powershell
python manage.py check
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### 4. Módulo de visión artificial (capstone-vision)

Desde la raíz del repositorio:

```powershell
cd .\Fase_2\Evidencias_Proyecto\Vision-Artificial\capstone-vision
.\Iniciar_LimpIA.bat --verificar
.\Iniciar_LimpIA.bat
```

Consulta la documentación del módulo para calibración de cámara, zonas, fuentes de conteo y modo operativo.

## Equipo de desarrollo

Proyecto desarrollado por estudiantes de Ingeniería en Informática de Duoc UC, sede Antonio Varas (Capstone, sección 802D, 2026).

| Integrante | Rol |
|---|---|
| Martín Vallejos | Líder del proyecto y desarrollador Full Stack |
| Juan Carlos Barraza | Desarrollador de visión artificial |
| Pablo Calfucura | Aseguramiento de calidad (QA) |
| Amaru Orellana | Desarrollador Frontend y UX/UI |

## Documentación

La documentación detallada se encuentra en `Fase_2/Evidencias_Proyecto/` (documentación metodológica y técnica, diagramas, planificación y evidencias).
