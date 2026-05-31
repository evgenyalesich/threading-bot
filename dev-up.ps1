param(
    [switch]$SkipInstall,
    [switch]$SkipMigrations
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

if (-not (Test-Path (Join-Path $backendDir ".env"))) {
    throw "backend/.env not found. Create it before startup."
}

Write-Host "[1/4] Checking backend dependencies..."
if (-not $SkipInstall) {
    uv sync --project $backendDir
}

Write-Host "[2/4] Checking frontend dependencies..."
if (-not $SkipInstall) {
    npm --prefix $frontendDir install
}

if (-not $SkipMigrations) {
    Write-Host "[3/4] Running migrations..."
    Push-Location $backendDir
    try {
        $env:DEBUG = "false"
        uv run alembic upgrade head
    }
    finally {
        Pop-Location
    }
} else {
    Write-Host "[3/4] Migrations skipped."
}

Write-Host "[4/4] Starting services..."

$backendCmd = "Set-Location `"$backendDir`"; `$env:DEBUG='false'; uv run uvicorn app.main:app --reload --port 8000"
$frontendCmd = "Set-Location `"$frontendDir`"; npm run dev"

$backendProc = Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -PassThru

Write-Host "Waiting for backend on http://localhost:8000 ..."
$backendReady = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $probe = Invoke-WebRequest -Uri "http://localhost:8000/api/health" -Method Get -TimeoutSec 2
        if ($probe.StatusCode -ge 200 -and $probe.StatusCode -lt 500) {
            $backendReady = $true
            break
        }
    }
    catch {
        # backend not ready yet
    }
}

if (-not $backendReady) {
    Write-Warning "Backend did not become ready in time. Check backend window for errors."
}

Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd | Out-Null

Write-Host "Done. Backend: http://localhost:8000 | Frontend: http://localhost:5173"
