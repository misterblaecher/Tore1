import csv
import io
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import Bar, Event, EventModuleConfig, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_manager_with_entry_event():
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f'Entry Bar {suffix}', city='Liege', partner_code=f'ENT{suffix}')
        s.add(bar)
        s.flush()
        manager = PartnerUser(display_name='Manager', pin_hash='hash')
        s.add(manager)
        s.flush()
        s.add(PartnerMembership(user_id=manager.id, bar_id=bar.id, role='manager', display_name='Manager'))
        event = Event(bar_id=bar.id, name='Entry Event')
        s.add(event)
        s.flush()
        s.add(EventModuleConfig(event_id=event.id, entry_enabled=True))
        s.commit()
        return {
            'event_id': event.id,
            'manager_token': _make_token(manager.id, bar.id, 'manager', 'Manager'),
        }
    finally:
        s.close()


def test_entry_scan_duplicate_keeps_counter_stable_and_returns_duplicate():
    seed = _seed_manager_with_entry_event()
    client = TestClient(app)

    issue = client.post(
        '/entry/tokens/issue',
        json={'event_id': seed['event_id'], 'count': 1},
        headers={'Authorization': f"Bearer {seed['manager_token']}"},
    )
    assert issue.status_code == 200
    token = issue.json()['issued'][0]['token']

    first = client.post(
        '/entry/scan',
        json={'event_id': seed['event_id'], 'token': token, 'scan_id': 'scan-a'},
        headers={'Authorization': f"Bearer {seed['manager_token']}"},
    )
    assert first.status_code == 200
    assert first.json()['status'] == 'accepted'
    first_count = first.json()['entry_count']

    second = client.post(
        '/entry/scan',
        json={'event_id': seed['event_id'], 'token': token, 'scan_id': 'scan-b'},
        headers={'Authorization': f"Bearer {seed['manager_token']}"},
    )
    assert second.status_code == 200
    assert second.json()['status'] == 'duplicate'
    assert second.json()['entry_count'] == first_count


def test_entry_scan_paused_returns_denied_event_paused_and_csv_export_has_header():
    seed = _seed_manager_with_entry_event()
    client = TestClient(app)

    issue = client.post(
        '/entry/tokens/issue',
        json={'event_id': seed['event_id'], 'count': 1},
        headers={'Authorization': f"Bearer {seed['manager_token']}"},
    )
    token = issue.json()['issued'][0]['token']

    pause = client.post(
        f"/partner/portal/event/{seed['event_id']}/state",
        json={'state': 'PAUSE', 'reason': 'rush break'},
        headers={'Authorization': f"Bearer {seed['manager_token']}"},
    )
    assert pause.status_code == 200

    denied = client.post(
        '/entry/scan',
        json={'event_id': seed['event_id'], 'token': token, 'scan_id': 'scan-paused'},
        headers={'Authorization': f"Bearer {seed['manager_token']}"},
    )
    assert denied.status_code == 200
    assert denied.json()['status'] == 'denied'
    assert denied.json()['reason'] == 'event_paused'

    export = client.get(
        f"/entry/logs/export?event_id={seed['event_id']}",
        headers={'Authorization': f"Bearer {seed['manager_token']}"},
    )
    assert export.status_code == 200
    assert export.headers['content-type'].startswith('text/csv')
    assert len(export.content) > 40
    rows = list(csv.reader(io.StringIO(export.content.decode('utf-8'))))
    assert rows[0] == ['timestamp', 'ticket_id', 'status', 'reason', 'staff_id', 'scan_id']
    assert len(rows) >= 2
