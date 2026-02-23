#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../tore/app"

echo "[RC verify] Flutter/Dart toolchain checks"
if ! command -v flutter >/dev/null 2>&1; then
  echo "flutter not found. Install Flutter SDK, ensure \`flutter\` is in PATH, then rerun."
  exit 0
fi

echo "[1/4] dart format --set-exit-if-changed lib test"
dart format --set-exit-if-changed lib test || {
  echo "Formatting issues found. Run: dart format lib test"
  exit 1
}

echo "[2/4] flutter analyze (or dart analyze fallback)"
if command -v flutter >/dev/null 2>&1; then
  flutter analyze --no-fatal-warnings --no-fatal-infos
else
  dart analyze
fi

echo "[3/4] flutter test"
flutter test

echo "[4/4] route-surface guard checks"
if rg -n "^\s*AppRoutes\.[A-Za-z0-9_]+\s*:\s*\(_\)\s*=>\s*AppShell\(" lib/rebuild/tore_rebuild_app.dart; then
  echo "Legacy AppShell wired into rebuild routes."
  exit 1
fi

if rg -n "^\s*static const .*=['\"]\/app_shell['\"]" lib/rebuild/routing/app_routes.dart; then
  echo "Legacy /app_shell route exposed in AppRoutes."
  exit 1
fi

echo "RC verification complete."
