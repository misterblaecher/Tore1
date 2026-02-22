import secrets
from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import Bar, Event, EventConfig, EventRuntimeState, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_manager_event():
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"RC Bar {suffix}", city="Liege", partner_code=f"RC{suffix}")
        s.add(bar)
        s.flush()
        manager = PartnerUser(display_name="Manager", pin_hash="hash")
        s.add(manager)
        s.flush()
        s.add(PartnerMembership(user_id=manager.id, bar_id=bar.id, role="manager", display_name="Manager"))
        event = Event(bar_id=bar.id, name="RC", starts_at=now_utc() - timedelta(hours=1), ends_at=now_utc() + timedelta(hours=3))
        s.add(event)
        s.commit()
        return event.id, _make_token(manager.id, bar.id, "manager", "Manager")
    finally:
        s.close()


def _guest(client: TestClient, name: str):
    res = client.post('/auth/guest', json={'display_name': name})
    assert res.status_code == 200
    payload = res.json()
    return payload['user']['id'], payload['token']


def _topup(client: TestClient, token: str, event_id: int, user_id: str, amount: int, idem: str):
    return client.post(
        '/partner/portal/wallet/topup',
        json={
            'event_id': event_id,
            'target_user_id': user_id,
            'amount_cents': amount,
            'reason_code': 'seed',
            'reason_text': 'seed topup',
        },
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': idem},
    )


def _set_runtime(event_id: int, state: str):
    s = get_session()
    try:
        row = s.query(EventRuntimeState).filter(EventRuntimeState.event_id == event_id).first()
        if row is None:
            row = EventRuntimeState(event_id=event_id, state=state, updated_at=now_utc())
        else:
            row.state = state
            row.updated_at = now_utc()
        s.add(row)
        s.commit()
    finally:
        s.close()


def test_wallet_credit_idempotency_prevents_duplicates():
    client = TestClient(app)
    event_id, manager_token = _seed_manager_event()
    user_id, _ = _guest(client, 'credit-user')
    first = _topup(client, manager_token, event_id, user_id, 30, 'idem-credit-1')
    second = _topup(client, manager_token, event_id, user_id, 30, 'idem-credit-1')
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()['idempotent'] is True


def test_wallet_transfer_idempotency_prevents_duplicates():
    client = TestClient(app)
    event_id, manager_token = _seed_manager_event()
    sender_id, sender_token = _guest(client, 'sender-rc')
    receiver_id, _ = _guest(client, 'receiver-rc')
    assert _topup(client, manager_token, event_id, sender_id, 20, 'idem-credit-2').status_code == 200

    first = client.post(
        '/wallet/transfers',
        json={
            'event_id': event_id,
            'to_user_id': receiver_id,
            'amount': 5,
            'reason_code': 'gift',
            'reason_text': 'gift transfer',
        },
        headers={'Authorization': f'Bearer {sender_token}', 'Idempotency-Key': 'idem-transfer-1'},
    )
    second = client.post(
        '/wallet/transfers',
        json={
            'event_id': event_id,
            'to_user_id': receiver_id,
            'amount': 5,
            'reason_code': 'gift',
            'reason_text': 'gift transfer',
        },
        headers={'Authorization': f'Bearer {sender_token}', 'Idempotency-Key': 'idem-transfer-1'},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()['idempotent'] is True


def test_missing_idempotency_key_rejected():
    client = TestClient(app)
    event_id, manager_token = _seed_manager_event()
    user_id, _ = _guest(client, 'missing-idem')
    res = client.post(
        '/partner/portal/wallet/topup',
        json={'event_id': event_id, 'target_user_id': user_id, 'amount_cents': 10, 'reason_code': 'manual', 'reason_text': 'manual topup'},
        headers={'Authorization': f'Bearer {manager_token}'},
    )
    assert res.status_code == 400
    assert res.json()['detail']['reason'] == 'missing_idempotency'


def test_missing_reason_rejected():
    client = TestClient(app)
    event_id, manager_token = _seed_manager_event()
    user_id, _ = _guest(client, 'missing-reason')
    res = client.post(
        '/partner/portal/wallet/topup',
        json={'event_id': event_id, 'target_user_id': user_id, 'amount_cents': 10},
        headers={'Authorization': f'Bearer {manager_token}', 'Idempotency-Key': 'idem-missing-reason'},
    )
    assert res.status_code == 422
    assert res.json()['detail']['reason'] == 'missing_reason'


def test_paused_and_ended_block_writes():
    client = TestClient(app)
    event_id, manager_token = _seed_manager_event()
    user_id, _ = _guest(client, 'paused-user')

    _set_runtime(event_id, 'PAUSED')
    paused = _topup(client, manager_token, event_id, user_id, 10, 'idem-paused')
    assert paused.status_code == 423
    assert paused.json()['detail']['reason'] == 'event_paused'

    _set_runtime(event_id, 'ENDED')
    ended = _topup(client, manager_token, event_id, user_id, 10, 'idem-ended')
    assert ended.status_code == 423
    assert ended.json()['detail']['reason'] == 'event_ended'


def test_module_off_blocks_write_with_412():
    client = TestClient(app)
    event_id, manager_token = _seed_manager_event()
    user_id, _ = _guest(client, 'module-off-user')
    s = get_session()
    try:
        cfg = s.query(EventConfig).filter(EventConfig.event_id == event_id).first()
        if cfg is None:
            cfg = EventConfig(event_id=event_id, wallet_enabled=False)
        else:
            cfg.wallet_enabled = False
        s.add(cfg)
        s.commit()
    finally:
        s.close()

    blocked = _topup(client, manager_token, event_id, user_id, 10, 'idem-module-off')
    assert blocked.status_code == 412
    assert blocked.json()['detail']['reason'] == 'module_off'
