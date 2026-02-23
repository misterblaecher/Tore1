#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/tore/app"

"$ROOT/scripts/rc_verify_mobile.sh"
"$ROOT/scripts/rc_grep_pii.sh"

VERSION_LINE=$(sed -n 's/^version:[[:space:]]*//p' "$APP/pubspec.yaml" | head -n 1)
VERSION="${VERSION_LINE%%+*}"
BUILD="${VERSION_LINE##*+}"
SHA=$(git -C "$ROOT" rev-parse --short HEAD)
TARGET_ENVS="dev,stage,prod"

DOCS_REQUIRED=(
  "$ROOT/docs/NIGHT1_CHECKLIST.md"
  "$ROOT/docs/REMOTE_CONFIG_SEED.md"
  "$ROOT/docs/RELEASE_PROCESS_MOBILE.md"
  "$ROOT/docs/ROLLBACK_PLAN_MOBILE.md"
)

MISSING_DOCS=()
for doc in "${DOCS_REQUIRED[@]}"; do
  if [[ ! -f "$doc" ]]; then
    MISSING_DOCS+=("$doc")
  fi
done

echo "Release bundle metadata"
echo "- git sha: $SHA"
echo "- version/build: $VERSION+$BUILD"
echo "- env targets: $TARGET_ENVS"

echo "Documentation checks"
if [[ ${#MISSING_DOCS[@]} -gt 0 ]]; then
  for doc in "${MISSING_DOCS[@]}"; do
    echo "- missing: $doc"
  done
  echo "Critical release docs missing; aborting release bundle."
  exit 1
else
  for doc in "${DOCS_REQUIRED[@]}"; do
    echo "- found: $doc"
  done
fi

NOTES_PATH=$("$ROOT/scripts/generate_release_notes.sh" all)
echo "Release notes generated: $NOTES_PATH"
