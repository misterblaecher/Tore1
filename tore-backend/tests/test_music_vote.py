import secrets
from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import AppUser, AuditLog, Bar, Event, EventMusicCandidate, EventRuntimeState, EventStaff, PartnerMembership, PartnerUser
from partner_auth import _make_token


def _seed(module_on: bool = True):
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suf = secrets.token_hex(4)
        bar = Bar(name=f"Music {suf}", city="Liège", partner_code=f"MUSIC{suf}")
        s.add(bar)
        s.flush()
        manager = PartnerUser(display_name="Manager", pin_hash="hash")
        staff = PartnerUser(display_name="Staff", pin_hash="hash")
        s.add_all([manager, staff])
        s.flush()
        s.add(PartnerMembership(user_id=manager.id, bar_id=bar.id, role="manager", display_name="Manager"))
        s.add(PartnerMembership(user_id=staff.id, bar_id=bar.id, role="bartender", display_name="Staff"))
        ev = Event(
            bar_id=bar.id,
            name="Music Event",
            starts_at=now_utc() - timedelta(hours=1),
            ends_at=now_utc() + timedelta(hours=5),
            modules_on={"music_vote": module_on},
        )
        s.add(ev)
        user = AppUser(id=f"u-{suf}", display_name="User")
        dj = AppUser(id=f"dj-{suf}", display_name="DJ")
        s.add_all([user, dj])
        s.flush()
        s.add(EventStaff(event_id=ev.id, user_id=dj.id, role="dj", is_active=True))
        s.commit()
        return {
            "event_id": ev.id,
            "bar_id": bar.id,
            "manager_token": _make_token(manager.id, bar.id, "manager", "Manager"),
            "staff_token": _make_token(staff.id, bar.id, "bartender", "Staff"),
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


def test_module_off_strict_404():
    seed = _seed(module_on=False)
    client = TestClient(app)
    res = client.get(f"/events/{seed['event_id']}/music")
    assert res.status_code == 404
    assert res.json()['detail']['reason'] == 'MODULE_OFF'


def test_vote_idempotent_and_cooldown_enforced():
    seed = _seed(module_on=True)
    client = TestClient(app)
    token, _ = _guest_token(client, 'mv-user')

    set_res = client.post(
        f"/events/{seed['event_id']}/music/admin/settings",
        json={"enabled": True},
        headers={'Authorization': f"Bearer {seed['manager_token']}", 'Idempotency-Key': 'set-1'},
    )
    assert set_res.status_code == 200

    start_round = client.post(
        f"/events/{seed['event_id']}/music/admin/round/start",
        json={'durationSec': 120},
        headers={'Authorization': f"Bearer {seed['manager_token']}", 'Idempotency-Key': 'round-1'},
    )
    assert start_round.status_code == 200

    body = {'candidate': _candidate('Song A')}
    r1 = client.post(
        f"/events/{seed['event_id']}/music/vote",
        json=body,
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'vote-1'},
    )
    assert r1.status_code == 200
    r2 = client.post(
        f"/events/{seed['event_id']}/music/vote",
        json=body,
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'vote-1'},
    )
    assert r2.status_code == 200

    r3 = client.post(
        f"/events/{seed['event_id']}/music/vote",
        json={'candidate': _candidate('Song B')},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'vote-2'},
    )
    assert r3.status_code == 429
    assert r3.json()['detail']['reason'] == 'vote_cooldown'


def test_settings_requires_manager():
    seed = _seed(module_on=True)
    client = TestClient(app)
    denied = client.post(
        f"/events/{seed['event_id']}/music/admin/settings",
        json={"enabled": True},
        headers={'Authorization': f"Bearer {seed['staff_token']}", 'Idempotency-Key': 'set-denied'},
    )
    assert denied.status_code == 403


def test_force_allowed_for_dj_only_when_override_enabled():
    seed = _seed(module_on=True)
    client = TestClient(app)
    dj_token, dj_user_id = _guest_token(client, 'dj-user')

    denied = client.post(
        f"/events/{seed['event_id']}/music/admin/force",
        json={'candidate': _candidate('DJ Song'), 'reason': 'test'},
        headers={'Authorization': f'Bearer {dj_token}', 'Idempotency-Key': 'force-1'},
    )
    assert denied.status_code == 403

    set_override = client.post(
        f"/events/{seed['event_id']}/music/admin/settings",
        json={"enabled": True, "djOverrideEnabled": True},
        headers={'Authorization': f"Bearer {seed['manager_token']}", 'Idempotency-Key': 'set-ovr'},
    )
    assert set_override.status_code == 200

    s = get_session()
    try:
        s.add(EventStaff(event_id=seed['event_id'], user_id=dj_user_id, role='dj', is_active=True))
        s.commit()
    finally:
        s.close()

    allowed = client.post(
        f"/events/{seed['event_id']}/music/admin/force",
        json={'candidate': _candidate('DJ Song'), 'reason': 'test'},
        headers={'Authorization': f'Bearer {dj_token}', 'Idempotency-Key': 'force-2'},
    )
    assert allowed.status_code == 200


