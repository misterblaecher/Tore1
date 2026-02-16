$ErrorActionPreference = 'Stop'

Write-Host 'Stopping Java/Gradle processes (if any)...' -ForegroundColor Yellow
Get-Process -Name java,gradle,gradlew -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

$pathsToRemove = @(
    'build',
    'android\.gradle',
    'android\app\build'
)

foreach ($relativePath in $pathsToRemove) {
    $fullPath = Join-Path -Path (Get-Location) -ChildPath $relativePath
    if (Test-Path $fullPath) {
        Write-Host "Removing $relativePath" -ForegroundColor Yellow
        Remove-Item -LiteralPath $fullPath -Recurse -Force
    } else {
        Write-Host "Skipping $relativePath (not found)" -ForegroundColor DarkGray
    }
}

Write-Host 'Hard clean complete.' -ForegroundColor Green
