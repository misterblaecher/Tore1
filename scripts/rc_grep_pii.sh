#!/usr/bin/env bash
set -euo pipefail

ROOT="$(dirname "$0")/.."
APP="$ROOT/tore/app"

cd "$ROOT"

echo "[PII grep] checking rebuild diagnostics/logging code for banned raw secrets"
if rg -n "Authorization:|Bearer [A-Za-z0-9\._\-]{8,}|token=|auth=|key=" "$APP/lib/rebuild" --glob '*.dart'; then
  echo "Potential raw secret patterns found above."
  exit 1
fi

echo "[PII grep] checking scrubber usage"
rg -n "scrubJsonMap|scrubUrlQueryParams|_redactFreeText" "$APP/lib/rebuild/services/client_log.dart" >/dev/null
rg -n "scrubJsonMap" "$APP/lib/rebuild/ui/screens/dev/diagnostics_screen.dart" >/dev/null

echo "PII static checks passed."
