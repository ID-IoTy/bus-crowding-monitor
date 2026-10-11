# SmartBus Central Server - one-command demo (Windows PowerShell)
#
# Initializes the DB, seeds the network, simulates a day of history,
# (optionally) trains the ML model, starts the server, streams live events,
# and prints a sample of the public API responses.
#
# Usage:  .\demo.ps1

$ErrorActionPreference = "Stop"
$py = ".\venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "Virtual environment not found. Create it first:" -ForegroundColor Yellow
    Write-Host "  python -m venv venv; .\venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

Write-Host "`n[1/6] Initializing database..." -ForegroundColor Cyan
& $py -m app.db.init_db

Write-Host "`n[2/6] Seeding routes, stops, buses, schedule..." -ForegroundColor Cyan
& $py seeder.py

Write-Host "`n[3/6] Simulating a day of historical data..." -ForegroundColor Cyan
& $py -m simulator.simulate_day --date 2024-01-15

Write-Host "`n[4/6] Training ML model (falls back to rule-based if sklearn missing)..." -ForegroundColor Cyan
& $py -m ml.train

Write-Host "`n[5/6] Starting server in a background job..." -ForegroundColor Cyan
$server = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    & ".\venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
}
Start-Sleep -Seconds 6

try {
    Write-Host "`n[6/6] Streaming live events + querying the API..." -ForegroundColor Cyan
    & $py -m simulator.live_feed --server "http://127.0.0.1:8000" --speed 200 --trips 1

    $h = @{ "X-API-Key" = "dev-key" }
    Write-Host "`n--- GET /stops/R1-S20/status ---" -ForegroundColor Green
    Invoke-RestMethod -Uri "http://127.0.0.1:8000/stops/R1-S20/status" -Headers $h | ConvertTo-Json -Depth 5

    Write-Host "`n--- GET /admin/anomalies?status=PENDING ---" -ForegroundColor Green
    $ha = @{ "X-API-Key" = "admin-key" }
    Invoke-RestMethod -Uri "http://127.0.0.1:8000/admin/anomalies?status=PENDING" -Headers $ha | ConvertTo-Json -Depth 5
}
finally {
    Write-Host "`nStopping server..." -ForegroundColor Cyan
    Stop-Job $server -ErrorAction SilentlyContinue
    Remove-Job $server -ErrorAction SilentlyContinue
}

Write-Host "`nDemo complete. Start the server yourself with:" -ForegroundColor Yellow
Write-Host "  .\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
