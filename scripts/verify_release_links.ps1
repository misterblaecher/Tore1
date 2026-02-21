$ErrorActionPreference = 'Stop'

param(
  [switch]$SkipAdb,
  [switch]$Ci,
  [string]$PackageName = $(if ($env:ANDROID_PACKAGE_NAME) { $env:ANDROID_PACKAGE_NAME } else { 'com.tore.app' }),
  [string]$PublicUrl = 'https://app.tore.be',
  [string]$Keystore = $(if ($env:ANDROID_KEYSTORE_PATH) { $env:ANDROID_KEYSTORE_PATH } else { '' }),
  [string]$Alias = $(if ($env:ANDROID_KEY_ALIAS) { $env:ANDROID_KEY_ALIAS } else { '' })
)

$rootDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$portalDir = Join-Path $rootDir 'tore-portal'
$assetlinksPath = Join-Path $portalDir 'public/.well-known/assetlinks.json'

function Pass([string]$msg) { Write-Host "PASS: $msg" }
function Fail([string]$msg) { Write-Host "FAIL: $msg"; exit 1 }
function Warn([string]$msg) { Write-Host "WARN: $msg" }

function Require-Command([string]$name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    Fail "Required command not found: $name"
  }
}

Write-Host '[verify_release_links] Checking prerequisites'
Require-Command python
Require-Command npm
Require-Command keytool

$adbAvailable = $null -ne (Get-Command adb -ErrorAction SilentlyContinue)
if ($adbAvailable) { Pass 'adb detected' } else { Warn 'adb not found in PATH (adb section will be skipped)' }

if (-not $Keystore) { Fail 'Missing keystore path. Use -Keystore or ANDROID_KEYSTORE_PATH.' }
if (-not $Alias) { Fail 'Missing key alias. Use -Alias or ANDROID_KEY_ALIAS.' }

Write-Host '[verify_release_links] Generating assetlinks.json'
& python (Join-Path $rootDir 'scripts/gen_assetlinks.py') --keystore-path $Keystore --key-alias $Alias --package-name $PackageName
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Pass 'assetlinks generated'

Write-Host '[verify_release_links] Building tore-portal'
$needCi = $Ci -or -not (Test-Path (Join-Path $portalDir 'node_modules'))
Push-Location $portalDir
try {
  if ($needCi) {
    & npm ci
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  } else {
    Write-Host '[verify_release_links] node_modules already present; skipping npm ci (use -Ci to force)'
  }

  & npm run build
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
  Pop-Location
}
Pass 'tore-portal build'

Write-Host '[verify_release_links] Validating generated assetlinks.json'
& python (Join-Path $rootDir 'scripts/verify_assetlinks.py') $assetlinksPath --package-name $PackageName
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Pass 'assetlinks content validated'

if ($SkipAdb) {
  Warn 'adb verification skipped via -SkipAdb'
  Write-Host 'RESULT: PASS'
  exit 0
}

if (-not $adbAvailable) {
  Warn 'adb verification skipped (adb not installed)'
  Write-Host 'RESULT: PASS'
  exit 0
}

$device = (& adb devices | Select-Object -Skip 1 | Where-Object { $_ -match "\sdevice$" } | Select-Object -First 1)
if (-not $device) {
  Warn 'adb detected but no connected device. Skipping adb checks.'
  Write-Host 'RESULT: PASS'
  exit 0
}

$deviceId = ($device -split "\s+")[0]
Write-Host "[verify_release_links] Running adb app-links verification on device: $deviceId"
& (Join-Path $rootDir 'scripts/verify_app_links_android.ps1') -AndroidAppId $PackageName -DeviceId $deviceId
if ($LASTEXITCODE -ne 0) {
  Write-Host 'RESULT: FAIL'
  exit $LASTEXITCODE
}

$openUrl = "{0}/open?type=join&code=TEST" -f $PublicUrl.TrimEnd('/')
Write-Host "[verify_release_links] Launching VIEW intent: $openUrl"
$adbOutput = & adb -s $deviceId shell am start -W -a android.intent.action.VIEW -d $openUrl 2>&1
$adbCode = $LASTEXITCODE
Write-Host ($adbOutput | Out-String)
if ($adbCode -ne 0) {
  Write-Host 'FAIL: adb VIEW intent failed'
  Write-Host 'RESULT: FAIL'
  exit $adbCode
}

$resultLine = ($adbOutput | Where-Object { $_ -match 'resultCode=' } | Select-Object -Last 1)
if ($resultLine) {
  $match = [regex]::Match($resultLine, 'resultCode=([-0-9]+)')
  if ($match.Success) {
    Pass "Intent resultCode=$($match.Groups[1].Value)"
  } else {
    Warn 'Intent resultCode line found but could not be parsed (best effort)'
  }
} else {
  Warn 'Intent resultCode not found in output (best effort)'
}

Write-Host 'RESULT: PASS'
exit 0
