from fastapi.testclient import TestClient

import secrets

from db import Base, engine, get_session
from main import app
from models import (
    AppUserPrivacySetting,
    AuditLog,
    Bar,
    BarPrivacySetting,
    Event,
    EventModuleConfig,
    EventStaff,
    MenuCategory,
    MenuItem,
    PartnerMembership,
    PartnerUser,
)
from partner_auth import _make_token


def _seed_partner_and_event(role: str = "manager"):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"Smoke {suffix}", city="Paris", partner_code=f"SM{suffix}")
        s.add(bar)
        s.flush()
        partner = PartnerUser(display_name="Staff", pin_hash="hash")
        s.add(partner)
        s.flush()
        s.add(PartnerMembership(user_id=partner.id, bar_id=bar.id, role=role, display_name="Staff"))

        event = Event(bar_id=bar.id, name="Soiree")
        s.add(event)
        s.flush()
        s.add(
            EventModuleConfig(
                event_id=event.id,
                orders_enabled=True,
                entry_enabled=True,
                wifi_enabled=True,
                checkins_enabled=True,
                safety_enabled=True,
            )
        )
        cat = MenuCategory(bar_id=bar.id, name="Soft", sort_order=1)
        s.add(cat)
        s.flush()
        item = MenuItem(bar_id=bar.id, category_id=cat.id, name="Cola", price_cents=450)
        s.add(item)
        s.commit()
        return bar.id, event.id, item.id, _make_token(partner.id, bar.id, role, "Staff")
    finally:
        s.close()


def test_auth_me_patch_privacy_and_audit_contract():
    client = TestClient(app)
    bar_id, _, _, _ = _seed_partner_and_event()

    guest = client.post('/auth/guest', json={'display_name': 'Alice'})
    token = guest.json()['token']

    patched = client.patch(
        '/auth/me',
        headers={'Authorization': f'Bearer {token}'},
        json={'show_identity_to_staff': True},
    )
    assert patched.status_code == 200
    assert patched.json()['show_identity_to_staff'] is True

    s = get_session()
    try:
        setting = s.query(AppUserPrivacySetting).filter(AppUserPrivacySetting.user_id == patched.json()['id']).first()
        assert setting is not None and setting.show_identity_to_staff is True
        audit = s.query(AuditLog).filter(AuditLog.action == 'user.privacy.update', AuditLog.entity_id == patched.json()['id']).first()
        assert audit is not None

        bar_setting = BarPrivacySetting(bar_id=bar_id, staff_identity_consent_required=True)
        s.add(bar_setting)
        s.commit()
    finally:
        s.close()

    me = client.get(f'/auth/me?bar_id={bar_id}', headers={'Authorization': f'Bearer {token}'})
    assert me.status_code == 200
    assert me.json()['show_identity_to_staff'] is True
    assert me.json()['bar_show_identity_to_staff'] is True


def test_mode_c_flow_smoke_with_entry_and_exports():
    bar_id, event_id, item_id, partner_token = _seed_partner_and_event(role='manager')
    client = TestClient(app)

    guest = client.post('/auth/guest', json={'display_name': 'Bob'})
    assert guest.status_code == 200
    user_token = guest.json()['token']
    user_id = guest.json()['user']['id']

    s = get_session()
    try:
        s.add(EventStaff(event_id=event_id, user_id=user_id, role='admin', is_active=True))
        s.commit()
    finally:
        s.close()

    order = client.post('/orders', json={
        'bar_id': bar_id,
        'event_id': event_id,
        'user_id': user_id,
        'device_id': 'dev-smoke',
        'items': [{'item_id': item_id, 'qty': 1}],
        'idempotency_key': 'mode-c-smoke-order',
    })
    assert order.status_code == 200

    issued = client.post(
        f"/orders/{order.json()['id']}/client-qr",
        headers={'Authorization': f'Bearer {user_token}'},
    )
    assert issued.status_code == 200

    # With both toggles off => identity hidden
    scan1 = client.post(
        '/partner/portal/orders/scan-client-qr',
        headers={'Authorization': f'Bearer {partner_token}'},
        json={'raw': issued.json()['qr_raw'], 'idempotency_key': 'mode-c-scan-1'},
    )
    assert scan1.status_code == 200
    assert scan1.json()['idempotent'] is False
    assert scan1.json()['identity_visible'] is False

    # Duplicate idempotent scan
    scan_dup = client.post(
        '/partner/portal/orders/scan-client-qr',
        headers={'Authorization': f'Bearer {partner_token}'},
        json={'raw': issued.json()['qr_raw'], 'idempotency_key': 'mode-c-scan-1'},
    )
    assert scan_dup.status_code == 200
    assert scan_dup.json()['idempotent'] is True

    # Flip both toggles => identity visible
    bar_toggle = client.patch(
        '/partner/portal/settings/identity-consent',
        headers={'Authorization': f'Bearer {partner_token}'},
        json={'staff_identity_consent_required': True},
    )
    assert bar_toggle.status_code == 200
    me_patch = client.patch(
        '/auth/me',
        headers={'Authorization': f'Bearer {user_token}'},
        json={'show_identity_to_staff': True},
    )
    assert me_patch.status_code == 200

    issued2 = client.post(
        f"/orders/{order.json()['id']}/client-qr",
        headers={'Authorization': f'Bearer {user_token}'},
    )
    scan2 = client.post(
        '/partner/portal/orders/scan-client-qr',
        headers={'Authorization': f'Bearer {partner_token}'},
        json={'raw': issued2.json()['qr_raw'], 'idempotency_key': 'mode-c-scan-2'},
    )
    assert scan2.status_code == 200
    assert scan2.json()['identity_visible'] is True

    # Entry duplicate smoke
    issued_entry = client.post(
        '/entry/tokens/issue',
        headers={'Authorization': f'Bearer {partner_token}'},
        json={'event_id': event_id, 'count': 1},
    )
    assert issued_entry.status_code == 200
    token = issued_entry.json()['issued'][0]['token']
    first = client.post(
        '/entry/scan',
        headers={'Authorization': f'Bearer {partner_token}'},
        json={'event_id': event_id, 'token': token, 'scan_id': 'entry-smoke-1'},
    )
    assert first.status_code == 200
    second = client.post(
        '/entry/scan',
        headers={'Authorization': f'Bearer {partner_token}'},
        json={'event_id': event_id, 'token': token, 'scan_id': 'entry-smoke-1'},
    )
    assert second.status_code == 200
    assert second.json()['idempotent'] is True

    # Exports smoke (app user admin on event)
    attendance = client.get(f'/events/{event_id}/exports/attendance.csv', headers={'Authorization': f'Bearer {user_token}'})
    report = client.get(f'/events/{event_id}/exports/report.pdf', headers={'Authorization': f'Bearer {user_token}'})
    assert attendance.status_code == 200
    assert report.status_code == 200
    assert attendance.headers['content-type'].startswith('text/csv')
    assert report.headers['content-type'].startswith('application/pdf')
