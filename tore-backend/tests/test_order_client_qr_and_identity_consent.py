from fastapi.testclient import TestClient

import secrets

from db import Base, engine, get_session
from main import app
from models import AppUserPrivacySetting, Bar, BarPrivacySetting, MenuCategory, MenuItem, Order, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_partner(role: str = "manager"):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"QR {suffix}", city="Paris", partner_code=f"QC{suffix}")
        s.add(bar)
        s.flush()
        user = PartnerUser(display_name="Staff", pin_hash="hash")
        s.add(user)
        s.flush()
        s.add(PartnerMembership(user_id=user.id, bar_id=bar.id, role=role, display_name="Staff"))
        cat = MenuCategory(bar_id=bar.id, name="Soft", sort_order=1)
        s.add(cat)
        s.flush()
        item = MenuItem(bar_id=bar.id, category_id=cat.id, name="Cola", price_cents=500)
        s.add(item)
        s.commit()
        return bar.id, user.id, item.id, _make_token(user.id, bar.id, role, "Staff")
    finally:
        s.close()


def test_order_client_qr_scan_is_idempotent_and_updates_status():
    bar_id, _, item_id, staff_token = _seed_partner(role="bartender")
    client = TestClient(app)

    guest = client.post('/auth/guest', json={'display_name': 'Alice'})
    assert guest.status_code == 200
    user_token = guest.json()['token']
    user_id = guest.json()['user']['id']

    order = client.post('/orders', json={
        'bar_id': bar_id,
        'user_id': user_id,
        'device_id': 'dev-1',
        'items': [{'item_id': item_id, 'qty': 1}],
        'idempotency_key': 'order-client-1',
    })
    assert order.status_code == 200

    issued = client.post(
        f"/orders/{order.json()['id']}/client-qr",
        headers={'Authorization': f'Bearer {user_token}'},
    )
    assert issued.status_code == 200
    assert issued.json()['qr_raw'].startswith('tore://order?ot=')

    first_scan = client.post(
        '/partner/portal/orders/scan-client-qr',
        json={'raw': issued.json()['qr_raw'], 'idempotency_key': 'scan-1'},
        headers={'Authorization': f'Bearer {staff_token}'},
    )
    assert first_scan.status_code == 200
    assert first_scan.json()['idempotent'] is False
    assert first_scan.json()['order']['status'] == 'IN_PROGRESS'

    second_scan = client.post(
        '/partner/portal/orders/scan-client-qr',
        json={'raw': issued.json()['qr_raw'], 'idempotency_key': 'scan-1'},
        headers={'Authorization': f'Bearer {staff_token}'},
    )
    assert second_scan.status_code == 200
    assert second_scan.json()['idempotent'] is True
    assert second_scan.json()['order']['id'] == order.json()['id']


def test_identity_consent_requires_bar_and_user_toggle():
    bar_id, _, item_id, staff_token = _seed_partner(role="manager")
    client = TestClient(app)

    guest = client.post('/auth/guest', json={'display_name': 'Bob'})
    user_token = guest.json()['token']
    user_id = guest.json()['user']['id']

    order = client.post('/orders', json={
        'bar_id': bar_id,
        'user_id': user_id,
        'device_id': 'dev-2',
        'items': [{'item_id': item_id, 'qty': 1}],
        'idempotency_key': 'order-client-2',
    })
    issued = client.post(
        f"/orders/{order.json()['id']}/client-qr",
        headers={'Authorization': f'Bearer {user_token}'},
    )

    no_consent = client.post(
        '/partner/portal/orders/scan-client-qr',
        json={'raw': issued.json()['qr_raw'], 'idempotency_key': 'scan-consent-1'},
        headers={'Authorization': f'Bearer {staff_token}'},
    )
    assert no_consent.status_code == 200
    assert no_consent.json()['user_visible_to_staff'] is False

    patch_bar = client.patch(
        '/partner/portal/settings/identity-consent',
        json={'staff_identity_consent_required': True},
        headers={'Authorization': f'Bearer {staff_token}'},
    )
    assert patch_bar.status_code == 200

    patch_me = client.patch(
        '/auth/me',
        json={'show_identity_to_staff': True},
        headers={'Authorization': f'Bearer {user_token}'},
    )
    assert patch_me.status_code == 200
    assert patch_me.json()['show_identity_to_staff'] is True

    issued2 = client.post(
        f"/orders/{order.json()['id']}/client-qr",
        headers={'Authorization': f'Bearer {user_token}'},
    )
    with_consent = client.post(
        '/partner/portal/orders/scan-client-qr',
        json={'raw': issued2.json()['qr_raw'], 'idempotency_key': 'scan-consent-2'},
        headers={'Authorization': f'Bearer {staff_token}'},
    )
    assert with_consent.status_code == 200
    assert with_consent.json()['user_visible_to_staff'] is True

    s = get_session()
    try:
        bar = s.query(BarPrivacySetting).filter(BarPrivacySetting.bar_id == bar_id).first()
        user = s.query(AppUserPrivacySetting).filter(AppUserPrivacySetting.user_id == user_id).first()
        refreshed_order = s.get(Order, order.json()['id'])
        assert bar is not None and bar.staff_identity_consent_required is True
        assert user is not None and user.show_identity_to_staff is True
        assert refreshed_order is not None and refreshed_order.status == 'IN_PROGRESS'
    finally:
        s.close()
