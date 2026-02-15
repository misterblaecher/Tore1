from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import AuditLog, Bar, Event, EventCostSimpleIdempotency, Order, OrderItem, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed_manager_event_with_orders():
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name='Profit Bar', city='Liege', partner_code=f'PROF{suffix}')
        s.add(bar)
        s.flush()

        user = PartnerUser(display_name='Manager Profit', pin_hash='hash')
        s.add(user)
        s.flush()
        s.add(PartnerMembership(user_id=user.id, bar_id=bar.id, role='manager', display_name='Manager Profit'))

        event = Event(
            bar_id=bar.id,
            name='Profit Event',
            starts_at=now_utc() - timedelta(hours=2),
            ends_at=now_utc() + timedelta(hours=2),
        )
        s.add(event)
        s.flush()

        order1 = Order(bar_id=bar.id, event_id=event.id, user_id='u1', total_tickets=10, total_cents=0, created_at=now_utc(), updated_at=now_utc())
        order2 = Order(bar_id=bar.id, event_id=event.id, user_id='u2', total_tickets=6, total_cents=0, created_at=now_utc(), updated_at=now_utc())
        s.add_all([order1, order2])
        s.flush()

        s.add_all([
            OrderItem(order_id=order1.id, name_snapshot='Beer', qty=2, line_total_cents=0, unit_price_cents=0),
            OrderItem(order_id=order2.id, name_snapshot='Shot', qty=1, line_total_cents=0, unit_price_cents=0),
        ])
        s.commit()
        return event.id, _make_token(user.id, bar.id, 'manager', 'Manager Profit')
    finally:
        s.close()


def test_profitability_returns_computed_gross_from_orders():
    event_id, token = _seed_manager_event_with_orders()
    client = TestClient(app)

    res = client.get(f'/partner/portal/orga/events/{event_id}/profitability', headers={'Authorization': f'Bearer {token}'})

    assert res.status_code == 200
    payload = res.json()
    assert payload['ordersCount'] == 2
    assert payload['itemsCount'] == 3
    assert payload['grossRevenueTickets'] == 16
    assert payload['avgOrderValueTickets'] == 8.0
    assert payload['netEstimateTickets'] == 16


def test_costs_update_is_idempotent_and_audited_once():
    event_id, token = _seed_manager_event_with_orders()
    client = TestClient(app)

    headers = {'Authorization': f'Bearer {token}', 'Idempotency-Key': 'profitability-costs-1'}
    body = {'costsTickets': 5, 'notes': 'DJ + sécurité', 'breakdown': {'staff': 2, 'dj': 3}}

    first = client.put(f'/partner/portal/orga/events/{event_id}/costs', json=body, headers=headers)
    second = client.put(f'/partner/portal/orga/events/{event_id}/costs', json=body, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()['costs']['costsTickets'] == 5
    assert first.json()['netEstimateTickets'] == 11

    s = get_session()
    try:
        idem = s.query(EventCostSimpleIdempotency).filter(EventCostSimpleIdempotency.event_id == event_id, EventCostSimpleIdempotency.idempotency_key == 'profitability-costs-1').first()
        assert idem is not None
        audits = s.query(AuditLog).filter(AuditLog.event_id == event_id, AuditLog.action == 'orga.profitability.costs.update').all()
        assert len(audits) == 1
    finally:
        s.close()


def test_profitability_export_csv_contains_expected_columns():
    event_id, token = _seed_manager_event_with_orders()
    client = TestClient(app)

    put = client.put(
        f'/partner/portal/orga/events/{event_id}/costs',
        json={'costsTickets': 4, 'notes': 'Costs snapshot'},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': f'export-{datetime.utcnow().timestamp()}'},
    )
    assert put.status_code == 200

    res = client.get(f'/partner/portal/orga/events/{event_id}/profitability/export.csv', headers={'Authorization': f'Bearer {token}'})

    assert res.status_code == 200
    lines = [line.strip() for line in res.text.splitlines() if line.strip()]
    assert lines[0] == 'event_id,timestamp,ordersCount,grossTickets,costsTickets,netTickets,notes'
    assert 'Costs snapshot' in lines[1]
