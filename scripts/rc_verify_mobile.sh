#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../tore/app"

echo "[RC verify] Flutter/Dart toolchain checks"
if ! command -v dart >/dev/null 2>&1; then
  echo "dart not found. Install Flutter SDK (includes dart) then rerun."
  exit 0
fi

echo "[1/3] dart format --set-exit-if-changed lib test"
dart format --set-exit-if-changed lib test || {
  echo "Formatting issues found. Run: dart format lib test"
  exit 1
}

echo "[2/3] flutter analyze (or dart analyze fallback)"
if command -v flutter >/dev/null 2>&1; then
  flutter analyze
else
  dart analyze
fi

echo "[3/3] dart test"
dart test

echo "RC verification complete."
