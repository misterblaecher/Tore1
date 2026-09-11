from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from db import Base, engine, now_utc
from main import app
from models import Organization, OrganizationMembership
from app.forum_models import StructureGovernance, StructureRole, StructureRoleAssignment


client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _guest(name: str) -> tuple[str, str]:
    res = client.post('/auth/guest', json={'display_name': name})
    assert res.status_code == 200
    token = res.json()['token']
    me = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.status_code == 200
    return token, me.json()['id']


def _h(token: str, idem: str | None = None) -> dict[str, str]:
    result = {'Authorization': f'Bearer {token}'}
    if idem:
        result['Idempotency-Key'] = idem
    return result


def _create_structure(token: str, name: str) -> dict:
    res = client.post('/forum/v2/structures', json={'name': name, 'org_type': 'COMMITTEE'}, headers=_h(token))
    assert res.status_code == 201, res.text
    return res.json()


def _join_legacy(org_id: int, token: str, key: str) -> None:
    res = client.post(f'/orgas/{org_id}/join', headers=_h(token, key))
    assert res.status_code == 200, res.text


def _member_id(org_id: int, user_id: str) -> int:
    with Session(engine) as db:
        return db.query(OrganizationMembership).filter_by(organization_id=org_id, user_id=user_id).one().id


def _role_id(slug: str, token: str, name: str) -> int:
    rows = client.get(f'/forum/v2/structures/{slug}/roles', headers=_h(token))
    assert rows.status_code == 200
    return next(row['id'] for row in rows.json() if row['name'] == name)


def test_public_page_is_draft_until_explicit_publish():
    owner, _ = _guest('backend-owner')
    structure = _create_structure(owner, 'Backend Structure')
    slug = structure['slug']
    assert structure['public_page_status'] == 'DRAFT'
    assert client.get(f'/forum/v2/public/structures/{slug}').status_code == 404

    published = client.patch(
        f'/forum/v2/structures/{slug}/public-page',
        json={'status': 'PUBLISHED'},
        headers=_h(owner),
    )
    assert published.status_code == 200
    public = client.get(f'/forum/v2/public/structures/{slug}')
    assert public.status_code == 200
    assert public.json()['slug'] == slug
    assert 'owner_user_id' not in public.json()


def test_cross_tenant_private_access_is_denied():
    owner_a, _ = _guest('tenant-a')
    owner_b, _ = _guest('tenant-b')
    a = _create_structure(owner_a, 'Tenant A')
    b = _create_structure(owner_b, 'Tenant B')

    assert client.get(f"/forum/v2/structures/{b['slug']}/roles", headers=_h(owner_a)).status_code == 403
    assert client.patch(
        f"/forum/v2/structures/{b['slug']}",
        json={'name': 'Cross tenant mutation'},
        headers=_h(owner_a),
    ).status_code == 403
    assert client.get(f"/forum/v2/structures/{a['slug']}/context", headers=_h(owner_a)).status_code == 200


def test_permission_grant_ceiling_and_nondelegable_permissions():
    owner, _ = _guest('ceiling-owner')
    manager, manager_id = _guest('ceiling-manager')
    structure = _create_structure(owner, 'Ceiling Org')
    slug, org_id = structure['slug'], structure['id']
    _join_legacy(org_id, manager, 'join-ceiling-manager')

    role = client.post(
        f'/forum/v2/structures/{slug}/roles',
        json={'name': 'Role manager', 'audience_level': 'BUREAU', 'permissions': ['structure.read', 'members.view', 'members.manage', 'roles.manage']},
        headers=_h(owner),
    )
    assert role.status_code == 201, role.text
    assign = client.patch(
        f'/forum/v2/structures/{slug}/members/{_member_id(org_id, manager_id)}',
        json={'role_id': role.json()['id']},
        headers=_h(owner),
    )
    assert assign.status_code == 200, assign.text

    higher = client.post(
        f'/forum/v2/structures/{slug}/roles',
        json={'name': 'Illegal higher', 'permissions': ['accounting.view']},
        headers=_h(manager),
    )
    assert higher.status_code == 403

    system = client.post(
        f'/forum/v2/structures/{slug}/roles',
        json={'name': 'Illegal system', 'permissions': ['structure.admin']},
        headers=_h(owner),
    )
    assert system.status_code == 403


