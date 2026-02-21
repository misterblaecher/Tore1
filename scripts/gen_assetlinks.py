#!/usr/bin/env python3
"""Generate Digital Asset Links file from template + release keystore SHA256."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_GRADLE_FILE = ROOT_DIR / "tore" / "app" / "android" / "app" / "build.gradle.kts"
ASSETLINKS_DIR = ROOT_DIR / "tore-portal" / "public" / ".well-known"
TEMPLATE_FILE = ASSETLINKS_DIR / "assetlinks.template.json"
OUTPUT_FILE = ASSETLINKS_DIR / "assetlinks.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Android Digital Asset Links JSON")
    parser.add_argument(
        "--package-name",
        default=os.getenv("ANDROID_PACKAGE_NAME"),
        help="Android package name (default: ANDROID_PACKAGE_NAME or build.gradle.kts)",
    )
    parser.add_argument(
        "--keystore-path",
        default=os.getenv("ANDROID_KEYSTORE_PATH"),
        help="Path to release keystore (or ANDROID_KEYSTORE_PATH)",
    )
    parser.add_argument(
        "--key-alias",
        default=os.getenv("ANDROID_KEY_ALIAS"),
        help="Keystore alias (or ANDROID_KEY_ALIAS)",
    )
    parser.add_argument(
        "--template",
        default=str(TEMPLATE_FILE),
        help=f"Template file path (default: {TEMPLATE_FILE})",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_FILE),
        help=f"Output file path (default: {OUTPUT_FILE})",
    )
    return parser.parse_args()


def infer_package_name(gradle_file: Path) -> str:
    if not gradle_file.exists():
        raise RuntimeError(f"build.gradle.kts not found: {gradle_file}")

    content = gradle_file.read_text(encoding="utf-8")
    match = re.search(r'applicationId\s*=\s*"([^"]+)"', content)
    if not match:
        raise RuntimeError(f"Unable to infer applicationId from {gradle_file}")
    return match.group(1)


def extract_sha256(keystore_path: Path, key_alias: str) -> str:
    keytool = shutil.which("keytool")
    if not keytool:
        raise RuntimeError("keytool command not found in PATH")
    if not keystore_path.exists():
        raise RuntimeError(f"Keystore not found: {keystore_path}")

    command = [
        keytool,
        "-list",
        "-v",
        "-keystore",
        str(keystore_path),
        "-alias",
        key_alias,
    ]

    store_pass = os.getenv("ANDROID_STOREPASS")
    key_pass = os.getenv("ANDROID_KEYPASS")
    if store_pass:
        command.extend(["-storepass", store_pass])
    if key_pass:
        command.extend(["-keypass", key_pass])

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        details = stderr if stderr else stdout
        raise RuntimeError(f"keytool failed: {details}") from exc

    match = re.search(r"SHA256:\s*([0-9A-Fa-f:]+)", result.stdout)
    if not match:
        raise RuntimeError("SHA256 fingerprint not found in keytool output")

    return match.group(1).replace(":", "").upper()


def main() -> int:
    args = parse_args()

    package_name = args.package_name or infer_package_name(DEFAULT_GRADLE_FILE)
    if not args.keystore_path:
        raise RuntimeError("Missing keystore path (use --keystore-path or ANDROID_KEYSTORE_PATH)")
    if not args.key_alias:
        raise RuntimeError("Missing key alias (use --key-alias or ANDROID_KEY_ALIAS)")

    keystore_path = Path(args.keystore_path).expanduser().resolve()
    sha256 = extract_sha256(keystore_path, args.key_alias)

    template_path = Path(args.template).expanduser().resolve()
    if not template_path.exists():
        raise RuntimeError(f"Template not found: {template_path}")

    data = json.loads(template_path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise RuntimeError("Template must be a non-empty JSON list")

    target = data[0].get("target", {})
    target["package_name"] = package_name
    target["sha256_cert_fingerprints"] = [sha256]
    data[0]["target"] = target

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"SHA256 release fingerprint: {sha256}")
    print(f"Generated: {output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
