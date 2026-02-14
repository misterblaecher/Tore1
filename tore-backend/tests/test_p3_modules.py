from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import Bar, Event, EventModuleConfig, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed(role: str = "manager"):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        bar = Bar(name="P3 Bar", city="Liege", partner_code=f"P3-{now_utc().timestamp()}")
        s.add(bar)
        s.flush()
        event = Event(bar_id=bar.id, name="P3 Event", starts_at=now_utc() - timedelta(hours=1), ends_at=now_utc() + timedelta(hours=2))
        s.add(event)
        s.flush()
        cfg = EventModuleConfig(event_id=event.id, battles_enabled=True, checkins_enabled=True, wifi_enabled=True, safety_enabled=True)
        s.add(cfg)
        user = PartnerUser(display_name="Mgr", pin_hash="hash")
        s.add(user)
        s.flush()
        s.add(PartnerMembership(user_id=user.id, bar_id=bar.id, role=role, display_name="Mgr"))
        s.commit()
        token = _make_token(user.id, bar.id, role, "Mgr")
        return bar.id, event.id, token
    finally:
        s.close()


def _guest(client: TestClient, name: str):
    res = client.post('/auth/guest', json={'display_name': name})
    assert res.status_code == 200
    return res.json()['token']


def test_p3_battle_create_guard_and_flow():
    bar_id, event_id, manager_token = _seed('manager')
    _, _, bartender_token = _seed('bartender')
    client = TestClient(app)

    forbidden = client.post('/battles/create', json={'event_id': event_id, 'mode': 'ffa'}, headers={'Authorization': f'Bearer {bartender_token}'})
    assert forbidden.status_code == 403

    created = client.post('/battles/create', json={'event_id': event_id, 'mode': 'ffa'}, headers={'Authorization': f'Bearer {manager_token}'})
    assert created.status_code == 200
    battle_id = created.json()['id']

    user_token = _guest(client, 'u1')
    join1 = client.post(f'/battles/{battle_id}/join', json={}, headers={'Authorization': f'Bearer {user_token}'})
    join2 = client.post(f'/battles/{battle_id}/join', json={}, headers={'Authorization': f'Bearer {user_token}'})
    assert join1.status_code == 200 and join1.json()['idempotent'] is False
    assert join2.status_code == 200 and join2.json()['idempotent'] is True

    sub = client.post(f'/battles/{battle_id}/submit', json={'scan_id': 'scan-1', 'points': 2}, headers={'Authorization': f'Bearer {user_token}'})
    assert sub.status_code == 200
    submit_id = sub.json()['submit_id']

    val = client.post(f'/battles/{battle_id}/validate', json={'submit_id': submit_id}, headers={'Authorization': f'Bearer {manager_token}'})
    assert val.status_code == 200

    board = client.get(f'/battles/{battle_id}/leaderboard')
    assert board.status_code == 200
    assert board.json()['rows'][0]['score'] == 2

    s = get_session()
    try:
        cfg = s.query(EventModuleConfig).filter(EventModuleConfig.event_id == event_id).first()
        cfg.battles_enabled = False
        s.add(cfg)
        s.commit()
    finally:
        s.close()
    disabled = client.post('/battles/create', json={'event_id': event_id, 'mode': 'ffa'}, headers={'Authorization': f'Bearer {manager_token}'})
    assert disabled.status_code == 409


def test_checkins_pagination_and_aggregation():
    _, event_id, _ = _seed('manager')
    client = TestClient(app)
    token = _guest(client, 'checkin-user')
    for idx in range(3):
        res = client.post('/drinks/checkin', json={'free_text_name': f'Beer {idx%2}', 'event_id': event_id}, headers={'Authorization': f'Bearer {token}'})
        assert res.status_code == 200

    page1 = client.get('/drinks/checkins/me?limit=2', headers={'Authorization': f'Bearer {token}'})
    assert page1.status_code == 200
    cursor = page1.json()['next_cursor']
    assert cursor
    page2 = client.get(f'/drinks/checkins/me?limit=2&cursor={cursor}', headers={'Authorization': f'Bearer {token}'})
    assert page2.status_code == 200
    assert len(page2.json()['items']) == 1

    agg = client.get(f'/drinks/checkins/event/{event_id}')
    assert agg.status_code == 200
    assert sum(x['count'] for x in agg.json()['top_drinks']) == 3


