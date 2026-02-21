#!/usr/bin/env python3
"""Validate Android Digital Asset Links content."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FINGERPRINT_PATTERN = re.compile(r"^(?:[0-9A-F]{2}:){31}[0-9A-F]{2}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate assetlinks.json structure and fingerprint format")
    parser.add_argument("assetlinks_path", help="Path to assetlinks.json")
    parser.add_argument("--package-name", required=True, help="Expected Android package name")
    return parser.parse_args()


def validate_assetlinks(path: Path, expected_package: str) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"File not found: {path}"]

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"Invalid JSON: {exc}"]

    if not isinstance(payload, list) or not payload:
        return ["Top-level JSON must be a non-empty list"]

    for index, entry in enumerate(payload):
        if not isinstance(entry, dict):
            errors.append(f"Entry[{index}] must be an object")
            continue

        relation = entry.get("relation")
        if not isinstance(relation, list) or not relation:
            errors.append(f"Entry[{index}].relation must be a non-empty list")

        target = entry.get("target")
        if not isinstance(target, dict):
            errors.append(f"Entry[{index}].target must be an object")
            continue

        namespace = target.get("namespace")
        if namespace != "android_app":
            errors.append(f"Entry[{index}].target.namespace must be 'android_app'")

        package_name = target.get("package_name")
        if package_name != expected_package:
            errors.append(
                f"Entry[{index}].target.package_name mismatch: expected {expected_package}, got {package_name}"
            )

        fingerprints = target.get("sha256_cert_fingerprints")
        if not isinstance(fingerprints, list) or not fingerprints:
            errors.append(f"Entry[{index}].target.sha256_cert_fingerprints must be a non-empty list")
            continue

        for fp_idx, fingerprint in enumerate(fingerprints):
            if not isinstance(fingerprint, str):
                errors.append(f"Entry[{index}] fingerprint[{fp_idx}] must be a string")
                continue
            normalized = fingerprint.strip().upper()
            if not FINGERPRINT_PATTERN.fullmatch(normalized):
                errors.append(
                    f"Entry[{index}] fingerprint[{fp_idx}] is invalid; expected colon-delimited SHA-256 bytes"
                )

    return errors


def main() -> int:
    args = parse_args()
    errors = validate_assetlinks(Path(args.assetlinks_path).expanduser().resolve(), args.package_name)
    if errors:
        print("FAIL: assetlinks validation failed", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("PASS: assetlinks validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
