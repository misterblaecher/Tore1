import secrets
from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import AppUser, Bar, Event, EventRuntimeState, EventStaff, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed(module_on: bool = True):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suf = secrets.token_hex(4)
        bar = Bar(name=f"Music R {suf}", city="Liège", partner_code=f"MUSICR{suf}")
        s.add(bar)
        s.flush()
        manager = PartnerUser(display_name="Manager", pin_hash="hash")
        s.add(manager)
        s.flush()
        s.add(PartnerMembership(user_id=manager.id, bar_id=bar.id, role="manager", display_name="Manager"))
        ev = Event(
            bar_id=bar.id,
            name="Music Event",
            starts_at=now_utc() - timedelta(hours=1),
            ends_at=now_utc() + timedelta(hours=5),
            modules_on={"music_vote": module_on},
        )
        s.add(ev)
        s.commit()
        return {
            "event_id": ev.id,
            "bar_id": bar.id,
            "manager_token": _make_token(manager.id, bar.id, "manager", "Manager"),
        }
    finally:
        s.close()


def _guest_token(client: TestClient, name: str) -> tuple[str, str]:
    res = client.post('/auth/guest', json={'display_name': name})
    assert res.status_code == 200
    payload = res.json()
    return payload['token'], payload['user']['id']


def _candidate(title: str = "Song A"):
    return {
        "provider": "spotify",
        "externalUrl": f"https://open.spotify.com/track/{title.replace(' ', '').lower()}",
        "title": title,
        "artist": "Artist",
    }


def test_round_start_idempotent():
    seed = _seed()
    client = TestClient(app)
    headers = {'Authorization': f"Bearer {seed['manager_token']}", 'Idempotency-Key': 'round-start-1'}
    r1 = client.post(f"/events/{seed['event_id']}/music/admin/round/start", json={'durationSec': 60}, headers=headers)
    assert r1.status_code == 200
    r2 = client.post(f"/events/{seed['event_id']}/music/admin/round/start", json={'durationSec': 60}, headers=headers)
    assert r2.status_code == 200
    assert r2.json()['round']['roundId'] == r1.json()['round']['roundId']


def test_vote_rejected_when_no_round_open():
    seed = _seed()
    client = TestClient(app)
    user_token, _ = _guest_token(client, 'round-user')
    res = client.post(
        f"/events/{seed['event_id']}/music/vote",
        json={'candidate': _candidate()},
        headers={'Authorization': f'Bearer {user_token}', 'Idempotency-Key': 'vote-no-round'},
    )
    assert res.status_code == 409
    assert res.json()['detail']['reason'] == 'VOTE_CLOSED'


def test_end_round_locks_winner():
    seed = _seed()
    client = TestClient(app)
    user_token, _ = _guest_token(client, 'round-winner')
    client.post(
        f"/events/{seed['event_id']}/music/admin/round/start",
        json={'durationSec': 120},
        headers={'Authorization': f"Bearer {seed['manager_token']}", 'Idempotency-Key': 'start-winner'},
    )
    vote = client.post(
        f"/events/{seed['event_id']}/music/vote",
        json={'candidate': _candidate('Song Winner')},
        headers={'Authorization': f'Bearer {user_token}', 'Idempotency-Key': 'vote-win'},
    )
    assert vote.status_code == 200
    end = client.post(
        f"/events/{seed['event_id']}/music/admin/round/end",
        headers={'Authorization': f"Bearer {seed['manager_token']}", 'Idempotency-Key': 'end-winner'},
    )
    assert end.status_code == 200
    assert end.json()['round']['status'] == 'LOCKED'
    assert end.json()['winner']['candidate']['title'] == 'Song Winner'


def test_now_playing_requires_permission():
    seed = _seed()
    client = TestClient(app)
    user_token, _ = _guest_token(client, 'plain-user')
    denied = client.post(
        f"/events/{seed['event_id']}/music/admin/now-playing",
        json={'candidate': _candidate('Now')},
        headers={'Authorization': f'Bearer {user_token}', 'Idempotency-Key': 'np-denied'},
    )
    assert denied.status_code == 403


def test_dj_override_respected_for_round_start():
    seed = _seed()
    client = TestClient(app)
    dj_token, dj_user_id = _guest_token(client, 'dj-override')
    denied = client.post(
        f"/events/{seed['event_id']}/music/admin/round/start",
        json={'durationSec': 60},
        headers={'Authorization': f'Bearer {dj_token}', 'Idempotency-Key': 'dj-denied'},
    )
    assert denied.status_code == 403

    enable = client.post(
        f"/events/{seed['event_id']}/music/admin/settings",
        json={'djOverrideEnabled': True},
        headers={'Authorization': f"Bearer {seed['manager_token']}", 'Idempotency-Key': 'enable-dj-ovr'},
    )
    assert enable.status_code == 200

    s = get_session()
    try:
        s.add(EventStaff(event_id=seed['event_id'], user_id=dj_user_id, role='dj', is_active=True))
        s.commit()
    finally:
        s.close()

    allowed = client.post(
        f"/events/{seed['event_id']}/music/admin/round/start",
        json={'durationSec': 60},
        headers={'Authorization': f'Bearer {dj_token}', 'Idempotency-Key': 'dj-allowed'},
    )
    assert allowed.status_code == 200


def test_runtime_blocked_writes_return_403():
    seed = _seed()
    client = TestClient(app)
    s = get_session()
    try:
        s.add(EventRuntimeState(event_id=seed['event_id'], state='PAUSE'))
        s.commit()
    finally:
        s.close()

    blocked = client.post(
        f"/events/{seed['event_id']}/music/admin/round/start",
        json={'durationSec': 60},
        headers={'Authorization': f"Bearer {seed['manager_token']}", 'Idempotency-Key': 'runtime-blocked'},
    )
    assert blocked.status_code == 403
    assert blocked.json()['detail']['reason'] == 'runtime_blocked'
