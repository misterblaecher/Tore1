from __future__ import annotations

from datetime import datetime, timedelta
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import AuditLog, Bar, Event, MenuCategory, MenuItem


def _seed_event_and_user():
    Base.metadata.create_all(engine)
    client = TestClient(app)
    user_token = client.post('/auth/guest', json={'display_name': f'user-{secrets.token_hex(2)}'}).json()['token']
    s = get_session()
    try:
        bar = Bar(name='Capstone Bar', city='Liege', partner_code=f'CP{secrets.token_hex(3)}')
        s.add(bar)
        s.flush()
        event = Event(
            bar_id=bar.id,
            name='Capstone Event',
            starts_at=datetime.utcnow().replace(microsecond=0) - timedelta(hours=1),
            ends_at=datetime.utcnow().replace(microsecond=0) + timedelta(hours=2),
            event_code=f'E{secrets.token_hex(3).upper()}',
        )
        s.add(event)
        s.flush()
        category = MenuCategory(bar_id=bar.id, name='Softs')
        s.add(category)
        s.flush()
        item = MenuItem(bar_id=bar.id, category_id=category.id, name='Cola', price_cents=300, is_active=True, is_available=True)
        s.add(item)
        s.commit()
        return client, user_token, event.id, event.event_code, bar.id, item.id
    finally:
        s.close()


def test_critical_writes_require_idempotency_key_and_emit_audit():
    client, token, event_id, event_code, bar_id, item_id = _seed_event_and_user()

    missing_join = client.post(
        f'/events/{event_id}/join',
        json={},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert missing_join.status_code == 400
    assert missing_join.json()['detail']['reason'] == 'IDEMPOTENCY_REQUIRED'

    missing_join_by_code = client.post(
        '/events/join_by_code',
        json={'code': event_code},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert missing_join_by_code.status_code == 400
    assert missing_join_by_code.json()['detail']['reason'] == 'IDEMPOTENCY_REQUIRED'

    joined = client.post(
        f'/events/{event_id}/join',
        json={},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'join-capstone-1'},
    )
    assert joined.status_code == 200

    missing_order = client.post(
        '/orders',
        json={
            'bar_id': bar_id,
            'event_id': event_id,
            'items': [{'item_id': item_id, 'qty': 1}],
            'payment_mode': 'pay_later',
        },
        headers={'Authorization': f'Bearer {token}'},
    )
    assert missing_order.status_code == 400
    assert missing_order.json()['detail']['reason'] == 'IDEMPOTENCY_REQUIRED'

    created_order = client.post(
        '/orders',
        json={
            'bar_id': bar_id,
            'event_id': event_id,
            'items': [{'item_id': item_id, 'qty': 1}],
            'payment_mode': 'pay_later',
        },
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'order-capstone-1'},
    )
    assert created_order.status_code == 200

    s = get_session()
    try:
        join_audit = s.query(AuditLog).filter(AuditLog.action == 'event.join', AuditLog.event_id == event_id).first()
        assert join_audit is not None
        assert join_audit.actor_user_id is not None
        assert join_audit.idempotency_key == 'join-capstone-1'

        order_audit = s.query(AuditLog).filter(AuditLog.action == 'orders.create', AuditLog.event_id == event_id).first()
        assert order_audit is not None
        assert order_audit.actor_user_id is not None
        assert order_audit.idempotency_key == 'order-capstone-1'
    finally:
        s.close()
