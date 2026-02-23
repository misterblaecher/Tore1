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

echo "Release bundle metadata"
echo "- git sha: $SHA"
echo "- version/build: $VERSION+$BUILD"
echo "- env targets: $TARGET_ENVS"

"$ROOT/scripts/generate_release_notes.sh" all
