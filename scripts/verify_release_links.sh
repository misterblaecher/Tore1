#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORTAL_DIR="$ROOT_DIR/tore-portal"
ASSETLINKS_PATH="$PORTAL_DIR/public/.well-known/assetlinks.json"

SKIP_ADB=false
FORCE_CI=false
PACKAGE_NAME="${ANDROID_PACKAGE_NAME:-com.tore.app}"
PUBLIC_URL="https://app.tore.be"
KEYSTORE_PATH="${ANDROID_KEYSTORE_PATH:-}"
KEY_ALIAS="${ANDROID_KEY_ALIAS:-}"

usage() {
  cat <<'EOF'
Usage: verify_release_links.sh [options]

Options:
  --skip-adb                Skip adb verification section.
  --ci                      Force npm ci before build.
  --package-name <name>     Android package name (default: com.tore.app or ANDROID_PACKAGE_NAME).
  --public-url <url>        Public URL used for intent test (default: https://app.tore.be).
  --keystore <path>         Override ANDROID_KEYSTORE_PATH.
  --alias <alias>           Override ANDROID_KEY_ALIAS.
  -h, --help                Show this help.
EOF
}

log() { echo "[verify_release_links] $*"; }
pass() { echo "PASS: $*"; }
fail() { echo "FAIL: $*" >&2; }
warn() { echo "WARN: $*"; }

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    fail "Required command not found: $cmd"
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-adb) SKIP_ADB=true; shift ;;
    --ci) FORCE_CI=true; shift ;;
    --package-name) PACKAGE_NAME="$2"; shift 2 ;;
    --public-url) PUBLIC_URL="$2"; shift 2 ;;
    --keystore) KEYSTORE_PATH="$2"; shift 2 ;;
    --alias) KEY_ALIAS="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) fail "Unknown argument: $1"; usage; exit 1 ;;
  esac
done

log "Checking prerequisites"
require_cmd python
require_cmd npm
require_cmd keytool

ADB_AVAILABLE=false
if command -v adb >/dev/null 2>&1; then
  ADB_AVAILABLE=true
  pass "adb detected"
else
  warn "adb not found in PATH (adb section will be skipped)"
fi

if [[ -z "$KEYSTORE_PATH" ]]; then
  fail "Missing keystore path. Use --keystore or ANDROID_KEYSTORE_PATH."
  exit 1
fi
if [[ -z "$KEY_ALIAS" ]]; then
  fail "Missing key alias. Use --alias or ANDROID_KEY_ALIAS."
  exit 1
fi

log "Generating assetlinks.json"
python "$ROOT_DIR/scripts/gen_assetlinks.py" \
  --keystore-path "$KEYSTORE_PATH" \
  --key-alias "$KEY_ALIAS" \
  --package-name "$PACKAGE_NAME"
pass "assetlinks generated"

log "Building tore-portal"
if [[ "$FORCE_CI" == "true" || ! -d "$PORTAL_DIR/node_modules" ]]; then
  (cd "$PORTAL_DIR" && npm ci)
else
  log "node_modules already present; skipping npm ci (use --ci to force)"
fi
(cd "$PORTAL_DIR" && npm run build)
pass "tore-portal build"

log "Validating generated assetlinks.json"
python "$ROOT_DIR/scripts/verify_assetlinks.py" "$ASSETLINKS_PATH" --package-name "$PACKAGE_NAME"
pass "assetlinks content validated"

if [[ "$SKIP_ADB" == "true" ]]; then
  warn "adb verification skipped via --skip-adb"
  echo "RESULT: PASS"
  exit 0
fi

if [[ "$ADB_AVAILABLE" != "true" ]]; then
  warn "adb verification skipped (adb not installed)"
  echo "RESULT: PASS"
  exit 0
fi

DEVICE_LINE="$(adb devices | awk 'NR>1 && $2=="device" {print $1; exit}')"
if [[ -z "$DEVICE_LINE" ]]; then
  warn "adb detected but no connected device. Skipping adb checks."
  echo "RESULT: PASS"
  exit 0
fi

log "Running adb app-links verification on device: $DEVICE_LINE"
if ! "$ROOT_DIR/scripts/verify_app_links_android.sh" --app-id "$PACKAGE_NAME" --device "$DEVICE_LINE"; then
  fail "verify_app_links_android.sh failed"
  echo "RESULT: FAIL"
  exit 1
fi

OPEN_URL="${PUBLIC_URL%/}/open?type=join&code=TEST"
log "Launching VIEW intent: $OPEN_URL"
set +e
ADB_OUTPUT="$(adb -s "$DEVICE_LINE" shell am start -W -a android.intent.action.VIEW -d "$OPEN_URL" 2>&1)"
ADB_CODE=$?
set -e

echo "$ADB_OUTPUT"
if [[ $ADB_CODE -ne 0 ]]; then
  fail "adb VIEW intent failed"
  echo "RESULT: FAIL"
  exit 1
fi

RESULT_CODE="$(sed -n 's/.*resultCode=\([-0-9]\+\).*/\1/p' <<<"$ADB_OUTPUT" | tail -n1)"
if [[ -n "$RESULT_CODE" ]]; then
  pass "Intent resultCode=$RESULT_CODE"
else
  warn "Intent resultCode not found in output (best effort)"
fi

echo "RESULT: PASS"
