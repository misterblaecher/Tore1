$ErrorActionPreference = 'Stop'

$flutterBin = 'C:\Users\miste\Documents\flutter\bin'
$pubCache = 'C:\Users\miste\Documents\flutter_pub_cache'

if (-not ($env:Path -split ';' | Where-Object { $_ -eq $flutterBin })) {
    $env:Path = "$flutterBin;$env:Path"
}

$env:PUB_CACHE = $pubCache

Write-Host 'Environment configured for Windows build stability:' -ForegroundColor Cyan
Write-Host "  FLUTTER_BIN = $flutterBin"
Write-Host "  PUB_CACHE   = $env:PUB_CACHE"
Write-Host ''
Write-Host 'where flutter:' -ForegroundColor Yellow
where.exe flutter
Write-Host ''
Write-Host 'flutter --version:' -ForegroundColor Yellow
flutter --version
Write-Host ''
Write-Host 'PUB_CACHE:' -ForegroundColor Yellow
Write-Output $env:PUB_CACHE
