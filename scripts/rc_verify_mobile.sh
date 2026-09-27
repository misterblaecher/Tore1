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

echo "[4/4] canonical runtime guard checks"
if ! rg -n "runApp\(const ProviderScope\(child: ToreMvpApp\(\)\)\)" lib/main.dart; then
  echo "Canonical ToreMvpApp runtime is not wired from lib/main.dart."
  exit 1
fi

if test -e lib/app_shell.dart; then
  echo "Legacy lib/app_shell.dart must remain orphaned and removed."
  exit 1
fi

if test -d lib/rebuild; then
  echo "Legacy lib/rebuild must remain orphaned and removed."
  exit 1
fi

if rg -n "app_shell\.dart|package:tore/rebuild" lib test; then
  echo "Legacy mobile runtime references found."
  exit 1
fi

echo "RC verification complete."
