from fastapi.testclient import TestClient

import uuid

from db import Base, engine, get_session, now_utc
from main import app
from models import AppUserPrivacySetting, Bar, BarPrivacySetting, Event, TicketTransfer


def _seed_event(modules_on: dict | None = None) -> int:
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        bar = Bar(name=f"Ticker Ext {now_utc().timestamp()}", city="Liege", partner_code=f"TKE{uuid.uuid4().hex[:10]}")
        s.add(bar)
        s.flush()
        event = Event(bar_id=bar.id, name="Ticker Extended", modules_on=modules_on or {"gifts_enabled": True, "menu": True, "ticker": True, "broadcast": False})
        s.add(event)
        s.flush()
        s.add(BarPrivacySetting(bar_id=bar.id, staff_identity_consent_required=True))
        s.commit()
        return event.id
    finally:
        s.close()


def _guest(client: TestClient, name: str) -> tuple[str, str]:
    res = client.post('/auth/guest', json={'display_name': name})
    assert res.status_code == 200
    tok = res.json()['token']
    me = client.get('/auth/me', headers={'Authorization': f'Bearer {tok}'})
    assert me.status_code == 200
    return tok, me.json()['id']


def _insert_transfer(event_id: int, from_user_id: str, to_user_id: str, amount: int = 5):
    s = get_session()
    try:
        s.add(AppUserPrivacySetting(user_id=from_user_id, visibility='private', show_identity_in_bar=True, show_identity_to_staff=True))
        s.add(AppUserPrivacySetting(user_id=to_user_id, visibility='private', show_identity_in_bar=True, show_identity_to_staff=True))
        s.add(TicketTransfer(event_id=event_id, from_user_id=from_user_id, to_user_id=to_user_id, amount=amount, reason='gift'))
        s.commit()
    finally:
        s.close()


def test_ticker_extended_gifts_on_with_privacy_masking_and_since():
    event_id = _seed_event({"gifts_enabled": True, "menu": False, "ticker": False, "broadcast": False})
    client = TestClient(app)
    user_token, user_id = _guest(client, 'alice')
    _, bob_id = _guest(client, 'bob')
    _insert_transfer(event_id, user_id, bob_id, amount=7)

    feed = client.get(f'/events/{event_id}/ticker?types=gift&limit=50', headers={'Authorization': f'Bearer {user_token}'})
    assert feed.status_code == 200
    data = feed.json()
    assert data['items']
    gift_item = data['items'][0]
    assert gift_item['type'] == 'gift'
    payload = gift_item['payloadCompact']
    assert payload['fromLabel'].startswith('U***')
    assert payload['toLabel'].startswith('U***')

    since = gift_item['ts']
    newer = client.get(f'/events/{event_id}/ticker?types=gift&since={since}', headers={'Authorization': f'Bearer {user_token}'})
    assert newer.status_code == 200
    assert newer.json()['items'] == []


def test_ticker_extended_gifts_off_excludes_items():
    event_id = _seed_event({"gifts_enabled": False, "menu": False, "ticker": False, "broadcast": False})
    client = TestClient(app)
    user_token, user_id = _guest(client, 'charlie')
    _, dana_id = _guest(client, 'dana')
    _insert_transfer(event_id, user_id, dana_id, amount=4)

    feed = client.get(f'/events/{event_id}/ticker?types=gift&limit=50', headers={'Authorization': f'Bearer {user_token}'})
    assert feed.status_code == 200
    assert feed.json()['items'] == []
