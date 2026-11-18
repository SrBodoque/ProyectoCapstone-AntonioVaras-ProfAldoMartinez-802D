@echo off
setlocal EnableExtensions DisableDelayedExpansion
for %%I in ("%~dp0..") do set "VISION_ROOT=%%~fI"
cd /d "%VISION_ROOT%"
echo === LIMPIAVISION OPERATIVO V0.5 MEJORADA ===
if not exist "%VISION_ROOT%\Iniciar_LimpIA.bat" (
    echo ERROR: Falta el Iniciar_LimpIA.bat original de Vision.
    goto fail
)
if not exist "%~dp0preparar_limpia_operativa.py" (
    echo ERROR: Falta preparar_limpia_operativa.py.
    goto fail
)
if not exist "%~dp0lanzador_operativo.py" (
    echo ERROR: Falta lanzador_operativo.py.
    goto fail
)
rem Usamos el instalador original SOLO en modo de comprobacion.
rem Nunca ejecutamos el launcher original del companero.
set "VISION_CANDIDATE="
if defined LIMPIA_PYTHON_VISION if exist "%LIMPIA_PYTHON_VISION%" set "VISION_CANDIDATE=%LIMPIA_PYTHON_VISION%"
if not defined VISION_CANDIDATE if exist "%VISION_ROOT%\.venv\Scripts\python.exe" set "VISION_CANDIDATE=%VISION_ROOT%\.venv\Scripts\python.exe"
if not defined VISION_CANDIDATE if exist "%USERPROFILE%\Documents\GitHub\LimpIAvision-integracion-vision-django\Fase_2\Evidencias_Proyecto\Vision-Artificial\capstone-vision\.venv\Scripts\python.exe" set "VISION_CANDIDATE=%USERPROFILE%\Documents\GitHub\LimpIAvision-integracion-vision-django\Fase_2\Evidencias_Proyecto\Vision-Artificial\capstone-vision\.venv\Scripts\python.exe"
if defined VISION_CANDIDATE (
    call "%VISION_ROOT%\Iniciar_LimpIA.bat" --python "%VISION_CANDIDATE%" --device cuda:0 --check
) else (
    call "%VISION_ROOT%\Iniciar_LimpIA.bat" --device cuda:0 --check
)
if errorlevel 1 (
    echo ERROR: No se pudo validar el entorno de vision.
    goto fail
)
rem Si el instalador creo un entorno nuevo, dar prioridad al nuevo .venv local.
set "PYTHON_BOOT="
if exist "%VISION_ROOT%\.venv\Scripts\python.exe" set "PYTHON_BOOT=%VISION_ROOT%\.venv\Scripts\python.exe"
if not defined PYTHON_BOOT if defined VISION_CANDIDATE set "PYTHON_BOOT=%VISION_CANDIDATE%"
if not defined PYTHON_BOOT (
    echo ERROR: La comprobacion termino pero no hay Python operativo identificado.
    echo Configure LIMPIA_PYTHON_VISION con la ruta del entorno valido.
    goto fail
)
rem Compartir al preparador la misma ruta explicita comprobada.
if defined VISION_CANDIDATE set "LIMPIA_PYTHON_VISION=%VISION_CANDIDATE%"
echo.
echo === VERIFICACION DE HIGIENESMART ===
"%PYTHON_BOOT%" "%~dp0preparar_limpia_operativa.py" %*
set "RESULT=%errorlevel%"
if not "%RESULT%"=="0" pause
exit /b %RESULT%
:fail
pause
exit /b 1
