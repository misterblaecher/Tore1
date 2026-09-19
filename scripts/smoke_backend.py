#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


class SmokeRunner:
    def __init__(self, base_url: str, admin_token: str | None) -> None:
        self.base_url = base_url.rstrip("/")
        self.admin_token = admin_token
        self.results: list[CheckResult] = []

    def record(self, name: str, ok: bool, detail: str) -> None:
        self.results.append(CheckResult(name=name, ok=ok, detail=detail))

    def _request(self, path: str, *, method: str = "GET", token: str | None = None, body: dict[str, Any] | None = None) -> tuple[int, Any]:
        data = None
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(f"{self.base_url}{path}", method=method, headers=headers, data=data)
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                raw = resp.read().decode("utf-8")
                parsed: Any
                try:
                    parsed = json.loads(raw)
                except Exception:
                    parsed = raw
                return resp.status, parsed
        except urllib.error.HTTPError as err:
            payload = err.read().decode("utf-8") if err.fp else ""
            try:
                parsed = json.loads(payload)
            except Exception:
                parsed = payload
            return err.code, parsed
        except urllib.error.URLError as err:
            return 0, {"error": str(err)}

    def _check_qr_signing_keys_env(self) -> None:
        ring = (os.getenv("TORE_QR_SIGNING_KEYS") or "").strip()
        if not ring:
            self.record(
                "env:TORE_QR_SIGNING_KEYS",
                True,
                "not set (dev fallback to TORE_QR_SIGNING_SECRET/TORE_JWT_SECRET)",
            )
            return

        values = [item.strip() for item in ring.split(",") if item.strip()]
        if not values:
            self.record("env:TORE_QR_SIGNING_KEYS", False, "empty ring after parsing")
            return

        invalid: list[str] = []
        for idx, value in enumerate(values, start=1):
            if len(value) < 16:
                invalid.append(f"#{idx}:too-short")
            elif not re.fullmatch(r"[A-Za-z0-9_\-:.]{16,}", value):
                invalid.append(f"#{idx}:invalid-chars")

        if invalid:
            self.record(
                "env:TORE_QR_SIGNING_KEYS",
                False,
                f"invalid key format ({', '.join(invalid)})",
            )
        else:
            self.record("env:TORE_QR_SIGNING_KEYS", True, f"{len(values)} key(s) parsed")

    def _check_health(self) -> None:
        status, payload = self._request("/healthz")
        if status == 200 and isinstance(payload, dict) and payload.get("ok") is True:
            self.record("GET /healthz", True, "ok=true")
            return

        status2, payload2 = self._request("/health")
        ok = status2 == 200
        self.record("GET /healthz|/health", ok, f"healthz={status}, health={status2}, payload={payload2}")

    def _check_modules(self) -> None:
        status, payload = self._request("/modules")
        ok = status == 200 and isinstance(payload, dict)
        if ok:
            required = {"committee_os", "folklore_glossary"}
            missing = sorted(required - set(payload.keys()))
            ok = not missing
            self.record("GET /modules", ok, f"keys={sorted(payload.keys())}, missing={missing}")
            return
        self.record("GET /modules", False, f"status={status}, payload={payload}")

    def _check_public_read_endpoints(self) -> None:
        for path in ("/bars", "/calendar/events"):
            status, payload = self._request(path)
            ok = status == 200
            kind = type(payload).__name__
            self.record(f"GET {path}", ok, f"status={status}, payload_type={kind}")

    def _check_admin_flags(self) -> None:
        if not self.admin_token:
            self.record("GET /admin/flags", True, "skipped (TORE_ADMIN_TOKEN absent)")
            return
        status, payload = self._request("/admin/flags", token=self.admin_token)
        ok = status == 200
        self.record("GET /admin/flags", ok, f"status={status}, payload_type={type(payload).__name__}")

    def _check_cors(self) -> None:
        origins = (os.getenv("TORE_CORS_ORIGINS") or "").strip()
        app_env = (os.getenv("TORE_ENV") or os.getenv("APP_ENV") or os.getenv("ENV") or "").strip().lower()

        if app_env in {"prod", "production"}:
            ok = bool(origins) and origins != "*"
            detail = "prod requires explicit non-* TORE_CORS_ORIGINS"
        else:
            ok = True if not origins else True
            detail = "dev default accepted" if not origins else f"custom={origins}"
        self.record("env:TORE_CORS_ORIGINS", ok, detail)

    def run(self) -> int:
        self._check_qr_signing_keys_env()
        self._check_cors()
        self._check_health()
        self._check_modules()
        self._check_public_read_endpoints()
        self._check_admin_flags()

        failures = [r for r in self.results if not r.ok]
        for item in self.results:
            prefix = "PASS" if item.ok else "FAIL"
            print(f"[{prefix}] {item.name}: {item.detail}")

        print(f"\nSummary: {len(self.results) - len(failures)} passed / {len(failures)} failed")
        return 1 if failures else 0


def main() -> int:
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    admin_token = os.getenv("TORE_ADMIN_TOKEN")
    runner = SmokeRunner(base_url=base_url, admin_token=admin_token)
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
