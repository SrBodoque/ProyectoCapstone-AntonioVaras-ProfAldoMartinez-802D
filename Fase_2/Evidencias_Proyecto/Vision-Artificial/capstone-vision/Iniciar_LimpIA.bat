@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" instalar_limpia.py %*
  goto done
)
if defined LIMPIA_PYTHON (
  "%LIMPIA_PYTHON%" instalar_limpia.py %*
  goto done
)
py -3.13 -c "import sys; assert sys.version_info[:2]==(3,13)" >nul 2>nul
if not errorlevel 1 (
  py -3.13 instalar_limpia.py %*
  goto done
)
python -c "import sys; assert sys.version_info[:2]==(3,13)" >nul 2>nul
if not errorlevel 1 (
  python instalar_limpia.py %*
  goto done
)
echo Instale Python 3.13 x64 desde python.org y vuelva a intentar.
pause
exit /b 2
:done
set "result=%errorlevel%"
if not "%result%"=="0" pause
exit /b %result%
