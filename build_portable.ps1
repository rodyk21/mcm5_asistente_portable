$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$distRoot = Join-Path $projectRoot "dist"
$buildRoot = Join-Path $projectRoot "build"
$exeName = "MCM5 AI Assistant"
$portableRoot = Join-Path $distRoot $exeName

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "No se encontro el Python del entorno en $pythonExe"
}

Write-Host "Instalando o actualizando PyInstaller..." -ForegroundColor Cyan
& $pythonExe -m pip install pyinstaller

Write-Host "Limpiando salida previa..." -ForegroundColor Cyan
if (Test-Path -LiteralPath $portableRoot) {
    Remove-Item -LiteralPath $portableRoot -Recurse -Force
}

Write-Host "Compilando ejecutable portable..." -ForegroundColor Cyan
& $pythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --distpath $distRoot `
    --workpath $buildRoot `
    --specpath $projectRoot `
    --name $exeName `
    --add-data "$projectRoot\app\static;app\static" `
    --hidden-import "uvicorn.logging" `
    --hidden-import "uvicorn.loops.auto" `
    --hidden-import "uvicorn.protocols.http.auto" `
    --hidden-import "uvicorn.protocols.websockets.auto" `
    --hidden-import "uvicorn.lifespan.on" `
    --collect-submodules "app" `
    "$projectRoot\launcher.py"

Write-Host "Preparando carpeta portable..." -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath $portableRoot)) {
    throw "PyInstaller no genero la carpeta esperada: $portableRoot"
}

Copy-Item -LiteralPath "$projectRoot\.env.example" -Destination (Join-Path $portableRoot ".env.example") -Force

if (Test-Path -LiteralPath "$projectRoot\.env") {
    Write-Warning "Se ha detectado un .env local. No se copiara al portable para evitar distribuir claves privadas."
}

$portableDataRoot = Join-Path $portableRoot "data"
$portableUploadsRoot = Join-Path $portableDataRoot "uploads"
New-Item -ItemType Directory -Path $portableUploadsRoot -Force | Out-Null

Write-Host ""
Write-Host "Portable listo en:" -ForegroundColor Green
Write-Host $portableRoot -ForegroundColor Green
