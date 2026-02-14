import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import AppUser, Bar, Event, EventAuditLog, EventConfig, EventStaff


def _seed_admin_event_with_user() -> tuple[str, int]:
    Base.metadata.create_all(engine)
    client = TestClient(app)
    guest = client.post('/auth/guest', json={'display_name': 'export-admin'})
    token = guest.json()['token']
    user_id = guest.json()['user']['id']

    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"Export Bar {suffix}", city="Liege", partner_code=f"EXP{suffix}")
        s.add(bar)
        s.flush()
        event = Event(bar_id=bar.id, name="Export Event")
        s.add(event)
        s.flush()
        s.add(EventConfig(event_id=event.id, report_enabled=True))
        s.add(EventStaff(event_id=event.id, user_id=user_id, role='admin', is_active=True))
        # attendance sample
        s.add(
            EventAuditLog(
                event_id=event.id,
                actor_user_id=user_id,
                action='entry.scan',
                payload_json='{"status":"accepted"}',
            )
        )
        s.commit()
        return token, event.id
    finally:
        s.close()


def test_exports_and_costs_and_audit_actions():
    token, event_id = _seed_admin_event_with_user()
    client = TestClient(app)

    add_cost = client.post(
        f"/events/{event_id}/costs",
        json={"label": "Security", "amount_cents": 15000, "category": "staff"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert add_cost.status_code == 200

    list_cost = client.get(f"/events/{event_id}/costs", headers={"Authorization": f"Bearer {token}"})
    assert list_cost.status_code == 200
    assert len(list_cost.json()) >= 1

    attendance = client.get(
        f"/events/{event_id}/exports/attendance.csv",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert attendance.status_code == 200
    assert attendance.headers['content-type'].startswith('text/csv')
    assert 'timestamp,ticket_id,status,reason,staff_id,scan_id' in attendance.text

    report = client.get(
        f"/events/{event_id}/exports/report.pdf",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert report.status_code == 200
    assert report.headers['content-type'].startswith('application/pdf')
    assert len(report.content) > 50

    costs_csv = client.get(
        f"/events/{event_id}/costs/export.csv",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert costs_csv.status_code == 200
    assert costs_csv.headers['content-type'].startswith('text/csv')
    assert 'timestamp,label,category,amount_cents' in costs_csv.text

    s = get_session()
    try:
        actions = {row.action for row in s.query(EventAuditLog).filter(EventAuditLog.event_id == event_id).all()}
        assert 'exports.attendance_download' in actions
        assert 'exports.report_generate' in actions
    finally:
        s.close()
