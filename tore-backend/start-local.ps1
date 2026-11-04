$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    & "$PSScriptRoot/.venv/Scripts/python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000 --env-file "$PSScriptRoot/.env"
} finally {
    Pop-Location
}
