#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class Step:
    name: str
    ok: bool
    detail: str


class SmokeRelease:
    def __init__(self) -> None:
        self.backend_url = (os.getenv("BACKEND_URL") or "").strip().rstrip("/")
        self.public_url = (os.getenv("PUBLIC_URL") or "").strip().rstrip("/")
        self.admin_token = (os.getenv("ADMIN_TOKEN") or "").strip()
        self.user_token = (os.getenv("USER_TOKEN") or "").strip()
        self.steps: list[Step] = []

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.steps.append(Step(name, ok, detail))

    def request(self, path: str, *, method: str = "GET", token: str | None = None, body: dict[str, Any] | None = None, follow_redirects: bool = True) -> tuple[int, Any, dict[str, str]]:
        if not self.backend_url:
            return 0, {"error": "BACKEND_URL missing"}, {}
        data = None
        headers: dict[str, str] = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")

        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, hdrs, newurl):
                return None

        opener = urllib.request.build_opener(_NoRedirect()) if not follow_redirects else urllib.request.build_opener()
        req = urllib.request.Request(f"{self.backend_url}{path}", method=method, data=data, headers=headers)

        try:
            with opener.open(req, timeout=12) as resp:
                raw = resp.read().decode("utf-8")
                try:
                    parsed: Any = json.loads(raw)
                except Exception:
                    parsed = raw
                return int(resp.status), parsed, {k.lower(): v for k, v in resp.headers.items()}
        except urllib.error.HTTPError as err:
            payload = err.read().decode("utf-8") if err.fp else ""
            try:
                parsed = json.loads(payload)
            except Exception:
                parsed = payload
            return int(err.code), parsed, {k.lower(): v for k, v in (err.headers.items() if err.headers else [])}
        except urllib.error.URLError as err:
            return 0, {"error": str(err)}, {}

    def run(self) -> int:
        if not self.backend_url:
            print("[FAIL] preflight: BACKEND_URL is required")
            return 1

        status, payload, _ = self.request("/healthz")
        if status == 200:
            self.add("GET /healthz", True, "ok")
        else:
            status2, payload2, _ = self.request("/health")
            ok = status2 == 200
            self.add("GET /healthz fallback /health", ok, f"healthz={status}, health={status2}, payload={payload2 or payload}")

        status, payload, _ = self.request("/modules")
        self.add("GET /modules", status == 200 and isinstance(payload, dict), f"status={status}")

        env_name = (os.getenv("ENV") or "").strip().upper()
        status, payload, _ = self.request("/debug/health-ui")
        if env_name == "DEV":
            self.add("GET /debug/health-ui (DEV)", status == 200, f"status={status}")
        else:
            self.add("GET /debug/health-ui (non-DEV expected skip)", status in {200, 404}, f"status={status}")

        invalid_code = urllib.parse.quote("@@INVALID-CODE", safe="")
        status, payload, _ = self.request(f"/codes/preview?code={invalid_code}")
        preview_ok = status == 200 and isinstance(payload, dict) and payload.get("status") == "invalid" and bool(payload.get("openUrl"))
        self.add("NO-QR GET /codes/preview invalid", preview_ok, f"status={status}, openUrl={payload.get('openUrl') if isinstance(payload, dict) else None}")

        if self.user_token:
            body = {"kind": "open_url", "open_type": "join", "open_code": "ABCDEF12"}
            status, payload, _ = self.request("/shortlinks", method="POST", token=self.user_token, body=body)
            short_ok = status == 200 and isinstance(payload, dict) and bool(payload.get("shortUrl")) and bool(payload.get("fallbackOpenUrl"))
            self.add("POST /shortlinks (idempotent path)", short_ok, f"status={status}")
            if short_ok:
                slug = str(payload.get("slug") or "")
                r_status, _, r_headers = self.request(f"/s/{slug}", follow_redirects=False)
                location = r_headers.get("location", "")
                redirect_ok = r_status in {301, 302, 307, 308} and "/open" in location
                if self.public_url:
                    redirect_ok = redirect_ok and location.startswith(self.public_url)
                self.add("GET /s/{slug} redirect", redirect_ok, f"status={r_status}, location={location}")
        else:
            self.add("POST /shortlinks", True, "skipped (USER_TOKEN absent)")

        if self.admin_token:
            status, payload, _ = self.request("/admin/flags", token=self.admin_token)
            self.add("GET /admin/flags", status == 200, f"status={status}")
        else:
            self.add("GET /admin/flags", True, "skipped (ADMIN_TOKEN absent)")

        failures = [s for s in self.steps if not s.ok]
        for item in self.steps:
            print(f"[{'PASS' if item.ok else 'FAIL'}] {item.name}: {item.detail}")
        print(f"\nSummary: {len(self.steps) - len(failures)} passed / {len(failures)} failed")
        return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(SmokeRelease().run())
