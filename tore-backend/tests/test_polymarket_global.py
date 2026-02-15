from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import AuditLog
from tests.test_polymarket import _create_global_bet, _create_guest, _seed_wallet_manager, _topup_wallet


def test_global_list_and_detail(monkeypatch):
    Base.metadata.create_all(engine)
    client = TestClient(app)
    token, user_id = _create_guest(client)
    bet_id = _create_global_bet(client, token, user_id, monkeypatch)

    list_res = client.get('/polymarket/global?status=all&type=all', headers={'Authorization': f'Bearer {token}'})
    assert list_res.status_code == 200
    items = list_res.json()['items']
    assert any(item['id'] == bet_id for item in items)

    detail_res = client.get(f'/polymarket/markets/{bet_id}', headers={'Authorization': f'Bearer {token}'})
    assert detail_res.status_code == 200
    assert detail_res.json()['market']['id'] == bet_id
    assert 'orderbook' in detail_res.json()['market']


def test_buy_is_idempotent_and_audited(monkeypatch):
    Base.metadata.create_all(engine)
    client = TestClient(app)
    manager_token = _seed_wallet_manager()
    token, user_id = _create_guest(client)
    bet_id = _create_global_bet(client, token, user_id, monkeypatch)
    _topup_wallet(client, manager_token, user_id, 100)

    headers = {'Authorization': f'Bearer {token}', 'Idempotency-Key': 'global-buy-1'}
    first = client.post(f'/polymarket/markets/{bet_id}/buy', json={'side': 'YES', 'amountTickets': 40}, headers=headers)
    assert first.status_code == 200

    duplicate = client.post(f'/polymarket/markets/{bet_id}/buy', json={'side': 'YES', 'amountTickets': 40}, headers=headers)
    assert duplicate.status_code == 200
    assert duplicate.json()['position']['id'] == first.json()['position']['id']

    s = get_session()
    try:
        rows = s.query(AuditLog).filter(AuditLog.action == 'polymarket.position').all()
        assert rows
    finally:
        s.close()


def test_buy_insufficient_funds_and_resolved_block(monkeypatch):
    Base.metadata.create_all(engine)
    client = TestClient(app)
    token, user_id = _create_guest(client)
    bet_id = _create_global_bet(client, token, user_id, monkeypatch)

    insufficient = client.post(
        f'/polymarket/markets/{bet_id}/buy',
        json={'side': 'YES', 'amountTickets': 9999},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'global-buy-insufficient'},
    )
    assert insufficient.status_code == 400
    assert insufficient.json()['detail']['reason'] == 'insufficient_balance'

    resolve = client.post(
        '/polymarket/resolve',
        json={'market_id': bet_id, 'outcome': 'yes'},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert resolve.status_code == 200

    blocked = client.post(
        f'/polymarket/markets/{bet_id}/buy',
        json={'side': 'NO', 'amountTickets': 10},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'global-buy-resolved'},
    )
    assert blocked.status_code == 409
