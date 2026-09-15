param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repo "tore-backend"
$site = Join-Path $repo "tore_site"

Write-Host "TORÈ Forum - prévisualisation locale sûre" -ForegroundColor Cyan
Write-Host "Repo: $repo"

Push-Location $repo
try {
    $branch = (git branch --show-current).Trim()
    Write-Host "Branche courante: $branch"
    if ($branch -ne "codex/forum-integration-2026-09-15") {
        throw "Cette prévisualisation doit être lancée depuis codex/forum-integration-2026-09-15. Aucun checkout automatique n'est effectué."
    }

    $dirty = git status --porcelain
    if ($dirty) {
        Write-Warning "Le worktree contient des modifications locales. Elles ne seront ni stashées, ni supprimées, ni modifiées par ce script."
    }

    foreach ($port in 8001, 5173) {
        $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($listener) {
            $process = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
            $name = if ($process) { $process.ProcessName } else { "PID $($listener.OwningProcess)" }
            throw "Le port $port est déjà occupé par $name. Arrête le processus explicitement avant de lancer la preview; ce script ne tue aucun processus."
        }
    }

    Write-Host "Sauvegarde des bases SQLite locales détectées..." -ForegroundColor Yellow
    $dbFiles = Get-ChildItem -Path $backend -File -Include *.db,*.sqlite,*.sqlite3 -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch "\\(node_modules|\.venv|venv)\\" }
    if ($dbFiles) {
        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $backupDir = Join-Path $backend "local-db-backups\forum-preview-$stamp"
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
        foreach ($db in $dbFiles) {
            Copy-Item $db.FullName (Join-Path $backupDir $db.Name) -Force
            Write-Host "  backup: $($db.Name)"
        }
        Write-Host "Backups: $backupDir"
    } else {
        Write-Host "  aucune base SQLite trouvée dans tore-backend"
    }

    Write-Host "Vérification Alembic en lecture seule..." -ForegroundColor Yellow
    Push-Location $backend
    try {
        $env:RUN_MIGRATIONS = "0"
        $env:TORE_AUTO_DB_BOOTSTRAP = "0"
        python -m alembic current
        if ($LASTEXITCODE -ne 0) {
            throw "Alembic ne reconnaît pas l'état courant de la base. Si la base locale contient une révision 0014 absente du code, restaure/inspecte-la avant toute migration."
        }
    } finally {
        Pop-Location
    }

    if (-not $SkipInstall) {
        Write-Host "Installation/vérification des dépendances frontend..." -ForegroundColor Yellow
        Push-Location $site
        try {
            npm install
            if ($LASTEXITCODE -ne 0) { throw "npm install a échoué." }
        } finally {
            Pop-Location
        }
    }

    $backendCommand = "Set-Location '$backend'; `$env:RUN_MIGRATIONS='0'; `$env:TORE_AUTO_DB_BOOTSTRAP='0'; python -m uvicorn main:app --host 127.0.0.1 --port 8001"
    $siteCommand = "Set-Location '$site'; `$env:VITE_API_BASE_URL='http://127.0.0.1:8001'; npm run dev -- --host 127.0.0.1 --port 5173"

    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCommand
    Start-Sleep -Seconds 1
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $siteCommand

    Write-Host "" 
    Write-Host "Preview: http://127.0.0.1:5173/forum" -ForegroundColor Green
    Write-Host "Backend: http://127.0.0.1:8001" -ForegroundColor Green
    Write-Host "Les migrations automatiques sont désactivées pour cette preview." -ForegroundColor Yellow
    Write-Host "Aucune donnée de démonstration du forum autonome n'est importée."
} finally {
    Pop-Location
}
