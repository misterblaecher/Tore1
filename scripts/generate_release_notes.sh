#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/tore/app"
TEMPLATE="$ROOT/docs/RELEASE_NOTES_TEMPLATE.md"
OUT_DIR="$ROOT/docs/releases"

mkdir -p "$OUT_DIR"

VERSION_LINE=$(sed -n 's/^version:[[:space:]]*//p' "$APP/pubspec.yaml" | head -n 1)
VERSION="${VERSION_LINE%%+*}"
BUILD="${VERSION_LINE##*+}"
ENV_NAME="${1:-all}"
DATE_STAMP=$(date -u +%F)
GIT_SHA=$(git -C "$ROOT" rev-parse --short HEAD)

OUT_FILE="$OUT_DIR/${DATE_STAMP}_${VERSION}+${BUILD}_${ENV_NAME}.md"
cp "$TEMPLATE" "$OUT_FILE"

cat >> "$OUT_FILE" <<EOF2

## Release metadata
- Git SHA: $GIT_SHA
- Version/build: $VERSION+$BUILD
- Target env: $ENV_NAME

## Linked docs
- [Release checklist](../RELEASE_CHECKLIST_MOBILE_RC.md)
- [Ops smoke test](../OPS_SMOKE_TEST_MOBILE_RC.md)
- [Rollback plan](../ROLLBACK_PLAN_MOBILE.md)

## Known risks
### Network and degraded mode
- Validate cache-first fallback and offline-to-online transitions.

### Write safety and idempotency
- Recheck confirm-with-reason presets and duplicate write protections.

### QR/deep link routing
- Confirm mode guards and blocked-state messaging for unsupported links.

### Remote config and update gate
- Verify min supported build/version and diagnostics enablement per env.
EOF2

echo "$OUT_FILE"
