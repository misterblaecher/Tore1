$ErrorActionPreference = 'Stop'

$rootDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendDir = Join-Path $rootDir 'tore-backend'
$portalDir = Join-Path $rootDir 'tore-portal'
$flutterDir = Join-Path $rootDir 'tore/app'

function Step([string]$message) {
  Write-Host ""
  Write-Host "==> $message"
}

function Run-Backend {
  Step 'Backend: pytest -q'
  Push-Location $backendDir
  try {
    pytest -q
  }
  finally {
    Pop-Location
  }

  if ($env:BACKEND_URL) {
    Step "Backend smoke: python scripts/smoke_backend.py (BACKEND_URL=$($env:BACKEND_URL))"
    Push-Location $rootDir
    try {
      python scripts/smoke_backend.py
    }
    finally {
      Pop-Location
    }
  }
  else {
    Write-Host 'SKIP backend smoke (BACKEND_URL not set)'
  }
}

function Run-Portal {
  Step 'Portal: npm ci'
  Push-Location $portalDir
  try {
    npm ci
  }
  finally {
    Pop-Location
  }

  Step 'Portal: npm run build'
  Push-Location $portalDir
  try {
    npm run build
  }
  finally {
    Pop-Location
  }
}

function Run-Flutter {
  Step 'Flutter sanity'
  $flutterCmd = Get-Command flutter -ErrorAction SilentlyContinue
  if ($null -eq $flutterCmd) {
    Write-Host 'SKIP flutter checks (flutter not installed)'
    return
  }

  Push-Location $flutterDir
  try {
    flutter pub get
    flutter analyze
    flutter test
  }
  finally {
    Pop-Location
  }
}

function Run-GrepGuards {
  Step 'Grep guards'

  $mobileDoc = Join-Path $rootDir 'docs/mobile_release_android.md'
  rg -q 'TORE_API_BASE_URL' $mobileDoc
  rg -q 'TORE_ENV' $mobileDoc

  $matches = rg -n 'https?://' (Join-Path $flutterDir 'lib') | rg -E '(localhost|127\.0\.0\.1|10\.0\.2\.2|api\.)'
  if ($LASTEXITCODE -eq 0 -and $matches) {
    Write-Host 'Found potential hardcoded base URLs in Flutter lib/:'
    Write-Host $matches
    throw 'Hardcoded base URLs found'
  }

  Write-Host 'Grep guards OK'
}

Run-Backend
Run-Portal
Run-Flutter
Run-GrepGuards

Write-Host ''
Write-Host 'ci_local checks completed successfully'
