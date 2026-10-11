$ErrorActionPreference = 'Stop'
$project = (Resolve-Path "$PSScriptRoot/..").Path
Start-Process -FilePath 'uv' -ArgumentList @('run','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory "$project/backend" -WindowStyle Hidden
Start-Process -FilePath 'cmd.exe' -ArgumentList @('/c','npm run dev -- --port 5174 --strictPort') -WorkingDirectory "$project/frontend" -WindowStyle Hidden
Write-Host 'BusFlow: http://127.0.0.1:5174/#citizens (backend: localhost:8000). Run the mock separately when needed.'
