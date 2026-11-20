# Start the isolated local PostgreSQL cluster and the real FastAPI backend.
# Run from Dev/Backend: powershell -ExecutionPolicy Bypass -File scripts/start_windows_demo.ps1
$ErrorActionPreference = 'Stop'
$backend = Split-Path -Parent $PSScriptRoot
Set-Location $backend

$python = Join-Path $backend '.venv\Scripts\python.exe'
$cluster = Join-Path $backend '.venv\demo-postgres-data'
$log = Join-Path $backend '.venv\demo-postgres.log'
$pgCtl = 'C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe'

if (-not (Test-Path -LiteralPath $python)) { throw 'Backend virtual environment is missing.' }
if (-not (Test-Path -LiteralPath $cluster)) { throw 'Local demo database is missing.' }
if (-not (Test-Path -LiteralPath $pgCtl)) { throw 'PostgreSQL 18 is missing.' }
if (-not (Test-Path -LiteralPath '.env')) { throw 'Backend .env is missing.' }

& $pgCtl -D $cluster status *> $null
if ($LASTEXITCODE -ne 0) {
    & $pgCtl -D $cluster -l $log -o '-p 55432 -h 127.0.0.1' -w start
    if ($LASTEXITCODE -ne 0) { throw 'Could not start the local demo database.' }
}

# A stale Windows environment variable can override the newer key in .env.
# Clear it for this process only; no system setting is changed.
if (Select-String -LiteralPath '.env' -Pattern '^OPENAI_API_KEY=.+' -Quiet) {
    Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
}

& $python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
& $python -m uvicorn app.main:app --host 127.0.0.1 --port 5000
