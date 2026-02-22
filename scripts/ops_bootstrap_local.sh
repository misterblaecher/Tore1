#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[ops-bootstrap] Starting docker compose services..."
docker compose up -d

echo "[ops-bootstrap] Applying database migrations..."
docker compose exec -T backend-prodlike alembic upgrade head || docker compose exec -T backend alembic upgrade head

echo "[ops-bootstrap] Seeding demo dataset..."
python scripts/seed_demo.py

echo
API_URL="http://localhost:8000"
PORTAL_URL="http://localhost:4173"
APP_URL="https://app.tore.be/open"
echo "[ops-bootstrap] URLs"
echo "- API: $API_URL"
echo "- Portal: $PORTAL_URL"
echo "- App deep link base: $APP_URL"
echo

echo "[ops-bootstrap] QR test links"
echo "- Join: ${APP_URL}?type=join&eventId=1"
echo "- Entry: ${APP_URL}?type=staff_invite&eventId=1&role=entry"
echo "- Bar: ${APP_URL}?type=staff_invite&eventId=1&role=bar"
echo "- Manager: ${APP_URL}?type=orga_invite&eventId=1"

echo "[ops-bootstrap] Done."
