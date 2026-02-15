from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import Bet, BetPosition, Event, EventJoin, Order, TicketTransfer, AppUserPrivacySetting


def _create_guest(client: TestClient, name: str) -> tuple[str, str]:
    res = client.post('/auth/guest', json={'display_name': name})
    assert res.status_code == 200
    payload = res.json()
    return payload['token'], payload['user']['id']


def _seed_event() -> int:
    s = get_session()
    try:
        event = Event(
            name='Ranking Event',
            starts_at=now_utc(),
            ends_at=now_utc() + timedelta(hours=5),
            entry_price_cents=0,
            ticket_mode=True,
        )
        s.add(event)
        s.commit()
        s.refresh(event)
        return event.id
    finally:
        s.close()


def test_event_ranking_aggregates_and_me_position():
    Base.metadata.create_all(engine)
    client = TestClient(app)

    token_a, user_a = _create_guest(client, 'Alice')
    _, user_b = _create_guest(client, 'Bob')

    event_id = _seed_event()

    s = get_session()
    try:
        s.add_all([
            EventJoin(event_id=event_id, user_id=user_a, idempotency_key=f'join-{user_a}'),
            EventJoin(event_id=event_id, user_id=user_b, idempotency_key=f'join-{user_b}'),
            Order(event_id=event_id, user_id=user_a, total_tickets=30, total_cents=0, status='DONE'),
            Order(event_id=event_id, user_id=user_a, total_tickets=20, total_cents=0, status='DONE'),
            Order(event_id=event_id, user_id=user_b, total_tickets=10, total_cents=0, status='DONE'),
            TicketTransfer(event_id=event_id, from_user_id=user_a, to_user_id=user_b, amount=7),
        ])
        s.flush()

        bet = Bet(
            scope='EVENT',
            event_id=event_id,
            question='Will ranking endpoint ship?',
            kind='OBJECTIVE',
            status='LIVE',
            deadline_at=now_utc() + timedelta(hours=1),
            rules_text='R',
            created_by_user_id=user_a,
        )
        s.add(bet)
        s.flush()
        s.add_all([
            BetPosition(bet_id=bet.id, user_id=user_a, side='YES', stake_tickets=15, idempotency_key='pos-a'),
            BetPosition(bet_id=bet.id, user_id=user_b, side='NO', stake_tickets=3, idempotency_key='pos-b'),
        ])
        s.commit()
    finally:
        s.close()

    res = client.get(f'/events/{event_id}/ranking', headers={'Authorization': f'Bearer {token_a}'})
    assert res.status_code == 200
    data = res.json()

    assert data['eventId'] == event_id
    assert len(data['top3']) >= 2
    assert len(data['list']) >= 2

    me = data['me']
    assert me['displayName'] == 'Alice'
    assert me['rank'] == 1
    assert me['stats']['orders'] == 2
    assert me['stats']['spentTickets'] == 50
    assert me['stats']['giftsSent'] == 7
    assert me['stats']['bets'] == 15
    assert me['score'] == 99  # 50 + (2*10) + (7*2) + 15


def test_event_ranking_privacy_masks_private_users_but_not_me():
    Base.metadata.create_all(engine)
    client = TestClient(app)

    token_public, user_public = _create_guest(client, 'Visible')
    token_private, user_private = _create_guest(client, 'Secret')
    event_id = _seed_event()

    s = get_session()
    try:
        s.add_all([
            EventJoin(event_id=event_id, user_id=user_public, idempotency_key=f'join-{user_public}'),
            EventJoin(event_id=event_id, user_id=user_private, idempotency_key=f'join-{user_private}'),
            Order(event_id=event_id, user_id=user_private, total_tickets=12, total_cents=0, status='DONE'),
            AppUserPrivacySetting(user_id=user_private, visibility='private', show_identity_to_staff=False, show_identity_in_bar=False),
        ])
        s.commit()
    finally:
        s.close()

    viewer_res = client.get(f'/events/{event_id}/ranking', headers={'Authorization': f'Bearer {token_public}'})
    assert viewer_res.status_code == 200
    viewer_data = viewer_res.json()

    masked_row = next(row for row in viewer_data['list'] if row['stats']['spentTickets'] == 12)
    assert masked_row['displayName'].startswith('Anonymous-')

    me_private_res = client.get(f'/events/{event_id}/ranking', headers={'Authorization': f'Bearer {token_private}'})
    assert me_private_res.status_code == 200
    me_private = me_private_res.json()['me']
    assert me_private['displayName'] == 'Secret'
