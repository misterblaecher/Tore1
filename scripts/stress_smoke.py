#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


def spam_qr(base_url: str, token: str, raw: str, rps: int, seconds: int) -> None:
    total = rps * seconds
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{base_url}/qr/resolve"
    start = time.time()
    hits_429 = 0
    for i in range(total):
        res = requests.post(url, headers=headers, json={"raw": raw}, timeout=5)
        if res.status_code == 429:
            hits_429 += 1
        delay = (start + (i + 1) / rps) - time.time()
        if delay > 0:
            time.sleep(delay)
    print(json.dumps({"phase": "qr", "total": total, "rate_limited": hits_429}, ensure_ascii=False))


def spam_orders_same_idem(base_url: str, body: dict, n: int = 20) -> None:
    url = f"{base_url}/orders"
    ids = set()
    with ThreadPoolExecutor(max_workers=10) as exe:
        futs = [exe.submit(requests.post, url, json=body, timeout=5) for _ in range(n)]
        for fut in as_completed(futs):
            res = fut.result()
            if res.status_code == 200:
                ids.add(res.json().get("id"))
    print(json.dumps({"phase": "orders_idempotency", "calls": n, "unique_order_ids": len(ids)}, ensure_ascii=False))


def spam_entry_same_scan(base_url: str, partner_token: str, event_id: int, entry_token: str, scan_id: str, n: int = 10) -> None:
    url = f"{base_url}/entry/scan"
    headers = {"Authorization": f"Bearer {partner_token}"}
    statuses = []
    for _ in range(n):
        res = requests.post(url, headers=headers, json={"event_id": event_id, "token": entry_token, "scan_id": scan_id}, timeout=5)
        statuses.append((res.status_code, res.json().get("status"), res.json().get("reason")))
    print(json.dumps({"phase": "entry_duplicate", "statuses": statuses[-3:]}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="TORÈ stress smoke")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--app-token", required=True, help="Bearer token for /qr/resolve app user")
    parser.add_argument("--partner-token", required=True, help="Bearer token for staff /entry/scan")
    parser.add_argument("--event-id", required=True, type=int)
    parser.add_argument("--bar-id", required=True, type=int)
    parser.add_argument("--item-id", required=True, type=int)
    parser.add_argument("--entry-token", required=True)
    args = parser.parse_args()

    idem = f"stress-{uuid.uuid4().hex[:12]}"
    order_body = {
        "bar_id": args.bar_id,
        "event_id": args.event_id,
        "items": [{"item_id": args.item_id, "qty": 1}],
        "device_id": "stress-device",
        "idempotency_key": idem,
    }

    spam_qr(args.base_url, args.app_token, f"tore://menu?event_id={args.event_id}&bar_id={args.bar_id}", rps=50, seconds=5)
    spam_orders_same_idem(args.base_url, order_body, n=20)
    spam_entry_same_scan(args.base_url, args.partner_token, args.event_id, args.entry_token, scan_id=f"scan-{uuid.uuid4().hex[:8]}", n=10)


if __name__ == "__main__":
    main()
