$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$listenAddress = if ($env:APP_HOST) { $env:APP_HOST } else { "127.0.0.1" }
$port = if ($env:APP_PORT) { $env:APP_PORT } else { "8000" }

if (-not (Test-Path -LiteralPath $python)) {
    throw ".venv was not found. Follow the README installation steps first."
}

try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/health" -TimeoutSec 2
    if ($health.status -eq "ok" -and $health.provider -eq "nvidia-nim") {
        Write-Host "The application is already running at http://127.0.0.1:$port"
        exit 0
    }
} catch {
    # Port 8000 is not serving this application yet; continue startup.
}

Push-Location (Join-Path $projectRoot "frontend")
try {
    & npm.cmd run build
} finally {
    Pop-Location
}

Push-Location (Join-Path $projectRoot "backend")
try {
    & $python -m alembic upgrade head
    & $python -m app.cli init-db
    & $python -m uvicorn app.main:app --host $listenAddress --port $port
} finally {
    Pop-Location
}
