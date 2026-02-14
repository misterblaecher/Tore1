from fastapi.testclient import TestClient

import secrets

from db import Base, engine, get_session
from main import app
from models import AuditLog, Bar, Event, EventRuntimeState, MenuCategory, MenuItem, Order, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_partner(role: str = "manager"):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"Orders Live {suffix}", city="Paris", partner_code=f"OL{suffix}")
        s.add(bar)
        s.flush()
        user = PartnerUser(display_name="Staff", pin_hash="hash")
        s.add(user)
        s.flush()
        s.add(PartnerMembership(user_id=user.id, bar_id=bar.id, role=role, display_name="Staff"))
        s.commit()
        return bar.id, user.id, _make_token(user.id, bar.id, role, "Staff")
    finally:
        s.close()


def _seed_item(bar_id: int) -> int:
    s = get_session()
    try:
        cat = MenuCategory(bar_id=bar_id, name="Bière", sort_order=1)
        s.add(cat)
        s.flush()
        item = MenuItem(bar_id=bar_id, category_id=cat.id, name="IPA", price_cents=700)
        s.add(item)
        s.commit()
        return item.id
    finally:
        s.close()


def _seed_event(bar_id: int) -> int:
    s = get_session()
    try:
        event = Event(bar_id=bar_id, name="Soirée")
        s.add(event)
        s.commit()
        return event.id
    finally:
        s.close()


def test_orders_live_idempotence_pause_and_audit():
    bar_id, _, staff_token = _seed_partner(role="bartender")
    item_id = _seed_item(bar_id)
    event_id = _seed_event(bar_id)
    client = TestClient(app)

    body = {
        "bar_id": bar_id,
        "event_id": event_id,
        "items": [{"item_id": item_id, "qty": 2}],
        "device_id": "phone-1",
        "idempotency_key": "order-live-1",
    }
    first = client.post('/orders', json=body)
    second = client.post('/orders', json=body, headers={'Idempotency-Key': 'order-live-1'})
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()['id'] == second.json()['id']

    live = client.get(f'/orders/live?event_id={event_id}&status=pending')
    assert live.status_code == 200
    assert any(row['id'] == first.json()['id'] for row in live.json()['items'])

    patched = client.patch(
        f"/orders/{first.json()['id']}/status",
        json={'status': 'accepted'},
        headers={'Authorization': f'Bearer {staff_token}'},
    )
    assert patched.status_code == 200
    assert patched.json()['status'] == 'IN_PROGRESS'

    s = get_session()
    try:
        create_audit = s.query(AuditLog).filter(AuditLog.action == 'orders.create', AuditLog.entity_id == str(first.json()['id'])).first()
        update_audit = s.query(AuditLog).filter(AuditLog.action == 'orders.status_update', AuditLog.entity_id == str(first.json()['id'])).first()
        assert create_audit is not None
        assert update_audit is not None

        runtime = s.query(EventRuntimeState).filter(EventRuntimeState.event_id == event_id).first()
        if runtime is None:
            runtime = EventRuntimeState(event_id=event_id, state='PAUSE')
            s.add(runtime)
        else:
            runtime.state = 'PAUSE'
            s.add(runtime)
        s.commit()
    finally:
        s.close()

    blocked = client.post('/orders', json={
        'bar_id': bar_id,
        'event_id': event_id,
        'items': [{'item_id': item_id, 'qty': 1}],
        'device_id': 'phone-2',
        'idempotency_key': 'order-live-paused',
    })
    assert blocked.status_code == 423
    assert blocked.json()['detail']['reason'] == 'event_paused'

    s = get_session()
    try:
        count = s.query(Order).filter(Order.idempotency_key == 'order-live-1', Order.bar_id == bar_id).count()
        assert count == 1
    finally:
        s.close()
