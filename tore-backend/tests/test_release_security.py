import pytest
from fastapi import HTTPException
from app.services.feature_policy_service import require_value_predictions_enabled


def test_value_predictions_are_disabled_without_explicit_configuration(monkeypatch):
    monkeypatch.delenv('TORE_VALUE_PREDICTIONS_ENABLED', raising=False)
    with pytest.raises(HTTPException) as error:
        require_value_predictions_enabled()
    assert error.value.status_code == 403
    assert error.value.detail['code'] == 'VALUE_PREDICTIONS_DISABLED'


def test_value_predictions_require_explicit_opt_in(monkeypatch):
    monkeypatch.setenv('TORE_VALUE_PREDICTIONS_ENABLED', '1')
    require_value_predictions_enabled()


def test_wallet_ledger_rejects_changed_retry_and_overdraft():
    from fastapi.testclient import TestClient
    from db import Base, engine, get_session
    from main import app
    from models import Wallet, WalletTx
    from app.services.wallet_service import apply_wallet_tx

    Base.metadata.create_all(engine)
    user_id = TestClient(app).post('/auth/guest', json={'display_name': 'Ledger regression'}).json()['user']['id']
    s = get_session()
    try:
        args = dict(user_id=user_id, kind='CREDIT', amount_tickets=20, ref_type='TEST', ref_id=None, idempotency_key='credit')
        apply_wallet_tx(s, **args)
        s.commit()
        assert apply_wallet_tx(s, **args)[2] is False
        with pytest.raises(HTTPException) as conflict:
            apply_wallet_tx(s, **{**args, 'amount_tickets': 30})
        assert conflict.value.detail['reason'] == 'idempotency_conflict'
        with pytest.raises(HTTPException) as denied:
            apply_wallet_tx(s, **{**args, 'kind': 'DEBIT', 'amount_tickets': -21, 'idempotency_key': 'debit'})
        assert denied.value.detail['reason'] == 'insufficient_balance'
        s.rollback()
        assert s.get(Wallet, user_id).balance_tickets == 20
        assert s.query(WalletTx).filter_by(user_id=user_id).count() == 1
    finally:
        s.close()


def test_wallet_gift_idempotency_is_scoped_per_sender_and_retry_is_stable():
    from fastapi.testclient import TestClient
    from db import Base, engine, get_session
    from main import app
    from models import WalletGift, WalletTx
    from app.services.wallet_service import apply_wallet_tx

    Base.metadata.create_all(engine)
    client = TestClient(app)
    sender_a = client.post('/auth/guest', json={'display_name': 'Gift sender A'})
    sender_b = client.post('/auth/guest', json={'display_name': 'Gift sender B'})
    recipient = client.post('/auth/guest', json={'display_name': 'Gift recipient'})
    token_a, user_a = sender_a.json()['token'], sender_a.json()['user']['id']
    token_b, user_b = sender_b.json()['token'], sender_b.json()['user']['id']
    recipient_id = recipient.json()['user']['id']

    db = get_session()
    try:
        apply_wallet_tx(db, user_id=user_a, kind='CREDIT', amount_tickets=20, ref_type='TEST', ref_id='gift-seed-a', idempotency_key='gift-seed-a')
        apply_wallet_tx(db, user_id=user_b, kind='CREDIT', amount_tickets=20, ref_type='TEST', ref_id='gift-seed-b', idempotency_key='gift-seed-b')
        db.commit()
    finally:
        db.close()

    payload_a = {'to_user_id': recipient_id, 'amount_cents': 7, 'message': 'A'}
    payload_b = {'to_user_id': recipient_id, 'amount_cents': 11, 'message': 'B'}
    headers_a = {'Authorization': f'Bearer {token_a}', 'Idempotency-Key': 'same-client-key'}
    headers_b = {'Authorization': f'Bearer {token_b}', 'Idempotency-Key': 'same-client-key'}
    first_a = client.post('/wallet/gift', json=payload_a, headers=headers_a)
    first_b = client.post('/wallet/gift', json=payload_b, headers=headers_b)
    retry_a = client.post('/wallet/gift', json=payload_a, headers=headers_a)
    assert first_a.status_code == 200
    assert first_b.status_code == 200
    assert retry_a.status_code == 200
    assert retry_a.json() == first_a.json()
    assert first_a.json()['gift_id'] != first_b.json()['gift_id']

    db = get_session()
    try:
        assert db.query(WalletGift).filter(WalletGift.from_user_id.in_([user_a, user_b])).count() == 2
        assert db.query(WalletTx).filter(WalletTx.user_id == user_a, WalletTx.ref_type == 'GIFT_OUT').count() == 1
        assert db.query(WalletTx).filter(WalletTx.user_id == user_b, WalletTx.ref_type == 'GIFT_OUT').count() == 1
    finally:
        db.close()
