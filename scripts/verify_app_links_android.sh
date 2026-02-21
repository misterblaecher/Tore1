#!/usr/bin/env bash
set -euo pipefail

ANDROID_APP_ID="${ANDROID_APP_ID:-be.tore.app}"
DEVICE_ID="${DEVICE_ID:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --app-id)
      ANDROID_APP_ID="$2"
      shift 2
      ;;
    --device)
      DEVICE_ID="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: $0 [--app-id <applicationId>] [--device <deviceId>]" >&2
      exit 1
      ;;
  esac
done

if ! command -v adb >/dev/null 2>&1; then
  echo "FAIL: adb not found in PATH"
  exit 1
fi

ADB=(adb)
if [[ -n "$DEVICE_ID" ]]; then
  ADB+=(-s "$DEVICE_ID")
fi

pass=true

run_pm_command() {
  local output
  if output="$(${ADB[@]} shell pm "$@" "$ANDROID_APP_ID" 2>&1)"; then
    echo "PASS: pm $* $ANDROID_APP_ID"
    echo "$output"
    return 0
  fi

  echo "$output"
  if grep -qiE "Unknown command|Unknown option|not found" <<<"$output"; then
    echo "WARN: pm $* not supported on this Android version/device."
    echo "      Fallback: open Settings > Apps > $ANDROID_APP_ID > Open by default"
    return 0
  fi

  echo "FAIL: pm $* $ANDROID_APP_ID"
  pass=false
  return 1
}

run_pm_command verify-app-links --re-verify
run_pm_command get-app-links

echo "Running VIEW intent test..."
if output="$(${ADB[@]} shell am start -W -a android.intent.action.VIEW -d "https://app.tore.be/open?type=event&id=test" 2>&1)"; then
  echo "PASS: am start VIEW intent"
  echo "$output"
else
  echo "FAIL: am start VIEW intent"
  echo "$output"
  pass=false
fi

if [[ "$pass" == "true" ]]; then
  echo "RESULT: PASS"
  exit 0
fi

echo "RESULT: FAIL"
exit 1