def test_runtime_blocked_states_return_403():
    seed = _seed(module_on=True)
    client = TestClient(app)
    token, _ = _guest_token(client, 'runtime-user')

    client.post(
        f"/events/{seed['event_id']}/music/admin/settings",
        json={"enabled": True},
        headers={'Authorization': f"Bearer {seed['manager_token']}", 'Idempotency-Key': 'set-run'},
    )

    start_round = client.post(
        f"/events/{seed['event_id']}/music/admin/round/start",
        json={'durationSec': 120},
        headers={'Authorization': f"Bearer {seed['manager_token']}", 'Idempotency-Key': 'round-run'},
    )
    assert start_round.status_code == 200

    s = get_session()
    try:
        s.add(EventRuntimeState(event_id=seed['event_id'], state='PAUSE'))
        s.commit()
    finally:
        s.close()

    blocked = client.post(
        f"/events/{seed['event_id']}/music/vote",
        json={'candidate': _candidate('Blocked')},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'vote-run'},
    )
    assert blocked.status_code == 403
    assert blocked.json()['detail']['reason'] == 'runtime_blocked'


def test_candidate_add_normalizes_and_deduplicates_youtube_music_link():
    seed = _seed(module_on=True)
    client = TestClient(app)
    token, _ = _guest_token(client, 'candidate-user')

    client.post(
        f"/events/{seed['event_id']}/music/admin/settings",
        json={"enabled": True},
        headers={'Authorization': f"Bearer {seed['manager_token']}", 'Idempotency-Key': 'set-cand'},
    )
    client.post(
        f"/events/{seed['event_id']}/music/admin/round/start",
        json={'durationSec': 120},
        headers={'Authorization': f"Bearer {seed['manager_token']}", 'Idempotency-Key': 'round-cand'},
    )

    payload = {
        'provider': 'youtube_music',
        'externalUrl': 'https://music.youtube.com/watch?v=abc123',
        'titleHint': 'Ma track',
    }
    added = client.post(
        f"/events/{seed['event_id']}/music/candidates",
        json=payload,
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'cand-1'},
    )
    assert added.status_code == 200
    assert added.json()['status'] == 'added'

    dup = client.post(
        f"/events/{seed['event_id']}/music/candidates",
        json=payload,
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'cand-2'},
    )
    assert dup.status_code == 200
    assert dup.json()['status'] == 'already_exists'

    s = get_session()
    try:
        rows = s.query(EventMusicCandidate).filter(EventMusicCandidate.event_id == seed['event_id']).all()
        assert len(rows) == 1
        assert rows[0].provider == 'youtube_music'
        assert rows[0].url_normalized == 'https://music.youtube.com/watch?v=abc123'
        assert rows[0].external_id == 'abc123'
    finally:
        s.close()


def test_candidate_add_validates_links_for_soundcloud_and_youtube_music_intent():
    seed = _seed(module_on=True)
    client = TestClient(app)
    token, _ = _guest_token(client, 'candidate-invalid')
    client.post(
        f"/events/{seed['event_id']}/music/admin/settings",
        json={"enabled": True},
        headers={'Authorization': f"Bearer {seed['manager_token']}", 'Idempotency-Key': 'set-invalid'},
    )
    client.post(
        f"/events/{seed['event_id']}/music/admin/round/start",
        json={'durationSec': 120},
        headers={'Authorization': f"Bearer {seed['manager_token']}", 'Idempotency-Key': 'round-invalid'},
    )

    invalid_sc = client.post(
        f"/events/{seed['event_id']}/music/candidates",
        json={'provider': 'soundcloud', 'externalUrl': 'https://soundcloud.com/discover'},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'cand-sc'},
    )
    assert invalid_sc.status_code == 400
    assert invalid_sc.json()['detail']['reason'] == 'LINK_NOT_SUPPORTED'

    invalid_yt = client.post(
        f"/events/{seed['event_id']}/music/candidates",
        json={'provider': 'youtube_music', 'externalUrl': 'https://youtube.com/channel/abc'},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'cand-yt'},
    )
    assert invalid_yt.status_code == 400
    assert invalid_yt.json()['detail']['reason'] == 'LINK_NOT_SUPPORTED'


