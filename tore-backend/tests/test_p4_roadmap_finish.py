import secrets
from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import AppUser, Bar, Event, EventModuleConfig, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_manager():
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"P4 {suffix}", city="City", partner_code=f"P4{suffix}")
        s.add(bar)
        s.flush()
        manager = PartnerUser(display_name="Manager", pin_hash="hash")
        s.add(manager)
        s.flush()
        s.add(PartnerMembership(user_id=manager.id, bar_id=bar.id, role="manager", display_name="Manager"))
        event = Event(bar_id=bar.id, name="P4 Event", starts_at=now_utc() - timedelta(hours=1), ends_at=now_utc() + timedelta(hours=6))
        s.add(event)
        s.flush()
        s.add(EventModuleConfig(event_id=event.id, entry_enabled=True, battles_enabled=True, checkins_enabled=True, wifi_enabled=True, safety_enabled=True, polymarket_enabled=True))
        user = AppUser(id=f"u-{suffix}", display_name="User")
        buddy = AppUser(id=f"buddy-{suffix}", display_name="Buddy")
        s.add(user)
        s.add(buddy)
        s.commit()
        return bar.id, event.id, user.id, buddy.id, _make_token(manager.id, bar.id, "manager", "Manager")
    finally:
        s.close()


def test_wifi_safety_battles_pagination_and_e2e_smoke():
    bar_id, event_id, user_id, buddy_id, manager_token = _seed_manager()
    client = TestClient(app)

    guest = client.post('/auth/guest', json={'display_name': 'p4-user'})
    guest_token = guest.json()['token']

    # wifi gated by module/live
    set_wifi = client.post('/partner/portal/wifi/set', json={'bar_id': bar_id, 'event_id': event_id, 'ssid': 'P4NET', 'password': 'secret'}, headers={'Authorization': f'Bearer {manager_token}'})
    assert set_wifi.status_code == 200
    pub = client.get(f'/public/wifi?bar_id={bar_id}&event_id={event_id}')
    assert pub.status_code == 200 and pub.json()['ssid'] == 'P4NET'

    s = get_session()
    try:
        cfg = s.query(EventModuleConfig).filter(EventModuleConfig.event_id == event_id).first()
        cfg.wifi_enabled = False
        s.add(cfg)
        s.commit()
    finally:
        s.close()
    assert client.get(f'/public/wifi?bar_id={bar_id}&event_id={event_id}').status_code == 204

    # safety lifecycle + ownership stats
    s = get_session()
    try:
        user = s.get(AppUser, user_id)
        if not user:
            s.add(AppUser(id=user_id, display_name='Seeded user'))
            s.commit()
    finally:
        s.close()
    app_user = client.post('/auth/guest', json={'display_name': 'safety-u'})
    app_token = app_user.json()['token']
    start = client.post('/safety/buddy/start', json={'buddy_user_id': buddy_id, 'expires_minutes': 10, 'event_id': event_id}, headers={'Authorization': f'Bearer {app_token}'})
    assert start.status_code == 200
    sid = start.json()['session_id']
    assert client.post('/safety/buddy/ping', json={'session_id': sid}, headers={'Authorization': f'Bearer {app_token}'}).status_code == 200
    assert client.post('/safety/buddy/end', json={'session_id': sid}, headers={'Authorization': f'Bearer {app_token}'}).status_code == 200
    stats = client.get(f'/partner/portal/safety/event/{event_id}/stats', headers={'Authorization': f'Bearer {manager_token}'})
    assert stats.status_code == 200
    assert 'recent_sessions' in stats.json()

    # entry issue + scan
    issue = client.post('/entry/tokens/issue', json={'event_id': event_id, 'count': 1, 'user_id': user_id}, headers={'Authorization': f'Bearer {manager_token}'})
    token = issue.json()['issued'][0]['token']
    scan = client.post('/entry/scan', json={'event_id': event_id, 'token': token, 'scan_id': f'scan-{secrets.token_hex(2)}'}, headers={'Authorization': f'Bearer {manager_token}'})
    assert scan.status_code == 200

    # wallet logs pagination
    for idx in range(3):
        top = client.post('/partner/portal/wallet/admin/topup', json={'event_id': event_id, 'user_id': user_id, 'amount_tickets': 5 + idx, 'reason': f'p4-{idx}', 'idempotency_key': f'p4-top-{idx}-{secrets.token_hex(2)}'}, headers={'Authorization': f'Bearer {manager_token}'})
        assert top.status_code == 200
    w1 = client.get(f'/partner/portal/wallet/admin/logs?event_id={event_id}&limit=2', headers={'Authorization': f'Bearer {manager_token}'})
    w2 = client.get(f"/partner/portal/wallet/admin/logs?event_id={event_id}&limit=2&cursor={w1.json()['next_cursor']}", headers={'Authorization': f'Bearer {manager_token}'})
    assert {x['id'] for x in w1.json()['items']}.isdisjoint({x['id'] for x in w2.json()['items']})

    # battles create/join/submit/validate
    battle = client.post('/battles/create', json={'event_id': event_id, 'mode': 'ffa'}, headers={'Authorization': f'Bearer {manager_token}'})
    assert battle.status_code == 200
    battle_id = battle.json()['id']
    assert client.post(f'/battles/{battle_id}/join', json={}, headers={'Authorization': f'Bearer {guest_token}'}).status_code == 200
    submit = client.post(f'/battles/{battle_id}/submit', json={'scan_id': f'sub-{secrets.token_hex(2)}', 'points': 2}, headers={'Authorization': f'Bearer {guest_token}'})
    assert submit.status_code == 200
    validate = client.post(f"/battles/{battle_id}/validate", json={'submit_id': submit.json()['submit_id']}, headers={'Authorization': f'Bearer {manager_token}'})
    assert validate.status_code == 200

    # checkins + paginated partner logs
    for i in range(3):
        ck = client.post('/drinks/checkin', json={'free_text_name': f'Drink-{i}', 'event_id': event_id}, headers={'Authorization': f'Bearer {guest_token}'})
        assert ck.status_code == 200
    c1 = client.get(f'/partner/portal/checkins/logs?event_id={event_id}&limit=2', headers={'Authorization': f'Bearer {manager_token}'})
    c2 = client.get(f"/partner/portal/checkins/logs?event_id={event_id}&limit=2&cursor={c1.json()['next_cursor']}", headers={'Authorization': f'Bearer {manager_token}'})
    assert {x['id'] for x in c1.json()['items']}.isdisjoint({x['id'] for x in c2.json()['items']})

    # audit pagination
    a1 = client.get(f'/partner/portal/audit/logs?event_id={event_id}&limit=2', headers={'Authorization': f'Bearer {manager_token}'})
    assert a1.status_code == 200
    if a1.json()['next_cursor']:
        a2 = client.get(f"/partner/portal/audit/logs?event_id={event_id}&limit=2&cursor={a1.json()['next_cursor']}", headers={'Authorization': f'Bearer {manager_token}'})
        assert a2.status_code == 200
        assert {x['id'] for x in a1.json()['items']}.isdisjoint({x['id'] for x in a2.json()['items']})