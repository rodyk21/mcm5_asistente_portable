@echo off
setlocal

cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -m venv .venv
  call .venv\Scripts\activate.bat
  py -3 -m pip install --upgrade pip
  py -3 -m pip install -r requirements.txt
  goto :eof
)

where python >nul 2>nul
if %errorlevel%==0 (
  python -m venv .venv
  call .venv\Scripts\activate.bat
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  goto :eof
)

echo No se ha encontrado Python en el PATH.
echo Instala Python 3.11+ y vuelve a ejecutar este archivo.
exit /b 1
