#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/tore-backend"
SEED_EXPORT_PATH="${SEED_EXPORT_PATH:-$ROOT_DIR/.seed.env}"

cd "$BACKEND_DIR"
alembic upgrade head

cd "$ROOT_DIR"
SEED_JSON="$(python scripts/seed_minimal.py)"

echo "$SEED_JSON" | python - "$SEED_EXPORT_PATH" <<'PY'
import json
import sys
from pathlib import Path

seed = json.loads(sys.stdin.read())
out = Path(sys.argv[1])
lines = [
    f"BAR_ID={seed['bar_id']}",
    f"EVENT_ID={seed['event_id']}",
    f"ZONE_ID={seed['zone_id']}",
    f"ITEM_ID={seed['item_id']}",
    f"APP_USER_TOKEN={seed['app_user_token']}",
    f"PARTNER_TOKEN={seed['partner_token']}",
]
out.write_text("\n".join(lines) + "\n")
print(out.as_posix())
PY

echo "Bootstrap terminé. Variables seed écrites dans: $SEED_EXPORT_PATH"
