$ErrorActionPreference = 'Stop'
Push-Location "$PSScriptRoot/../backend"
try { uv run python -m app.cli export-openapi ../frontend/openapi.json; if ($LASTEXITCODE) { throw 'OpenAPI export failed' } } finally { Pop-Location }
Push-Location "$PSScriptRoot/../frontend"
try { npx openapi-typescript openapi.json -o src/api/generated.ts; if ($LASTEXITCODE) { throw 'Type generation failed' } } finally { Pop-Location }
