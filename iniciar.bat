@echo off
setlocal

cd /d "%~dp0"

if "%MCM5_HOST%"=="" set MCM5_HOST=0.0.0.0
if "%MCM5_PORT%"=="" set MCM5_PORT=8080

if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe launcher.py
  goto :eof
)

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 launcher.py
  goto :eof
)

where python >nul 2>nul
if %errorlevel%==0 (
  python launcher.py
  goto :eof
)

echo No se ha encontrado Python portable ni Python en el PATH.
exit /b 1
