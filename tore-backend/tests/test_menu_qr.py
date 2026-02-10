from fastapi.testclient import TestClient

import secrets

from db import Base, engine, get_session
from main import app
from models import Bar, MenuItem, MenuTrackEvent, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_partner_user(role: str = "manager"):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"Menu Bar {suffix}", city="Test City", partner_code=f"MEN{suffix}")
        s.add(bar)
        s.flush()
        user = PartnerUser(display_name="Menu User", pin_hash="hash")
        s.add(user)
        s.flush()
        membership = PartnerMembership(user_id=user.id, bar_id=bar.id, role=role, display_name="Menu User")
        s.add(membership)
        s.commit()
        token = _make_token(user.id, bar.id, role, "Menu User")
        return bar.id, token
    finally:
        s.close()


def test_menu_category_item_permissions_and_public_structure():
    bar_id, token = _seed_partner_user(role="manager")
    _, staff_token = _seed_partner_user(role="bartender")
    client = TestClient(app)

    unauthorized = client.post('/partner/portal/menu/categories', json={'name': 'Cocktails'})
    assert unauthorized.status_code == 401

    forbidden = client.post('/partner/portal/menu/categories', json={'name': 'Cocktails'}, headers={'Authorization': f'Bearer {staff_token}'})
    assert forbidden.status_code == 403

    created_category = client.post(
        '/partner/portal/menu/categories',
        json={'name': 'Cocktails', 'sort_order': 1},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert created_category.status_code == 200
    category_id = created_category.json()['id']

    created_item = client.post(
        '/partner/portal/menu/items',
        json={'category_id': category_id, 'name': 'Spritz', 'description': 'Aperitivo', 'price_cents': 900},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert created_item.status_code == 200
    item_id = created_item.json()['id']

    menu_res = client.get(f'/menu/public/{bar_id}')
    assert menu_res.status_code == 200
    payload = menu_res.json()
    assert payload['bar']['id'] == bar_id
    assert payload['categories'][0]['id'] == category_id
    assert payload['categories'][0]['items'][0]['id'] == item_id


def test_menu_bar_mismatch_forbidden():
    bar_id, token = _seed_partner_user(role='manager')
    _, other_token = _seed_partner_user(role='manager')
    client = TestClient(app)

    created_category = client.post(
        '/partner/portal/menu/categories',
        json={'name': 'Food', 'sort_order': 1},
        headers={'Authorization': f'Bearer {token}'},
    )
    category_id = created_category.json()['id']

    patch_res = client.patch(
        f'/partner/portal/menu/categories/{category_id}',
        json={'name': 'Updated'},
        headers={'Authorization': f'Bearer {other_token}'},
    )
    assert patch_res.status_code == 403
    assert bar_id != 0


def test_menu_track_and_analytics():
    bar_id, token = _seed_partner_user(role='manager')
    client = TestClient(app)

    category = client.post(
        '/partner/portal/menu/categories',
        json={'name': 'Beer', 'sort_order': 1},
        headers={'Authorization': f'Bearer {token}'},
    ).json()
    item = client.post(
        '/partner/portal/menu/items',
        json={'category_id': category['id'], 'name': 'IPA', 'description': '', 'price_cents': 600},
        headers={'Authorization': f'Bearer {token}'},
    ).json()

    track = client.post('/menu/track', json={'bar_id': bar_id, 'item_id': item['id'], 'action': 'view', 'device_id': 'd1'})
    assert track.status_code == 200

    s = get_session()
    try:
        row = s.query(MenuTrackEvent).filter(MenuTrackEvent.id == track.json()['id']).first()
        assert row is not None
    finally:
        s.close()

    client.post('/menu/track', json={'bar_id': bar_id, 'item_id': item['id'], 'action': 'click'})
    analytics = client.get('/partner/portal/menu/analytics', headers={'Authorization': f'Bearer {token}'})
    assert analytics.status_code == 200
    data = analytics.json()
    assert data['period_days'] == 7
    assert len(data['top_items']) >= 1
    assert data['top_items'][0]['item_id'] == item['id']


def test_delete_category_cascades_items():
    _, token = _seed_partner_user(role='manager')
    client = TestClient(app)

    category = client.post(
        '/partner/portal/menu/categories',
        json={'name': 'Wine', 'sort_order': 1},
        headers={'Authorization': f'Bearer {token}'},
    ).json()
    item = client.post(
        '/partner/portal/menu/items',
        json={'category_id': category['id'], 'name': 'Red', 'description': '', 'price_cents': 700},
        headers={'Authorization': f'Bearer {token}'},
    ).json()

    deleted = client.delete(
        f"/partner/portal/menu/categories/{category['id']}",
        headers={'Authorization': f'Bearer {token}'},
    )
    assert deleted.status_code == 200
    assert deleted.json()['ok'] is True

    s = get_session()
    try:
        remaining_item = s.query(MenuItem).filter(MenuItem.id == item['id']).first()
        assert remaining_item is None
    finally:
        s.close()


def test_qr_resolve_menu_route_front():
    client = TestClient(app)
    guest = client.post('/auth/guest', json={'display_name': 'qr'})
    token = guest.json()['token']
    res = client.post('/qr/resolve', json={'raw': 'tore://menu?bar_id=42&item_id=7'}, headers={'Authorization': f'Bearer {token}'})
    assert res.status_code == 200
    payload = res.json()
    assert payload['type'] == 'menu'
    assert payload['bar_id'] == 42
    assert payload['item_id'] == 7
    assert payload['route_front'] == '/menu/42/item/7'
