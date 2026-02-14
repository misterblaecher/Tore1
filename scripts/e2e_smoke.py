#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import uuid

import requests


def main() -> None:
    p = argparse.ArgumentParser(description='TORÈ end-to-end smoke (Mode C + entry + exports)')
    p.add_argument('--base-url', required=True)
    p.add_argument('--user-token', required=True, help='App user bearer token (owner order + admin event for exports)')
    p.add_argument('--partner-token', required=True, help='Partner staff/manager token')
    p.add_argument('--bar-id', type=int, required=True)
    p.add_argument('--event-id', type=int, required=True)
    p.add_argument('--item-id', type=int, required=True)
    args = p.parse_args()

    base = args.base_url.rstrip('/')
    user_h = {'Authorization': f'Bearer {args.user_token}'}
    partner_h = {'Authorization': f'Bearer {args.partner_token}'}

    order_idem = f'e2e-order-{uuid.uuid4().hex[:8]}'
    order = requests.post(
        f'{base}/orders',
        json={
            'bar_id': args.bar_id,
            'event_id': args.event_id,
            'device_id': 'e2e-smoke-device',
            'items': [{'item_id': args.item_id, 'qty': 1}],
            'idempotency_key': order_idem,
        },
        timeout=8,
    )
    order.raise_for_status()
    order_id = order.json()['id']

    issue = requests.post(f'{base}/orders/{order_id}/client-qr', headers=user_h, timeout=8)
    issue.raise_for_status()
    qr_raw = issue.json()['qr_raw']

    scan_idem = f'e2e-scan-{uuid.uuid4().hex[:8]}'
    scan_1 = requests.post(
        f'{base}/partner/portal/orders/scan-client-qr',
        headers=partner_h,
        json={'raw': qr_raw, 'idempotency_key': scan_idem},
        timeout=8,
    )
    scan_1.raise_for_status()
    scan_2 = requests.post(
        f'{base}/partner/portal/orders/scan-client-qr',
        headers=partner_h,
        json={'raw': qr_raw, 'idempotency_key': scan_idem},
        timeout=8,
    )
    scan_2.raise_for_status()

    entry_issue = requests.post(
        f'{base}/entry/tokens/issue',
        headers=partner_h,
        json={'event_id': args.event_id, 'count': 1},
        timeout=8,
    )
    entry_issue.raise_for_status()
    entry_token = entry_issue.json()['issued'][0]['token']
    entry_scan_id = f'e2e-entry-{uuid.uuid4().hex[:8]}'
    entry_1 = requests.post(
        f'{base}/entry/scan',
        headers=partner_h,
        json={'event_id': args.event_id, 'token': entry_token, 'scan_id': entry_scan_id},
        timeout=8,
    )
    entry_1.raise_for_status()
    entry_2 = requests.post(
        f'{base}/entry/scan',
        headers=partner_h,
        json={'event_id': args.event_id, 'token': entry_token, 'scan_id': entry_scan_id},
        timeout=8,
    )
    entry_2.raise_for_status()

    attendance = requests.get(f'{base}/events/{args.event_id}/exports/attendance.csv', headers=user_h, timeout=8)
    report = requests.get(f'{base}/events/{args.event_id}/exports/report.pdf', headers=user_h, timeout=8)

    summary = {
        'order_id': order_id,
        'mode_c': {
            'first_idempotent': scan_1.json().get('idempotent'),
            'second_idempotent': scan_2.json().get('idempotent'),
            'identity_visible': scan_1.json().get('identity_visible'),
        },
        'entry': {
            'first_status': entry_1.json().get('status'),
            'second_idempotent': entry_2.json().get('idempotent'),
        },
        'exports': {
            'attendance_status': attendance.status_code,
            'report_status': report.status_code,
        },
    }

    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
