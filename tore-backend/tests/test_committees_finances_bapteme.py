from __future__ import annotations

from datetime import timedelta
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import AuditLog, Committee, CommitteeInviteCode, CommitteeMembership, CommitteeYear


def _auth_guest(client: TestClient, name: str) -> tuple[str, str]:
    Base.metadata.create_all(engine)
    token = client.post('/auth/guest', json={'display_name': name}).json()['token']
    me = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'}).json()
    return token, me['id']


def _seed_committee(owner_user_id: str) -> tuple[int, int, str]:
    Base.metadata.create_all(engine)
    s = get_session()
    try:
        suffix = secrets.token_hex(3)
        committee = Committee(name='Comité Finances', slug=f'com-fin-{suffix}')
        s.add(committee)
        s.flush()
        year = CommitteeYear(committee_id=committee.id, year_label='2025-2026', is_active=True)
        s.add(year)
        s.add(CommitteeMembership(committee_id=committee.id, user_id=owner_user_id, role='OWNER', is_active=True))
        join_code = f'JOIN{suffix.upper()}'
        s.add(CommitteeInviteCode(committee_id=committee.id, code=join_code, expires_at=now_utc() + timedelta(days=2), created_by=owner_user_id, uses_left=10))
        s.commit()
        return committee.id, year.id, join_code
    finally:
        s.close()


def test_finance_ledger_idempotent_permissions_exports_and_summary():
    client = TestClient(app)
    owner_token, owner_id = _auth_guest(client, 'fin-owner')
    committee_id, year_id, join_code = _seed_committee(owner_id)

    member_token, _ = _auth_guest(client, 'fin-member')
    client.post(f'/committees/{committee_id}/join_by_code', json={'code': join_code}, headers={'Authorization': f'Bearer {member_token}', 'Idempotency-Key': 'join-fin-1'})

    denied = client.post(
        f'/committees/{committee_id}/finances/ledger',
        json={'yearId': year_id, 'type': 'EXPENSE', 'amountCents': 1500, 'currency': 'EUR', 'category': 'Logistique', 'occurredAt': '2026-01-15'},
        headers={'Authorization': f'Bearer {member_token}', 'Idempotency-Key': 'fin-ledger-member-1'},
    )
    assert denied.status_code == 403

    headers = {'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'fin-ledger-owner-1'}
    first = client.post(
        f'/committees/{committee_id}/finances/ledger',
        json={'yearId': year_id, 'type': 'EXPENSE', 'amountCents': 1500, 'currency': 'EUR', 'category': 'Logistique', 'occurredAt': '2026-01-15', 'note': 'sono'},
        headers=headers,
    )
    second = client.post(
        f'/committees/{committee_id}/finances/ledger',
        json={'yearId': year_id, 'type': 'EXPENSE', 'amountCents': 1500, 'currency': 'EUR', 'category': 'Logistique', 'occurredAt': '2026-01-15', 'note': 'sono'},
        headers=headers,
    )
    assert first.status_code == 200
    assert first.json() == second.json()

    client.post(
        f'/committees/{committee_id}/finances/ledger',
        json={'yearId': year_id, 'type': 'INCOME', 'amountCents': 5000, 'currency': 'EUR', 'category': 'Sponsors', 'occurredAt': '2026-01-16'},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'fin-ledger-owner-2'},
    )

    summary = client.get(f'/committees/{committee_id}/finances/summary?year_id={year_id}', headers={'Authorization': f'Bearer {owner_token}'})
    assert summary.status_code == 200
    assert summary.json()['incomeCents'] == 5000
    assert summary.json()['expenseCents'] == 1500
    assert summary.json()['netCents'] == 3500

    export_csv = client.get(f'/committees/{committee_id}/finances/export.csv?year_id={year_id}', headers={'Authorization': f'Bearer {owner_token}'})
    assert export_csv.status_code == 200
    assert export_csv.headers['content-type'].startswith('text/csv')

    snapshot = client.get(f'/committees/{committee_id}/finances/snapshot.json?year_id={year_id}', headers={'Authorization': f'Bearer {owner_token}'})
    assert snapshot.status_code == 200
    assert 'ledger' in snapshot.json()


def test_bapteme_campaign_invite_accept_assign_incident_and_exports():
    client = TestClient(app)
    owner_token, owner_id = _auth_guest(client, 'bap-owner')
    committee_id, year_id, _ = _seed_committee(owner_id)
    headers = {'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'bap-campaign-1'}

    campaign = client.post(f'/committees/{committee_id}/bapteme/campaign', json={'yearId': year_id, 'name': 'Baptême 2026'}, headers=headers)
    assert campaign.status_code == 200
    campaign_id = campaign.json()['id']

    invite = client.post(
        f'/committees/{committee_id}/bapteme/invites',
        json={'campaignId': campaign_id, 'blueDisplayName': 'Bleu Test'},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'bap-invite-1'},
    )
    assert invite.status_code == 200
    invite_code = invite.json()['inviteCode']
    invite_id = invite.json()['id']

    accepted_user_token, _ = _auth_guest(client, 'bleu-accepted')
    accept = client.post(
        f'/committees/{committee_id}/bapteme/invites/accept',
        json={'inviteCode': invite_code},
        headers={'Authorization': f'Bearer {accepted_user_token}', 'Idempotency-Key': 'bap-accept-1'},
    )
    assert accept.status_code == 200
    assert accept.json()['status'] == 'ACCEPTED'

    slot = client.post(
        f'/committees/{committee_id}/bapteme/slots',
        json={'campaignId': campaign_id, 'startsAt': now_utc().isoformat(), 'endsAt': (now_utc() + timedelta(hours=2)).isoformat(), 'location': 'Campus', 'description': 'Atelier'},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'bap-slot-1'},
    )
    assert slot.status_code == 200
    slot_id = slot.json()['id']

    assign = client.post(
        f'/committees/{committee_id}/bapteme/assign',
        json={'inviteId': invite_id, 'slotId': slot_id},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'bap-assign-1'},
    )
    assert assign.status_code == 200

    outsider_token, _ = _auth_guest(client, 'outsider')
    denied = client.post(
        f'/committees/{committee_id}/bapteme/incidents',
        json={'campaignId': campaign_id, 'inviteId': invite_id, 'type': 'SAFETY', 'note': 'test'},
        headers={'Authorization': f'Bearer {outsider_token}', 'Idempotency-Key': 'bap-incident-denied'},
    )
    assert denied.status_code == 403

    incident = client.post(
        f'/committees/{committee_id}/bapteme/incidents',
        json={'campaignId': campaign_id, 'inviteId': invite_id, 'type': 'SAFETY', 'note': 'incident discret'},
        headers={'Authorization': f'Bearer {owner_token}', 'Idempotency-Key': 'bap-incident-1'},
    )
    assert incident.status_code == 200

    exp_inv = client.get(f'/committees/{committee_id}/bapteme/export_invites.csv?campaignId={campaign_id}', headers={'Authorization': f'Bearer {owner_token}'})
    exp_slots = client.get(f'/committees/{committee_id}/bapteme/export_slots.csv?campaignId={campaign_id}', headers={'Authorization': f'Bearer {owner_token}'})
    assert exp_inv.status_code == 200
    assert exp_slots.status_code == 200

    s = get_session()
    try:
        audit = s.query(AuditLog).filter(AuditLog.action == 'committee.bapteme.incident.create').first()
        assert audit is not None
    finally:
        s.close()
