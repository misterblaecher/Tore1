import io
import secrets
import zipfile

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import Bar, Event, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_manager_bar_event():
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f'Zone Bar {suffix}', city='Liege', partner_code=f'ZONE{suffix}')
        s.add(bar)
        s.flush()
        manager = PartnerUser(display_name='Manager', pin_hash='hash')
        bartender = PartnerUser(display_name='Bartender', pin_hash='hash')
        s.add(manager)
        s.add(bartender)
        s.flush()
        s.add(PartnerMembership(user_id=manager.id, bar_id=bar.id, role='manager', display_name='Manager'))
        s.add(PartnerMembership(user_id=bartender.id, bar_id=bar.id, role='bartender', display_name='Bartender'))
        event = Event(bar_id=bar.id, name='Zone Event')
        s.add(event)
        s.commit()
        return {
            'bar_id': bar.id,
            'event_id': event.id,
            'manager_token': _make_token(manager.id, bar.id, 'manager', 'Manager'),
            'bartender_token': _make_token(bartender.id, bar.id, 'bartender', 'Bartender'),
        }
    finally:
        s.close()


def test_zones_crud_bulk_and_export_pack_zip():
    seed = _seed_manager_bar_event()
    client = TestClient(app)

    created_ids = []
    for idx in range(3):
        res = client.post(
            f"/bars/{seed['bar_id']}/zones",
            json={'name': f'Table {idx + 1}', 'event_id': seed['event_id']},
            headers={'Authorization': f"Bearer {seed['bartender_token']}"},
        )
        assert res.status_code == 200
        data = res.json()
        created_ids.append(data['id'])
        assert data['qr_payload'].startswith(f"tore://menu?bar_id={seed['bar_id']}&zone_id=")

    page = client.get(
        f"/bars/{seed['bar_id']}/zones?limit=2",
        headers={'Authorization': f"Bearer {seed['manager_token']}"},
    )
    assert page.status_code == 200
    assert len(page.json()['items']) == 2

    patch = client.patch(
        f"/zones/{created_ids[0]}",
        json={'name': 'Table VIP', 'enabled': False},
        headers={'Authorization': f"Bearer {seed['manager_token']}"},
    )
    assert patch.status_code == 200
    assert patch.json()['name'] == 'Table VIP'
    assert patch.json()['enabled'] is False

    bulk = client.post(
        f"/bars/{seed['bar_id']}/zones/bulk",
        json={'zone_ids': created_ids, 'action': 'disable'},
        headers={'Authorization': f"Bearer {seed['manager_token']}"},
    )
    assert bulk.status_code == 200
    assert bulk.json()['updated'] == 3

    export = client.post(
        f"/bars/{seed['bar_id']}/zones/export_pack?format=zip",
        headers={'Authorization': f"Bearer {seed['manager_token']}"},
    )
    assert export.status_code == 200
    assert export.headers['content-type'].startswith('application/zip')
    assert len(export.content) > 100

    zf = zipfile.ZipFile(io.BytesIO(export.content))
    names = zf.namelist()
    assert any(name.startswith('stickers/') and name.endswith('.svg') for name in names)
    assert 'manifest.json' in names


def test_qr_resolve_menu_zone_id_contract():
    client = TestClient(app)
    guest = client.post('/auth/guest', json={'display_name': 'qr-zone'})
    token = guest.json()['token']

    res = client.post(
        '/qr/resolve',
        json={'raw': 'tore://menu?bar_id=42&zone_id=9'},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload['valid'] is True
    assert payload['type'] == 'menu'
    assert payload['bar_id'] == 42
    assert payload['zone_id'] == 9
