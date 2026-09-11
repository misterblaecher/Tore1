from __future__ import annotations

from urllib.parse import quote

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from db import Base, engine, now_utc
from main import app
from models import (
    AuditLog,
    Event,
    OrganizationMembership,
    OrgaPost,
    StructureDiscussionPost,
    StructureDocument,
)
from app.forum_models import (
    AccountingEntry,
    OrgaPostPublication,
    StructureAuditContext,
    StructureDocumentVersion,
    StructureGovernance,
    StructurePublicPage,
    StructureRole,
    StructureRoleAssignment,
)


client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _guest(name: str) -> tuple[str, str]:
    response = client.post('/auth/guest', json={'display_name': name})
    assert response.status_code == 200, response.text
    token = response.json()['token']
    me = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.status_code == 200, me.text
    return token, me.json()['id']


def _h(token: str, idem: str | None = None) -> dict[str, str]:
    headers = {'Authorization': f'Bearer {token}'}
    if idem:
        headers['Idempotency-Key'] = idem
    return headers


def _create_structure(token: str, name: str) -> dict:
    response = client.post(
        '/forum/v2/structures',
        json={'name': name, 'org_type': 'COMMITTEE'},
        headers=_h(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _join_legacy(org_id: int, token: str, key: str) -> None:
    response = client.post(f'/orgas/{org_id}/join', headers=_h(token, key))
    assert response.status_code == 200, response.text


def _member_id(org_id: int, user_id: str) -> int:
    with Session(engine) as db:
        return db.query(OrganizationMembership).filter_by(
            organization_id=org_id,
            user_id=user_id,
        ).one().id


def _assign_custom_role(owner_token: str, member_token: str, member_id: int, slug: str, permissions: list[str], name: str = 'Delegated manager') -> int:
    role = client.post(
        f'/forum/v2/structures/{slug}/roles',
        json={'name': name, 'audience_level': 'BUREAU', 'permissions': permissions},
        headers=_h(owner_token),
    )
    assert role.status_code == 201, role.text
    assigned = client.patch(
        f'/forum/v2/structures/{slug}/members/{member_id}',
        json={'role_id': role.json()['id']},
        headers=_h(owner_token),
    )
    assert assigned.status_code == 200, assigned.text
    context = client.get(f'/forum/v2/structures/{slug}/context', headers=_h(member_token))
    assert context.status_code == 200, context.text
    return role.json()['id']


def _role_manager_fixture(prefix: str) -> tuple[str, str, str, int, int]:
    owner, _ = _guest(f'{prefix}-owner')
    manager, manager_id = _guest(f'{prefix}-manager')
    structure = _create_structure(owner, f'{prefix} Structure')
    _join_legacy(structure['id'], manager, f'join-{prefix}')
    member_id = _member_id(structure['id'], manager_id)
    _assign_custom_role(
        owner,
        manager,
        member_id,
        structure['slug'],
        ['structure.read', 'members.view', 'members.manage', 'roles.manage'],
    )
    return owner, manager, structure['slug'], structure['id'], member_id


def test_roles_manager_cannot_delegate_structure_admin():
    _, manager, slug, _, _ = _role_manager_fixture('grant-admin')
    response = client.post(
        f'/forum/v2/structures/{slug}/roles',
        json={'name': 'Forbidden admin', 'permissions': ['structure.admin']},
        headers=_h(manager),
    )
    assert response.status_code == 403
    assert response.json()['detail']['reason'] == 'NON_DELEGABLE_PERMISSION'


def test_roles_manager_cannot_delegate_ownership_transfer():
    _, manager, slug, _, _ = _role_manager_fixture('grant-owner-transfer')
    response = client.post(
        f'/forum/v2/structures/{slug}/roles',
        json={'name': 'Forbidden ownership', 'permissions': ['ownership.transfer']},
        headers=_h(manager),
    )
    assert response.status_code == 403
    assert response.json()['detail']['reason'] == 'NON_DELEGABLE_PERMISSION'


def test_roles_manager_cannot_delegate_accounting_unlock():
    _, manager, slug, _, _ = _role_manager_fixture('grant-accounting-unlock')
    response = client.post(
        f'/forum/v2/structures/{slug}/roles',
        json={'name': 'Forbidden unlock', 'permissions': ['accounting.unlock']},
        headers=_h(manager),
    )
    assert response.status_code == 403
    assert response.json()['detail']['reason'] == 'NON_DELEGABLE_PERMISSION'


def test_contaminated_legacy_role_cannot_propagate_ownership_transfer():
    owner, manager, slug, org_id, member_id = _role_manager_fixture('legacy-contaminated')
    with Session(engine) as db:
        role = StructureRole(
            organization_id=org_id,
            name='Legacy contaminated',
            system_role=False,
            audience_level='BUREAU',
            permissions_json=['structure.read', 'members.view', 'members.manage', 'roles.manage', 'ownership.transfer'],
            created_by_user_id=None,
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        db.add(role)
        db.flush()
        assignment = db.query(StructureRoleAssignment).filter_by(membership_id=member_id).one()
        assignment.role_id = role.id
        assignment.updated_at = now_utc()
        db.commit()

    context = client.get(f'/forum/v2/structures/{slug}/context', headers=_h(manager))
    assert context.status_code == 200
    assert 'ownership.transfer' in context.json()['permissions']
    response = client.post(
        f'/forum/v2/structures/{slug}/roles',
        json={'name': 'Copied legacy power', 'permissions': ['ownership.transfer']},
        headers=_h(manager),
    )
    assert response.status_code == 403
    assert response.json()['detail']['reason'] == 'NON_DELEGABLE_PERMISSION'

    # Possessing contaminated historical data still does not make the actor the owner.
    target, target_id = _guest('legacy-contaminated-target')
    _join_legacy(org_id, target, 'legacy-contaminated-target-join')
    transfer = client.post(
        f'/forum/v2/structures/{slug}/ownership/transfer',
        json={'new_owner_user_id': target_id},
        headers=_h(manager, 'legacy-contaminated-transfer'),
    )
    assert transfer.status_code == 403
    assert transfer.json()['detail']['reason'] == 'CURRENT_OWNER_REQUIRED'


def test_non_owner_cannot_transfer_ownership():
    owner, _ = _guest('transfer-denied-owner')
    member, member_id = _guest('transfer-denied-member')
    structure = _create_structure(owner, 'Transfer Denied Org')
    _join_legacy(structure['id'], member, 'transfer-denied-join')
    response = client.post(
        f"/forum/v2/structures/{structure['slug']}/ownership/transfer",
        json={'new_owner_user_id': member_id},
        headers=_h(member, 'transfer-denied'),
    )
    assert response.status_code == 403


def test_owner_transfer_to_active_member_is_atomic_and_audited():
    owner, owner_id = _guest('transfer-success-owner')
    target, target_id = _guest('transfer-success-target')
    structure = _create_structure(owner, 'Transfer Success Org')
    slug, org_id = structure['slug'], structure['id']
    _join_legacy(org_id, target, 'transfer-success-join')

    response = client.post(
        f'/forum/v2/structures/{slug}/ownership/transfer',
        json={'new_owner_user_id': target_id},
        headers=_h(owner, 'transfer-success'),
    )
    assert response.status_code == 200, response.text
    assert response.json()['ownerUserId'] == target_id

    with Session(engine) as db:
        governance = db.get(StructureGovernance, org_id)
        assert governance.owner_user_id == target_id
        owner_role = db.query(StructureRole).filter_by(
            organization_id=org_id, name='Owner', system_role=True
        ).one()
        bureau_role = db.query(StructureRole).filter_by(
            organization_id=org_id, name='Bureau', system_role=True
        ).one()
        assignments = db.query(StructureRoleAssignment, OrganizationMembership).join(
            OrganizationMembership,
            OrganizationMembership.id == StructureRoleAssignment.membership_id,
        ).filter(
            StructureRoleAssignment.organization_id == org_id,
            OrganizationMembership.status == 'ACTIVE',
            OrganizationMembership.revoked_at.is_(None),
        ).all()
        active_owner_assignments = [pair for pair in assignments if pair[0].role_id == owner_role.id]
        assert len(active_owner_assignments) == 1
        assert active_owner_assignments[0][1].user_id == target_id
        old_owner_assignment = next(pair[0] for pair in assignments if pair[1].user_id == owner_id)
        assert old_owner_assignment.role_id == bureau_role.id
        audit = db.query(AuditLog).join(
            StructureAuditContext,
            StructureAuditContext.audit_log_id == AuditLog.id,
        ).filter(
            StructureAuditContext.organization_id == org_id,
            AuditLog.action == 'forum.ownership.transfer',
        ).one_or_none()
        assert audit is not None


def test_owner_transfer_rejects_non_member_without_mutation():
    owner, owner_id = _guest('transfer-nonmember-owner')
    _, outsider_id = _guest('transfer-nonmember-outsider')
    structure = _create_structure(owner, 'Transfer Nonmember Org')
    response = client.post(
        f"/forum/v2/structures/{structure['slug']}/ownership/transfer",
        json={'new_owner_user_id': outsider_id},
        headers=_h(owner, 'transfer-nonmember'),
    )
    assert response.status_code == 409
    with Session(engine) as db:
        assert db.get(StructureGovernance, structure['id']).owner_user_id == owner_id


def test_owner_transfer_rejects_revoked_member_without_mutation():
    owner, owner_id = _guest('transfer-revoked-owner')
    target, target_id = _guest('transfer-revoked-target')
    structure = _create_structure(owner, 'Transfer Revoked Org')
    _join_legacy(structure['id'], target, 'transfer-revoked-join')
    with Session(engine) as db:
        membership = db.query(OrganizationMembership).filter_by(
            organization_id=structure['id'], user_id=target_id
        ).one()
        membership.status = 'REVOKED'
        membership.revoked_at = now_utc()
        membership.ends_at = now_utc()
        db.commit()
    response = client.post(
        f"/forum/v2/structures/{structure['slug']}/ownership/transfer",
        json={'new_owner_user_id': target_id},
        headers=_h(owner, 'transfer-revoked'),
    )
    assert response.status_code == 409
    with Session(engine) as db:
        assert db.get(StructureGovernance, structure['id']).owner_user_id == owner_id


def test_owner_transfer_rejects_member_of_other_structure_without_mutation():
    owner_a, owner_a_id = _guest('transfer-cross-owner-a')
    owner_b, owner_b_id = _guest('transfer-cross-owner-b')
    a = _create_structure(owner_a, 'Transfer Cross A')
    _create_structure(owner_b, 'Transfer Cross B')
    response = client.post(
        f"/forum/v2/structures/{a['slug']}/ownership/transfer",
        json={'new_owner_user_id': owner_b_id},
        headers=_h(owner_a, 'transfer-cross'),
    )
    assert response.status_code == 409
    with Session(engine) as db:
        assert db.get(StructureGovernance, a['id']).owner_user_id == owner_a_id


def test_cross_tenant_writes_are_denied_and_target_data_stays_intact():
    owner_a, _ = _guest('write-isolation-a')
    owner_b, _ = _guest('write-isolation-b')
    a = _create_structure(owner_a, 'Write Isolation A')
    b = _create_structure(owner_b, 'Write Isolation B')

    event = client.post(
        f"/forum/v2/structures/{b['slug']}/events",
        json={'name': 'B event intact', 'starts_at': '2031-01-01T18:00:00Z', 'ends_at': '2031-01-01T22:00:00Z'},
        headers=_h(owner_b),
    )
    assert event.status_code == 201, event.text
    document = client.post(
        f"/forum/v2/structures/{b['slug']}/documents",
        json={'title': 'B document intact', 'visibility': 'MEMBERS'},
        headers=_h(owner_b),
    )
    assert document.status_code == 201, document.text
    channel = client.post(
        f"/forum/v2/structures/{b['slug']}/channels",
        json={'name': 'B private channel', 'visibility': 'MEMBERS'},
        headers=_h(owner_b),
    )
    assert channel.status_code == 201, channel.text
    accounting = client.post(
        f"/forum/v2/structures/{b['slug']}/accounting",
        json={'entry_type': 'EXPENSE', 'category': 'supplier', 'label': 'B accounting intact', 'amount_cents': 4321},
        headers=_h(owner_b),
    )
    assert accounting.status_code == 201, accounting.text

    before_messages = None
    with Session(engine) as db:
        before_messages = db.query(StructureDiscussionPost).filter_by(organization_id=b['id']).count()

    attempts = [
        client.patch(f"/forum/v2/structures/{b['slug']}/documents/{document.json()['id']}", json={'title': 'forged'}, headers=_h(owner_a)),
        client.delete(f"/forum/v2/structures/{b['slug']}/documents/{document.json()['id']}", headers=_h(owner_a)),
        client.post(f"/forum/v2/structures/{b['slug']}/channels/{channel.json()['id']}/messages", json={'body': 'forged'}, headers=_h(owner_a)),
        client.patch(f"/forum/v2/structures/{b['slug']}/events/{event.json()['id']}", json={'name': 'forged'}, headers=_h(owner_a)),
        client.patch(f"/forum/v2/structures/{b['slug']}/accounting/{accounting.json()['id']}", json={'amount_cents': 999999}, headers=_h(owner_a)),
    ]
    assert all(response.status_code in {403, 404} for response in attempts), [response.text for response in attempts]

    with Session(engine) as db:
        doc = db.get(StructureDocument, document.json()['id'])
        ev = db.get(Event, event.json()['id'])
        acc = db.get(AccountingEntry, accounting.json()['id'])
        assert doc.organization_id == b['id'] and doc.title == 'B document intact' and doc.archived_at is None
        assert ev.name == 'B event intact'
        assert acc.organization_id == b['id'] and acc.amount_cents == 4321
        assert db.query(StructureDiscussionPost).filter_by(organization_id=b['id']).count() == before_messages
        assert a['id'] != b['id']


def test_client_supplied_structure_id_cannot_escape_url_scope():
    owner_a, _ = _guest('scope-injection-a')
    owner_b, _ = _guest('scope-injection-b')
    a = _create_structure(owner_a, 'Scope Injection A')
    b = _create_structure(owner_b, 'Scope Injection B')
    injected = str(b['id'])

    event = client.post(
        f"/forum/v2/structures/{a['slug']}/events",
        json={'name': 'Scoped event', 'starts_at': '2032-01-01T18:00:00Z', 'ends_at': '2032-01-01T22:00:00Z', 'structure_id': injected},
        headers=_h(owner_a),
    )
    role = client.post(
        f"/forum/v2/structures/{a['slug']}/roles",
        json={'name': 'Scoped role', 'permissions': ['structure.read'], 'structure_id': injected},
        headers=_h(owner_a),
    )
    document = client.post(
        f"/forum/v2/structures/{a['slug']}/documents",
        json={'title': 'Scoped document', 'visibility': 'MEMBERS', 'structure_id': injected},
        headers=_h(owner_a),
    )
    channel = client.post(
        f"/forum/v2/structures/{a['slug']}/channels",
        json={'name': 'Scoped channel', 'visibility': 'MEMBERS', 'structure_id': injected},
        headers=_h(owner_a),
    )
    accounting = client.post(
        f"/forum/v2/structures/{a['slug']}/accounting",
        json={'entry_type': 'INCOME', 'category': 'bar', 'label': 'Scoped accounting', 'amount_cents': 1234, 'structure_id': injected},
        headers=_h(owner_a),
    )
    post = client.post(
        f"/forum/v2/structures/{a['slug']}/posts",
        json={'title': 'Scoped post', 'body': 'Scoped body', 'status': 'DRAFT', 'structure_id': injected},
        headers=_h(owner_a),
    )
    for response in (event, role, document, channel, accounting, post):
        assert response.status_code in {200, 201}, response.text

    with Session(engine) as db:
        assert db.get(Event, event.json()['id']).host_id == str(a['id'])
        assert db.get(StructureRole, role.json()['id']).organization_id == a['id']
        assert db.get(StructureDocument, document.json()['id']).organization_id == a['id']
        assert db.get(AccountingEntry, accounting.json()['id']).organization_id == a['id']
        assert db.get(OrgaPost, post.json()['id']).organization_id == a['id']
        publication = db.query(OrgaPostPublication).filter_by(post_id=post.json()['id']).one()
        assert publication.organization_id == a['id']
        assert all(row.organization_id != b['id'] for row in [
            db.get(StructureRole, role.json()['id']),
            db.get(StructureDocument, document.json()['id']),
            db.get(AccountingEntry, accounting.json()['id']),
            db.get(OrgaPost, post.json()['id']),
        ])

    channels = client.get(f"/forum/v2/structures/{a['slug']}/channels", headers=_h(owner_a))
    assert any(item['id'] == channel.json()['id'] for item in channels.json()['items'])


def test_stats_json_for_stats_only_role_contains_no_finance_keys():
    owner, _ = _guest('stats-json-owner')
    staff, staff_id = _guest('stats-json-staff')
    structure = _create_structure(owner, 'Stats JSON Org')
    _join_legacy(structure['id'], staff, 'stats-json-join')
    _assign_custom_role(
        owner,
        staff,
        _member_id(structure['id'], staff_id),
        structure['slug'],
        ['structure.read', 'events.view', 'stats.view'],
        'Stats only',
    )
    event = client.post(
        f"/forum/v2/structures/{structure['slug']}/events",
        json={'name': 'Stats JSON Event', 'starts_at': '2033-01-01T18:00:00Z', 'ends_at': '2033-01-01T22:00:00Z'},
        headers=_h(owner),
    )
    assert event.status_code == 201, event.text
    secret = client.post(
        f"/forum/v2/structures/{structure['slug']}/accounting",
        json={'event_id': event.json()['id'], 'entry_type': 'INCOME', 'category': 'bar', 'label': 'Secret finance', 'amount_cents': 987654},
        headers=_h(owner),
    )
    assert secret.status_code == 201
    stats = client.get(
        f"/forum/v2/structures/{structure['slug']}/stats?event_id={event.json()['id']}",
        headers=_h(staff),
    )
    assert stats.status_code == 200, stats.text
    body = stats.json()
    for key in ('revenue', 'cost', 'estimated_profit', 'actual_profit', 'margin', 'turnover', 'incomeCents', 'expenseCents', 'resultCents'):
        assert key not in body
    assert client.get(f"/forum/v2/structures/{structure['slug']}/accounting", headers=_h(staff)).status_code == 403


def test_search_does_not_reveal_treasury_document_or_bureau_message_existence():
    owner, _ = _guest('search-private-owner')
    member, _ = _guest('search-private-member')
    structure = _create_structure(owner, 'Search Privacy Org')
    _join_legacy(structure['id'], member, 'search-private-join')
    client.get(f"/forum/v2/structures/{structure['slug']}/context", headers=_h(member))

    doc_word = 'treasury-unique-omega-391'
    doc = client.post(
        f"/forum/v2/structures/{structure['slug']}/documents",
        json={'title': doc_word, 'visibility': 'TREASURY'},
        headers=_h(owner),
    )
    assert doc.status_code == 201

    msg_word = 'bureau-unique-sigma-827'
    channel = client.post(
        f"/forum/v2/structures/{structure['slug']}/channels",
        json={'name': 'Bureau secret', 'visibility': 'BUREAU'},
        headers=_h(owner),
    )
    assert channel.status_code == 201
    message = client.post(
        f"/forum/v2/structures/{structure['slug']}/channels/{channel.json()['id']}/messages",
        json={'body': msg_word},
        headers=_h(owner),
    )
    assert message.status_code == 201, message.text

    for word in (doc_word, msg_word):
        search = client.get(f"/forum/v2/structures/{structure['slug']}/search?q={word}", headers=_h(member))
        assert search.status_code == 200, search.text
        assert search.json() == {'items': []}


def test_document_direct_access_never_exposes_storage_key_to_unauthorized_member():
    owner, _ = _guest('doc-direct-owner')
    member, _ = _guest('doc-direct-member')
    structure = _create_structure(owner, 'Document Direct Org')
    _join_legacy(structure['id'], member, 'doc-direct-join')
    client.get(f"/forum/v2/structures/{structure['slug']}/context", headers=_h(member))

    doc = client.post(
        f"/forum/v2/structures/{structure['slug']}/documents",
        json={'title': 'Treasury direct secret', 'visibility': 'TREASURY'},
        headers=_h(owner),
    )
    assert doc.status_code == 201
    uploaded = client.post(
        f"/forum/v2/structures/{structure['slug']}/documents/{doc.json()['id']}/versions",
        files={'file': ('secret.txt', b'private bytes', 'text/plain')},
        headers=_h(owner),
    )
    assert uploaded.status_code == 201, uploaded.text

    with Session(engine) as db:
        version = db.query(StructureDocumentVersion).filter_by(document_id=doc.json()['id']).one()
        version_number = version.version_number
        storage_key = version.storage_key

    metadata = client.get(
        f"/forum/v2/structures/{structure['slug']}/documents/{doc.json()['id']}",
        headers=_h(member),
    )
    latest_download = client.get(
        f"/forum/v2/structures/{structure['slug']}/documents/{doc.json()['id']}/download",
        headers=_h(member),
    )
    version_download = client.get(
        f"/forum/v2/structures/{structure['slug']}/documents/{doc.json()['id']}/download?version={version_number}&storage_key={quote(storage_key, safe='')}",
        headers=_h(member),
    )
    direct_storage = client.get(f"/forum/v2/storage/{quote(storage_key, safe='')}", headers=_h(member))
    signed_url = client.get(
        f"/forum/v2/structures/{structure['slug']}/documents/{doc.json()['id']}/signed-url?version={version_number}",
        headers=_h(member),
    )
    assert metadata.status_code == 404
    assert latest_download.status_code == 404
    assert version_download.status_code == 404
    assert direct_storage.status_code == 404
    assert signed_url.status_code == 404
    combined = ' '.join(response.text for response in (metadata, latest_download, version_download, direct_storage, signed_url))
    assert storage_key not in combined


def test_authorized_document_metadata_dto_omits_internal_storage_fields():
    owner, _ = _guest('doc-dto-owner')
    structure = _create_structure(owner, 'Document DTO Org')
    doc = client.post(
        f"/forum/v2/structures/{structure['slug']}/documents",
        json={'title': 'Safe document DTO', 'visibility': 'PRIVATE'},
        headers=_h(owner),
    )
    assert doc.status_code == 201
    uploaded = client.post(
        f"/forum/v2/structures/{structure['slug']}/documents/{doc.json()['id']}/versions",
        files={'file': ('safe.txt', b'safe bytes', 'text/plain')},
        headers=_h(owner),
    )
    assert uploaded.status_code == 201
    metadata = client.get(
        f"/forum/v2/structures/{structure['slug']}/documents/{doc.json()['id']}",
        headers=_h(owner),
    )
    assert metadata.status_code == 200, metadata.text
    serialized = metadata.json()
    assert 'storage_key' not in str(serialized)
    assert 'filesystem_path' not in str(serialized)
    assert 'bucket' not in str(serialized).lower()


def test_claim_reject_and_approve_preserve_governance_unless_transfer_is_explicit():
    owner, owner_id = _guest('claim-flow-owner')
    claimant, claimant_id = _guest('claim-flow-user')
    structure = _create_structure(owner, 'Claim Flow Org')
    slug, org_id = structure['slug'], structure['id']

    with Session(engine) as db:
        before = db.get(StructureGovernance, org_id)
        before_owner, before_status = before.owner_user_id, before.status
    created = client.post(
        f'/forum/v2/public/structures/{slug}/claims',
        json={'reason': 'First claim'}, headers=_h(claimant),
    )
    assert created.status_code == 201
    with Session(engine) as db:
        governance = db.get(StructureGovernance, org_id)
        assert governance.owner_user_id == before_owner == owner_id
        assert governance.status == before_status

    rejected = client.post(
        f"/forum/v2/structures/{slug}/claims/{created.json()['id']}/review",
        json={'decision': 'REJECTED', 'transfer_ownership': False},
        headers=_h(owner),
    )
    assert rejected.status_code == 200
    with Session(engine) as db:
        governance = db.get(StructureGovernance, org_id)
        assert governance.owner_user_id == owner_id
        assert governance.status == before_status

    created_again = client.post(
        f'/forum/v2/public/structures/{slug}/claims',
        json={'reason': 'Second claim'}, headers=_h(claimant),
    )
    assert created_again.status_code == 201
    approved = client.post(
        f"/forum/v2/structures/{slug}/claims/{created_again.json()['id']}/review",
        json={'decision': 'APPROVED', 'transfer_ownership': False},
        headers=_h(owner),
    )
    assert approved.status_code == 200
    with Session(engine) as db:
        governance = db.get(StructureGovernance, org_id)
        membership = db.query(OrganizationMembership).filter_by(organization_id=org_id, user_id=claimant_id).one()
        assert governance.owner_user_id == owner_id
        assert governance.status == before_status
        assert membership.status == 'ACTIVE'


def test_claim_approval_can_transfer_ownership_only_via_explicit_business_workflow():
    owner, _ = _guest('claim-transfer-owner')
    claimant, claimant_id = _guest('claim-transfer-user')
    structure = _create_structure(owner, 'Claim Transfer Org')
    claim = client.post(
        f"/forum/v2/public/structures/{structure['slug']}/claims",
        json={'reason': 'Explicit handover'},
        headers=_h(claimant),
    )
    assert claim.status_code == 201
    approved = client.post(
        f"/forum/v2/structures/{structure['slug']}/claims/{claim.json()['id']}/review",
        json={'decision': 'APPROVED', 'transfer_ownership': True},
        headers=_h(owner),
    )
    assert approved.status_code == 200, approved.text
    with Session(engine) as db:
        assert db.get(StructureGovernance, structure['id']).owner_user_id == claimant_id
        transfer_audit = db.query(AuditLog).join(
            StructureAuditContext,
            StructureAuditContext.audit_log_id == AuditLog.id,
        ).filter(
            StructureAuditContext.organization_id == structure['id'],
            AuditLog.action == 'forum.ownership.transfer',
        ).one_or_none()
        assert transfer_audit is not None


def test_public_page_nonpublished_states_stay_nonpublic_and_query_cannot_escalate_audience():
    owner, _ = _guest('public-lifecycle-owner')
    structure = _create_structure(owner, 'Public Lifecycle Org')
    slug = structure['slug']
    public_url = f'/forum/v2/public/structures/{slug}'
    assert client.get(public_url).status_code == 404

    for status in ('HIDDEN', 'SUSPENDED', 'ARCHIVED'):
        changed = client.patch(
            f'/forum/v2/structures/{slug}/public-page',
            json={'status': status}, headers=_h(owner),
        )
        assert changed.status_code == 200, changed.text
        assert client.get(public_url).status_code == 404
        assert client.get(f'{public_url}?audience=PRIVATE&preview=admin').status_code == 404

    published = client.patch(
        f'/forum/v2/structures/{slug}/public-page',
        json={'status': 'PUBLISHED'}, headers=_h(owner),
    )
    assert published.status_code == 200
    assert published.json()['structureStatus'] == 'ACTIVE'
    assert client.get(public_url).status_code == 200

    hidden = client.patch(
        f'/forum/v2/structures/{slug}/public-page',
        json={'status': 'HIDDEN'}, headers=_h(owner),
    )
    assert hidden.status_code == 200
    assert client.get(f'{public_url}?audience=PRIVATE').status_code == 404


def test_public_page_is_blocked_when_structure_is_archived_even_if_page_is_published():
    owner, _ = _guest('public-archived-owner')
    structure = _create_structure(owner, 'Public Archived Structure')
    slug = structure['slug']
    assert client.patch(
        f'/forum/v2/structures/{slug}/public-page',
        json={'status': 'PUBLISHED'}, headers=_h(owner),
    ).status_code == 200
    with Session(engine) as db:
        governance = db.get(StructureGovernance, structure['id'])
        governance.status = 'ARCHIVED'
        db.commit()
    assert client.get(f'/forum/v2/public/structures/{slug}').status_code == 404


def test_openapi_forum_json_bodies_are_typed_and_message_uses_message_create_in():
    response = client.get('/openapi.json')
    assert response.status_code == 200
    schema = response.json()
    message_path = '/forum/v2/structures/{slug}/channels/{channel_id}/messages'
    message_body = schema['paths'][message_path]['post']['requestBody']['content']['application/json']['schema']
    assert message_body.get('$ref', '').endswith('/MessageCreateIn')

    components = schema.get('components', {}).get('schemas', {})
    untyped: list[str] = []
    for path, methods in schema['paths'].items():
        if not path.startswith('/forum/v2/'):
            continue
        for method, operation in methods.items():
            if method.lower() not in {'post', 'put', 'patch', 'delete'} or not isinstance(operation, dict):
                continue
            request_body = operation.get('requestBody', {})
            json_schema = request_body.get('content', {}).get('application/json', {}).get('schema')
            if not json_schema:
                continue
            target = json_schema
            ref = json_schema.get('$ref') if isinstance(json_schema, dict) else None
            if ref:
                target = components.get(ref.rsplit('/', 1)[-1], {})
            if not isinstance(target, dict):
                untyped.append(f'{method.upper()} {path}: non-dict schema')
                continue
            if target.get('additionalProperties') is True:
                untyped.append(f'{method.upper()} {path}: arbitrary object')
            if target.get('type') == 'object' and not target.get('properties') and not any(key in target for key in ('$ref', 'allOf', 'oneOf', 'anyOf')):
                untyped.append(f'{method.upper()} {path}: empty object')
    assert untyped == []


def test_openapi_pydantic_contracts_do_not_expose_internal_storage_fields():
    schema = client.get('/openapi.json').json()
    forbidden = {'storage_key', 'filesystem_path', 'internal_bucket_key', 'bucket_key'}
    exposed: list[str] = []
    for name, component in schema.get('components', {}).get('schemas', {}).items():
        properties = set((component.get('properties') or {}).keys())
        for key in sorted(properties & forbidden):
            exposed.append(f'{name}.{key}')
    assert exposed == []
