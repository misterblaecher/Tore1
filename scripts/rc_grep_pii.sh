#!/usr/bin/env bash
set -euo pipefail

ROOT="$(dirname "$0")/.."
APP="$ROOT/tore/app"

cd "$ROOT"

echo "[PII grep] checking canonical HTTP logging for banned raw secrets"
if rg -n "Authorization:|Bearer [A-Za-z0-9\._\-]{8,}|token=|auth=|key=" "$APP/lib/core/network/api_client.dart"; then
  echo "Potential raw secret patterns found above."
  exit 1
fi

echo "[PII grep] checking canonical scrubber usage"
rg -n "scrubLogFields|scrubUrlQueryParams|redactFreeText" "$APP/lib/core/logging/pii_redactor.dart" >/dev/null
rg -n "scrubUrlQueryParams" "$APP/lib/core/network/api_client.dart" >/dev/null

echo "PII static checks passed."
