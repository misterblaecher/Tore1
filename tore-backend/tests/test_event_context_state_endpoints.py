from datetime import timedelta
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import Bar, Event, EventRuntimeState


def _seed_event() -> int:
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        bar = Bar(name='Context Bar', city='Liege', partner_code=f'CTX{now_utc().timestamp()}')
        s.add(bar)
        s.flush()
        event = Event(
            bar_id=bar.id,
            name='Context Event',
            starts_at=now_utc() - timedelta(hours=1),
            ends_at=now_utc() + timedelta(hours=2),
            event_code=f'C{secrets.token_hex(3).upper()}',
        )
        s.add(event)
        s.commit()
        return event.id
    finally:
        s.close()


def test_event_context_and_state_reflect_runtime_state_updates():
    event_id = _seed_event()
    client = TestClient(app)

    base = client.get(f'/events/{event_id}/context')
    assert base.status_code == 200
    base_payload = base.json()
    assert base_payload['event']['id'] == event_id
    assert base_payload['eventState'] == 'LIVE'
    assert 'modulesOn' in base_payload

    s = get_session()
    try:
        runtime = s.query(EventRuntimeState).filter(EventRuntimeState.event_id == event_id).first()
        if runtime is None:
            runtime = EventRuntimeState(event_id=event_id, state='PAUSE', reason='manual_pause', updated_at=now_utc())
            s.add(runtime)
        else:
            runtime.state = 'PAUSE'
            runtime.reason = 'manual_pause'
            runtime.updated_at = now_utc()
            s.add(runtime)
        s.commit()
    finally:
        s.close()

    fast_state = client.get(f'/events/{event_id}/state')
    assert fast_state.status_code == 200
    fast_payload = fast_state.json()
    assert fast_payload['eventState'] == 'PAUSE'
    assert fast_payload['lastUpdatedAt'] is not None

    after = client.get(f'/events/{event_id}/context')
    assert after.status_code == 200
    after_payload = after.json()
    assert after_payload['eventState'] == 'PAUSE'
    assert after_payload['lastUpdatedAt'] == fast_payload['lastUpdatedAt']


def test_event_context_accepts_app_bearer_token():
    event_id = _seed_event()
    client = TestClient(app)
    guest = client.post('/auth/guest', json={'display_name': 'Context Guest'})
    assert guest.status_code == 200
    token = guest.json()['token']

    response = client.get(
        f'/events/{event_id}/context',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['event']['id'] == event_id
    assert payload['permissions'] == {
        'canCreateBets': False,
        'canResolveBets': False,
        'canAdminMusic': False,
        'canDjMusic': False,
    }