def test_only_current_owner_can_transfer_ownership():
    owner, owner_id = _guest('transfer-owner')
    member, member_id = _guest('transfer-member')
    structure = _create_structure(owner, 'Transfer Org')
    slug, org_id = structure['slug'], structure['id']
    _join_legacy(org_id, member, 'join-transfer-member')

    denied = client.post(
        f'/forum/v2/structures/{slug}/ownership/transfer',
        json={'new_owner_user_id': owner_id},
        headers=_h(member, 'transfer-denied'),
    )
    assert denied.status_code == 403

    moved = client.post(
        f'/forum/v2/structures/{slug}/ownership/transfer',
        json={'new_owner_user_id': member_id},
        headers=_h(owner, 'transfer-ok'),
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()['ownerUserId'] == member_id
    with Session(engine) as db:
        assert db.get(StructureGovernance, org_id).owner_user_id == member_id
        owner_role = db.query(StructureRole).filter_by(organization_id=org_id, name='Owner').one()
        active_owner_assignments = db.query(StructureRoleAssignment).join(
            OrganizationMembership, OrganizationMembership.id == StructureRoleAssignment.membership_id
        ).filter(
            StructureRoleAssignment.organization_id == org_id,
            StructureRoleAssignment.role_id == owner_role.id,
            OrganizationMembership.status == 'ACTIVE',
            OrganizationMembership.revoked_at.is_(None),
        ).all()
        assert len(active_owner_assignments) == 1


def test_operational_stats_never_leak_accounting():
    owner, _ = _guest('stats-owner')
    staff, staff_id = _guest('stats-staff')
    structure = _create_structure(owner, 'Stats Org')
    slug, org_id = structure['slug'], structure['id']
    _join_legacy(org_id, staff, 'join-stats-staff')

    role = client.post(
        f'/forum/v2/structures/{slug}/roles',
        json={'name': 'Stats only', 'audience_level': 'STAFF', 'permissions': ['structure.read', 'events.view', 'stats.view']},
        headers=_h(owner),
    )
    assert role.status_code == 201
    assert client.patch(
        f'/forum/v2/structures/{slug}/members/{_member_id(org_id, staff_id)}',
        json={'role_id': role.json()['id']}, headers=_h(owner)
    ).status_code == 200

    event = client.post(
        f'/forum/v2/structures/{slug}/events',
        json={'name': 'Stats Event', 'starts_at': '2030-01-01T18:00:00Z', 'ends_at': '2030-01-01T22:00:00Z'},
        headers=_h(owner),
    )
    assert event.status_code == 201, event.text
    accounting = client.post(
        f'/forum/v2/structures/{slug}/accounting',
        json={'event_id': event.json()['id'], 'entry_type': 'INCOME', 'category': 'bar', 'label': 'Secret revenue', 'amount_cents': 342000},
        headers=_h(owner),
    )
    assert accounting.status_code == 201

    stats = client.get(f'/forum/v2/structures/{slug}/stats?event_id={event.json()["id"]}', headers=_h(staff))
    assert stats.status_code == 200, stats.text
    body = stats.json()
    assert not ({'revenue', 'cost', 'profit', 'margin', 'incomeCents', 'expenseCents', 'resultCents'} & set(body))
    assert client.get(f'/forum/v2/structures/{slug}/accounting', headers=_h(staff)).status_code == 403


def test_channel_and_document_visibility_block_direct_ids_and_search():
    owner, _ = _guest('privacy-owner')
    member, member_id = _guest('privacy-member')
    structure = _create_structure(owner, 'Privacy Org')
    slug, org_id = structure['slug'], structure['id']
    _join_legacy(org_id, member, 'join-privacy-member')

    # Explicitly normalize legacy MEMBER into the new server role assignment.
    client.get(f'/forum/v2/structures/{slug}/context', headers=_h(member))

    channel = client.post(
        f'/forum/v2/structures/{slug}/channels',
        json={'name': 'Tresorerie', 'visibility': 'TREASURY'}, headers=_h(owner)
    )
    assert channel.status_code == 201, channel.text
    channel_id = channel.json()['id']
    assert all(row['id'] != channel_id for row in client.get(f'/forum/v2/structures/{slug}/channels', headers=_h(member)).json()['items'])
    assert client.get(f'/forum/v2/structures/{slug}/channels/{channel_id}/messages', headers=_h(member)).status_code == 404
    assert client.post(f'/forum/v2/structures/{slug}/channels/{channel_id}/messages', json={'body': 'forged'}, headers=_h(member)).status_code == 404

    doc = client.post(
        f'/forum/v2/structures/{slug}/documents',
        json={'title': 'budget-secret-xyz', 'visibility': 'TREASURY'}, headers=_h(owner)
    )
    assert doc.status_code == 201, doc.text
    doc_id = doc.json()['id']
    uploaded = client.post(
        f'/forum/v2/structures/{slug}/documents/{doc_id}/versions',
        files={'file': ('budget.txt', b'budget-secret-xyz', 'text/plain')}, headers=_h(owner)
    )
    assert uploaded.status_code == 201, uploaded.text
    assert all(row['id'] != doc_id for row in client.get(f'/forum/v2/structures/{slug}/documents', headers=_h(member)).json()['items'])
    assert client.get(f'/forum/v2/structures/{slug}/documents/{doc_id}/download', headers=_h(member)).status_code == 404
    search = client.get(f'/forum/v2/structures/{slug}/search?q=budget-secret-xyz', headers=_h(member))
    assert search.status_code == 200
    assert search.json()['items'] == []


def test_accounting_lock_is_enforced_server_side():
    owner, _ = _guest('lock-owner')
    structure = _create_structure(owner, 'Lock Org')
    slug = structure['slug']
    entry = client.post(
        f'/forum/v2/structures/{slug}/accounting',
        json={'entry_type': 'EXPENSE', 'category': 'supplier', 'label': 'Invoice', 'amount_cents': 1200},
        headers=_h(owner),
    )
    assert entry.status_code == 201
    entry_id = entry.json()['id']
    locked = client.post(f'/forum/v2/structures/{slug}/accounting/{entry_id}/lock', headers=_h(owner, 'lock-1'))
    assert locked.status_code == 200
    assert locked.json()['status'] == 'LOCKED'
    assert client.patch(f'/forum/v2/structures/{slug}/accounting/{entry_id}', json={'amount_cents': 9999}, headers=_h(owner)).status_code == 409
    assert client.delete(f'/forum/v2/structures/{slug}/accounting/{entry_id}', headers=_h(owner)).status_code == 409


def test_claim_does_not_mutate_structure_before_review():
    owner, owner_id = _guest('claim-owner')
    claimant, claimant_id = _guest('claim-user')
    structure = _create_structure(owner, 'Claim Org')
    slug, org_id = structure['slug'], structure['id']
    before = client.get(f'/forum/v2/structures/{slug}/context', headers=_h(owner)).json()['structure']
    claim = client.post(f'/forum/v2/public/structures/{slug}/claims', json={'reason': 'Official handover request'}, headers=_h(claimant))
    assert claim.status_code == 201
    after = client.get(f'/forum/v2/structures/{slug}/context', headers=_h(owner)).json()['structure']
    assert after['status'] == before['status']
    assert after['owner_user_id'] == owner_id
    with Session(engine) as db:
        assert db.get(StructureGovernance, org_id).owner_user_id != claimant_id


def test_openapi_declares_typed_forum_models_and_statuses():
    schema = client.get('/openapi.json')
    assert schema.status_code == 200
    paths = schema.json()['paths']
    assert '/forum/v2/structures/{slug}/roles' in paths
    assert '/forum/v2/structures/{slug}/documents/{document_id}/versions' in paths
    assert '/forum/v2/public/structures/{slug}' in paths
    message = paths['/forum/v2/structures/{slug}/channels/{channel_id}/messages']['post']
    body_schema = message['requestBody']['content']['application/json']['schema']
    assert body_schema.get('$ref', '').endswith('/MessageCreateIn')
