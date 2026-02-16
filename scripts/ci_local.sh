#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/tore-backend"
PORTAL_DIR="$ROOT_DIR/tore-portal"
FLUTTER_DIR="$ROOT_DIR/tore/app"

step() {
  echo
  echo "==> $1"
}

run_backend() {
  step "Backend: pytest -q"
  (
    cd "$BACKEND_DIR"
    pytest -q
  )

  if [[ -n "${BACKEND_URL:-}" ]]; then
    step "Backend smoke: python scripts/smoke_backend.py (BACKEND_URL=$BACKEND_URL)"
    (
      cd "$ROOT_DIR"
      BACKEND_URL="$BACKEND_URL" python scripts/smoke_backend.py
    )
  else
    echo "SKIP backend smoke (BACKEND_URL not set)"
  fi
}

run_portal() {
  step "Portal: npm ci"
  (
    cd "$PORTAL_DIR"
    npm ci
  )

  step "Portal: npm run build"
  (
    cd "$PORTAL_DIR"
    npm run build
  )
}

run_flutter() {
  step "Flutter sanity"
  if command -v flutter >/dev/null 2>&1; then
    (
      cd "$FLUTTER_DIR"
      flutter pub get
      flutter analyze
      flutter test
    )
  else
    echo "SKIP flutter checks (flutter not installed)"
  fi
}

run_grep_guards() {
  step "Grep guards"

  rg -q "TORE_API_BASE_URL" "$ROOT_DIR/docs/mobile_release_android.md"
  rg -q "TORE_ENV" "$ROOT_DIR/docs/mobile_release_android.md"

  local suspicious
  suspicious="$(rg -n "https?://" "$FLUTTER_DIR/lib" | rg -E "(localhost|127\\.0\\.0\\.1|10\\.0\\.2\\.2|api\\.)" || true)"
  if [[ -n "$suspicious" ]]; then
    echo "Found potential hardcoded base URLs in Flutter lib/:"
    echo "$suspicious"
    return 1
  fi

  echo "Grep guards OK"
}

run_backend
run_portal
run_flutter
run_grep_guards

echo
echo "ci_local checks completed successfully"
