from __future__ import annotations

import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import AuditLog, Committee, CommitteeMembership, CommitteeYear


def _auth_guest(client: TestClient, name: str) -> tuple[str, str]:
    Base.metadata.create_all(engine)
    token = client.post('/auth/guest', json={'display_name': name}).json()['token']
    me = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'}).json()
    return token, me['id']


def _seed_committee(owner_user_id: str) -> tuple[int, int]:
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(3)
        committee = Committee(name=f'Glossary {suffix}', slug=f'glossary-{suffix}', description_public='Glossary test')
        s.add(committee)
        s.flush()
        year = CommitteeYear(committee_id=committee.id, year_label='2025-2026', is_active=True)
        s.add_all([
            year,
            CommitteeMembership(committee_id=committee.id, user_id=owner_user_id, role='OWNER', is_active=True),
        ])
        s.commit()
        return committee.id, year.id
    finally:
        s.close()


def test_module_off_strict(monkeypatch):
    monkeypatch.setenv('TORE_MODULE_FOLKLORE_GLOSSARY', '0')
    client = TestClient(app)
    res = client.get('/glossary/committees')
    assert res.status_code == 404
    assert res.json()['detail']['reason'] == 'MODULE_OFF'


def test_public_disabled_blocks_public_endpoints():
    client = TestClient(app)
    owner_token, owner_id = _auth_guest(client, 'owner-public-disabled')
    committee_id, _ = _seed_committee(owner_id)

    list_res = client.get('/glossary/committees')
    assert list_res.status_code == 200
    assert all(item['id'] != committee_id for item in list_res.json())

    terms = client.get(f'/glossary/committees/{committee_id}/terms')
    assert terms.status_code == 404

    settings = client.get(f'/glossary/committees/{committee_id}/settings')
    assert settings.status_code == 404

    enable = client.put(
        f'/committees/{committee_id}/glossary/settings',
        json={'public_enabled': True},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'glossary-settings-enable-1'},
    )
    assert enable.status_code == 200

    terms_after = client.get(f'/glossary/committees/{committee_id}/terms')
    assert terms_after.status_code == 200


def test_create_term_idempotent_and_audit_present():
    client = TestClient(app)
    owner_token, owner_id = _auth_guest(client, 'owner-idem')
    committee_id, year_id = _seed_committee(owner_id)

    headers = {'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'glossary-create-idem-1'}
    payload = {
        'term': 'Guindaille',
        'definition': 'Fête étudiante liégeoise.',
        'examples': 'On va en guindaille ce soir.',
        'tags': ['Guindaille', 'Chants'],
        'yearId': year_id,
        'isOfficial': True,
    }
    c1 = client.post(f'/committees/{committee_id}/glossary/terms', json=payload, headers=headers)
    c2 = client.post(f'/committees/{committee_id}/glossary/terms', json=payload, headers=headers)
    assert c1.status_code == 200
    assert c2.status_code == 200
    assert c1.json()['id'] == c2.json()['id']

    s = get_session()
    try:
        audit = s.query(AuditLog).filter(AuditLog.action == 'committee.glossary.term.create', AuditLog.entity_id == str(c1.json()['id'])).first()
        assert audit is not None
    finally:
        s.close()


def test_edit_delete_requires_mod_or_admin():
    client = TestClient(app)
    owner_token, owner_id = _auth_guest(client, 'owner-role')
    committee_id, _ = _seed_committee(owner_id)
    member_token, member_id = _auth_guest(client, 'member-role')
    mod_token, mod_id = _auth_guest(client, 'mod-role')

    s = get_session()
    try:
        s.add_all([
            CommitteeMembership(committee_id=committee_id, user_id=member_id, role='MEMBER', is_active=True),
            CommitteeMembership(committee_id=committee_id, user_id=mod_id, role='MOD', is_active=True),
        ])
        s.commit()
    finally:
        s.close()

    created = client.post(
        f'/committees/{committee_id}/glossary/terms',
        json={'term': 'Baptême', 'definition': 'Rituel étudiant'},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'g-role-create-1'},
    )
    assert created.status_code == 200
    term_id = created.json()['id']

    denied = client.put(
        f'/committees/{committee_id}/glossary/terms/{term_id}',
        json={'definition': 'Nouveau'},
        headers={'Authorization': f'Bearer {member_token}', 'Idempotency-Key': 'g-role-update-denied-1'},
    )
    assert denied.status_code == 403

    mod_ok = client.put(
        f'/committees/{committee_id}/glossary/terms/{term_id}',
        json={'definition': 'Nouveau sens', 'tags': ['Baptême']},
        headers={'Authorization': f'Bearer {mod_token}', 'Idempotency-Key': 'g-role-update-ok-1'},
    )
    assert mod_ok.status_code == 200

    mod_delete = client.post(
        f'/committees/{committee_id}/glossary/terms/{term_id}/delete',
        json={'reason': 'soft delete test'},
        headers={'Authorization': f'Bearer {mod_token}', 'Idempotency-Key': 'g-role-del-ok-1'},
    )
    assert mod_delete.status_code == 200


def test_list_filters_query_tags_year():
    client = TestClient(app)
    owner_token, owner_id = _auth_guest(client, 'owner-filters')
    committee_id, year_id = _seed_committee(owner_id)

    s = get_session()
    try:
        year2 = CommitteeYear(committee_id=committee_id, year_label='2024-2025', is_active=False)
        s.add(year2)
        s.commit()
        year2_id = year2.id
    finally:
        s.close()

    client.post(
        f'/committees/{committee_id}/glossary/terms',
        json={'term': 'Guindaille', 'definition': 'Fête', 'tags': ['Guindaille'], 'yearId': year_id},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'g-filter-1'},
    )
    client.post(
        f'/committees/{committee_id}/glossary/terms',
        json={'term': 'Chanson', 'definition': 'Chant de guindaille', 'tags': ['Chants'], 'yearId': year2_id},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'g-filter-2'},
    )

    by_query = client.get(
        f'/committees/{committee_id}/glossary/terms',
        params={'query': 'fête'},
        headers={'Authorization': f'Bearer {owner_token}'},
    )
    assert by_query.status_code == 200
    assert len(by_query.json()['items']) == 1

    by_tag = client.get(
        f'/committees/{committee_id}/glossary/terms',
        params={'tags': 'chants'},
        headers={'Authorization': f'Bearer {owner_token}'},
    )
    assert by_tag.status_code == 200
    assert len(by_tag.json()['items']) == 1
    assert by_tag.json()['items'][0]['term'] == 'Chanson'

    by_year = client.get(
        f'/committees/{committee_id}/glossary/terms',
        params={'year': year_id},
        headers={'Authorization': f'Bearer {owner_token}'},
    )
    assert by_year.status_code == 200
    assert len(by_year.json()['items']) == 1
    assert by_year.json()['items'][0]['term'] == 'Guindaille'


def test_rate_limit_triggered_on_writes():
    client = TestClient(app)
    owner_token, owner_id = _auth_guest(client, 'owner-rate-limit')
    committee_id, _ = _seed_committee(owner_id)

    for i in range(10):
        ok = client.post(
            f'/committees/{committee_id}/glossary/terms',
            json={'term': f'Term {i}', 'definition': 'abc'},
            headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': f'g-rate-{i}'},
        )
        assert ok.status_code == 200

    limited = client.post(
        f'/committees/{committee_id}/glossary/terms',
        json={'term': 'Term overflow', 'definition': 'abc'},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'g-rate-11'},
    )
    assert limited.status_code == 429