def test_candidate_add_writes_audit_log():
    seed = _seed(module_on=True)
    client = TestClient(app)
    token, _ = _guest_token(client, 'candidate-audit')
    client.post(
        f"/events/{seed['event_id']}/music/admin/settings",
        json={"enabled": True},
        headers={'Authorization': f"Bearer {seed['manager_token']}", 'Idempotency-Key': 'set-audit'},
    )
    client.post(
        f"/events/{seed['event_id']}/music/admin/round/start",
        json={'durationSec': 120},
        headers={'Authorization': f"Bearer {seed['manager_token']}", 'Idempotency-Key': 'round-audit'},
    )

    res = client.post(
        f"/events/{seed['event_id']}/music/candidates",
        json={'provider': 'soundcloud', 'externalUrl': 'https://soundcloud.com/artist/track'},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'cand-audit'},
    )
    assert res.status_code == 200

    s = get_session()
    try:
        row = s.query(AuditLog).filter(AuditLog.action == 'music_vote.candidate_added', AuditLog.event_id == seed['event_id']).first()
        assert row is not None
    finally:
        s.close()

def test_pre_event_suggest_and_vote_with_cooldown_and_idempotency():
    seed = _seed(module_on=True)
    client = TestClient(app)
    token, _ = _guest_token(client, 'pre-user')

    suggest = client.post(
        f"/events/{seed['event_id']}/music/pre_event/suggest",
        json={'provider': 'spotify', 'externalUrl': 'https://open.spotify.com/track/pre1', 'title': 'Pre1', 'artist': 'Artist'},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'pre-s-1'},
    )
    assert suggest.status_code == 200
    same = client.post(
        f"/events/{seed['event_id']}/music/pre_event/suggest",
        json={'provider': 'spotify', 'externalUrl': 'https://open.spotify.com/track/pre1', 'title': 'Pre1', 'artist': 'Artist'},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'pre-s-1'},
    )
    assert same.status_code == 200

    blocked = client.post(
        f"/events/{seed['event_id']}/music/pre_event/suggest",
        json={'provider': 'spotify', 'externalUrl': 'https://open.spotify.com/track/pre2', 'title': 'Pre2', 'artist': 'Artist'},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'pre-s-2'},
    )
    assert blocked.status_code == 429

    vote = client.post(
        f"/events/{seed['event_id']}/music/pre_event/vote",
        json={'suggestionId': suggest.json()['suggestionId']},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'pre-v-1'},
    )
    assert vote.status_code == 200


def test_new_rounds_lifecycle_and_permissions():
    seed = _seed(module_on=True)
    client = TestClient(app)
    dj_token, dj_user_id = _guest_token(client, 'dj-round')

    denied = client.post(
        f"/events/{seed['event_id']}/music/rounds/start",
        json={'durationSec': 120},
        headers={'Authorization': f'Bearer {seed["staff_token"]}', 'Idempotency-Key': 'rd-deny'},
    )
    assert denied.status_code == 403

    client.post(
        f"/events/{seed['event_id']}/music/admin/settings",
        json={"enabled": True, "djOverrideEnabled": True},
        headers={'Authorization': f"Bearer {seed['manager_token']}", 'Idempotency-Key': 'set-rnd'},
    )
    s = get_session()
    try:
        s.add(EventStaff(event_id=seed['event_id'], user_id=dj_user_id, role='dj', is_active=True))
        s.commit()
    finally:
        s.close()

    started = client.post(
        f"/events/{seed['event_id']}/music/rounds/start",
        json={'durationSec': 120},
        headers={'Authorization': f'Bearer {dj_token}', 'Idempotency-Key': 'rd-start'},
    )
    assert started.status_code == 200

    current = client.get(f"/events/{seed['event_id']}/music/rounds/current")
    assert current.status_code == 200
    assert current.json()['round']['status'] == 'OPEN'

    closed = client.post(
        f"/events/{seed['event_id']}/music/rounds/close",
        headers={'Authorization': f"Bearer {seed['manager_token']}", 'Idempotency-Key': 'rd-close'},
    )
    assert closed.status_code == 200
    assert closed.json()['round']['status'] == 'LOCKED'