def test_wifi_and_module_off_behavior():
    bar_id, event_id, manager_token = _seed('manager')
    client = TestClient(app)
    res = client.post('/partner/portal/wifi/set', json={'bar_id': bar_id, 'event_id': event_id, 'ssid': 'BAR', 'password': 'secret'}, headers={'Authorization': f'Bearer {manager_token}'})
    assert res.status_code == 200

    pub = client.get(f'/public/wifi?bar_id={bar_id}&event_id={event_id}')
    assert pub.status_code == 200
    assert pub.json()['ssid'] == 'BAR'

    s = get_session()
    try:
        cfg = s.query(EventModuleConfig).filter(EventModuleConfig.event_id == event_id).first()
        cfg.wifi_enabled = False
        s.add(cfg)
        s.commit()
    finally:
        s.close()

    disabled = client.get(f'/public/wifi?bar_id={bar_id}&event_id={event_id}')
    assert disabled.status_code == 204


def test_wifi_public_returns_no_content_before_event_starts():
    bar_id, _, manager_token = _seed('manager')
    client = TestClient(app)

    s = get_session()
    try:
        future_event = Event(
            bar_id=bar_id,
            name='Future WiFi Event',
            starts_at=now_utc() + timedelta(hours=1),
            ends_at=now_utc() + timedelta(hours=3),
        )
        s.add(future_event)
        s.flush()
        s.add(EventModuleConfig(event_id=future_event.id, wifi_enabled=True))
        s.commit()
        event_id = future_event.id
    finally:
        s.close()

    res = client.post('/partner/portal/wifi/set', json={'bar_id': bar_id, 'event_id': event_id, 'ssid': 'BAR', 'password': 'secret'}, headers={'Authorization': f'Bearer {manager_token}'})
    assert res.status_code == 200

    pub = client.get(f'/public/wifi?bar_id={bar_id}&event_id={event_id}')
    assert pub.status_code == 204


def test_safety_transitions_and_smoke_audit_viewer():
    _, event_id, manager_token = _seed('manager')
    client = TestClient(app)
    token = _guest(client, 'safe-user')
    start = client.post('/safety/buddy/start', json={'buddy_user_id': 'buddy', 'expires_minutes': 10, 'event_id': event_id}, headers={'Authorization': f'Bearer {token}'})
    assert start.status_code == 200
    session_id = start.json()['session_id']
    ping = client.post('/safety/buddy/ping', json={'session_id': session_id}, headers={'Authorization': f'Bearer {token}'})
    assert ping.status_code == 200
    end = client.post('/safety/buddy/end', json={'session_id': session_id}, headers={'Authorization': f'Bearer {token}'})
    assert end.status_code == 200

    audit = client.get(f'/partner/portal/audit/logs?event_id={event_id}', headers={'Authorization': f'Bearer {manager_token}'})
    assert audit.status_code == 200
    assert 'items' in audit.json()


def test_safety_ping_rate_limit_uses_ping_window_not_start_expiry_default():
    _, event_id, _ = _seed('manager')
    client = TestClient(app)
    token = _guest(client, 'safe-default-expiry')

    start = client.post('/safety/buddy/start', json={'buddy_user_id': 'buddy', 'event_id': event_id}, headers={'Authorization': f'Bearer {token}'})
    assert start.status_code == 200
    session_id = start.json()['session_id']

    first_ping = client.post('/safety/buddy/ping', json={'session_id': session_id}, headers={'Authorization': f'Bearer {token}'})
    assert first_ping.status_code == 200

    second_ping = client.post('/safety/buddy/ping', json={'session_id': session_id}, headers={'Authorization': f'Bearer {token}'})
    assert second_ping.status_code == 429
