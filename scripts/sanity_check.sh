#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${BASE_URL:-http://localhost:8000}"
SEED_ENV_FILE="${SEED_ENV_FILE:-$ROOT_DIR/.seed.env}"

if [[ -f "$SEED_ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$SEED_ENV_FILE"
fi

: "${BAR_ID:?BAR_ID non défini}"
: "${EVENT_ID:?EVENT_ID non défini}"
: "${ITEM_ID:?ITEM_ID non défini}"
: "${APP_USER_TOKEN:?APP_USER_TOKEN non défini}"
: "${PARTNER_TOKEN:?PARTNER_TOKEN non défini}"

curl -fsS "$BASE_URL/health" >/dev/null
curl -fsS "$BASE_URL/healthz" >/dev/null

python "$ROOT_DIR/scripts/e2e_smoke.py" \
  --base-url "$BASE_URL" \
  --user-token "$APP_USER_TOKEN" \
  --partner-token "$PARTNER_TOKEN" \
  --bar-id "$BAR_ID" \
  --event-id "$EVENT_ID" \
  --item-id "$ITEM_ID"
