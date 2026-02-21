$ErrorActionPreference = 'Stop'

param(
  [string]$AndroidAppId = $(if ($env:ANDROID_APP_ID) { $env:ANDROID_APP_ID } else { 'be.tore.app' }),
  [string]$DeviceId = $(if ($env:DEVICE_ID) { $env:DEVICE_ID } else { '' })
)

$pass = $true

if (-not (Get-Command adb -ErrorAction SilentlyContinue)) {
  Write-Host 'FAIL: adb not found in PATH'
  exit 1
}

$adbArgs = @()
if ($DeviceId) {
  $adbArgs += @('-s', $DeviceId)
}

function Run-PmCommand {
  param([string[]]$PmArgs)

  $result = & adb @adbArgs shell pm @PmArgs $AndroidAppId 2>&1
  $code = $LASTEXITCODE
  $text = ($result | Out-String)

  if ($code -eq 0) {
    Write-Host "PASS: pm $($PmArgs -join ' ') $AndroidAppId"
    Write-Host $text
    return
  }

  if ($text -match 'Unknown command|Unknown option|not found') {
    Write-Host "WARN: pm $($PmArgs -join ' ') not supported on this Android version/device."
    Write-Host "      Fallback: Settings > Apps > $AndroidAppId > Open by default"
    return
  }

  Write-Host "FAIL: pm $($PmArgs -join ' ') $AndroidAppId"
  Write-Host $text
  $script:pass = $false
}

Run-PmCommand -PmArgs @('verify-app-links', '--re-verify')
Run-PmCommand -PmArgs @('get-app-links')

Write-Host 'Running VIEW intent test...'
$intentResult = & adb @adbArgs shell am start -W -a android.intent.action.VIEW -d 'https://app.tore.be/open?type=event&id=test' 2>&1
if ($LASTEXITCODE -eq 0) {
  Write-Host 'PASS: am start VIEW intent'
  Write-Host ($intentResult | Out-String)
} else {
  Write-Host 'FAIL: am start VIEW intent'
  Write-Host ($intentResult | Out-String)
  $pass = $false
}

if ($pass) {
  Write-Host 'RESULT: PASS'
  exit 0
}

Write-Host 'RESULT: FAIL'
exit 1
