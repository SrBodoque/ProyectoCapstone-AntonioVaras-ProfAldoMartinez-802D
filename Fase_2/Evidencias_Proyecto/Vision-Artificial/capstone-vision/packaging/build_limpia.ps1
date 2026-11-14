param([Parameter(Mandatory=$true)][string]$BuildPython)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& $BuildPython -c 'import PyInstaller, torch, torchvision, cv2, ultralytics, tkinter, PIL, yaml, lap; print("Build dependencies available")'
if ($LASTEXITCODE -ne 0) { throw 'Faltan dependencias en el entorno de build. No se instala ni actualiza nada automaticamente.' }
$runRoot = Join-Path $project ('logs\packaging\' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $runRoot | Out-Null
& $BuildPython -m PyInstaller --noconfirm --workpath (Join-Path $runRoot 'build') --distpath (Join-Path $runRoot 'dist') (Join-Path $PSScriptRoot 'LimpIA.spec')
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller fallo. Conservar los logs y revisar antes de distribuir.' }
Write-Output ('Candidato NO VALIDADO: ' + (Join-Path $runRoot 'dist\LimpIA\LimpIA.exe'))
Write-Output 'Ejecutar los ensayos de MP4, camara, calibracion y cierre antes de distribuir.'
