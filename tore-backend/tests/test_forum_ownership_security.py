import os
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from db import Base, engine, now_utc
from main import app
from models import AuditLog, OrganizationMembership
from app.ownership_models import StructureOwnership, StructureOwnershipTransfer, StructureRecoveryRequest


client = TestClient(app)


def setup_function():
    os.environ["ADMIN_API_KEY"] = "ownership-test-admin"
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _guest(name: str) -> tuple[str, str]:
    response = client.post("/auth/guest", json={"display_name": name})
    assert response.status_code == 200
    token = response.json()["token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    return token, me.json()["id"]


def _headers(token: str, key: str | None = None) -> dict[str, str]:
    result = {"Authorization": f"Bearer {token}"}
    if key:
        result["Idempotency-Key"] = key
    return result


def _structure(owner_token: str, name: str = "Ownership Secure") -> tuple[int, str]:
    response = client.post(
        "/orgas",
        json={"name": name, "city": "Liège", "org_type": "CIRCLE"},
        headers=_headers(owner_token, f"create-{name}"),
    )
    assert response.status_code == 200
    org = response.json()["orga"]
    return org["id"], org["slug"]


def _join(org_id: int, token: str, suffix: str):
    response = client.post(f"/orgas/{org_id}/join", headers=_headers(token, f"join-{suffix}"))
    assert response.status_code == 200


def _admin_headers() -> dict[str, str]:
    return {"X-Admin-Api-Key": "ownership-test-admin"}


def test_recovery_requires_configured_secondary_owner_and_never_grants_owner_on_request():
    owner_token, owner_id = _guest("owner")
    recovery_token, recovery_id = _guest("recovery")
    outsider_token, outsider_id = _guest("outsider")
    org_id, slug = _structure(owner_token)
    _join(org_id, recovery_token, "recovery")
    _join(org_id, outsider_token, "outsider")

    bootstrap = client.get(f"/forum/structures/{slug}/ownership", headers=_headers(owner_token))
    assert bootstrap.status_code == 200
    assert "ownership.transfer" in bootstrap.json()["capabilities"]
    assert "ownership.recover" in bootstrap.json()["capabilities"]

    configured = client.put(
        f"/forum/structures/{slug}/ownership/recovery-owner",
        json={"user_id": recovery_id},
        headers=_headers(owner_token),
    )
    assert configured.status_code == 200

    denied = client.post(
        f"/forum/structures/{slug}/ownership/recovery",
        json={"reason": "Je connais seulement l'identifiant de cette structure."},
        headers=_headers(outsider_token),
    )
    assert denied.status_code == 403

    requested = client.post(
        f"/forum/structures/{slug}/ownership/recovery",
        json={"reason": "Le propriétaire principal a perdu son accès; demande de récupération contrôlée."},
        headers=_headers(recovery_token),
    )
    assert requested.status_code == 200
    assert requested.json()["status"] == "REQUESTED"

    with Session(engine) as db:
        state = db.query(StructureOwnership).filter_by(organization_id=org_id).one()
        assert state.primary_owner_user_id == owner_id
        assert state.recovery_owner_user_id == recovery_id
        recovery_membership = db.query(OrganizationMembership).filter_by(organization_id=org_id, user_id=recovery_id).one()
        outsider_membership = db.query(OrganizationMembership).filter_by(organization_id=org_id, user_id=outsider_id).one()
        assert recovery_membership.role != "OWNER"
        assert outsider_membership.role != "OWNER"


def test_transfer_is_backend_enforced_target_confirmed_and_completed():
    owner_token, owner_id = _guest("transfer-owner")
    target_token, target_id = _guest("transfer-target")
    outsider_token, _ = _guest("transfer-outsider")
    org_id, slug = _structure(owner_token, "Transfer Secure")
    _join(org_id, target_token, "target")
    _join(org_id, outsider_token, "outsider")

    denied = client.post(
        f"/forum/structures/{slug}/ownership/transfers",
        json={"to_user_id": target_id},
        headers=_headers(outsider_token),
    )
    assert denied.status_code == 403

    requested = client.post(
        f"/forum/structures/{slug}/ownership/transfers",
        json={"to_user_id": target_id},
        headers=_headers(owner_token),
    )
    assert requested.status_code == 200
    transfer_id = requested.json()["id"]
    assert requested.json()["status"] == "REQUESTED"

    wrong_confirmation = client.post(
        f"/forum/structures/{slug}/ownership/transfers/{transfer_id}/confirm",
        headers=_headers(outsider_token),
    )
    assert wrong_confirmation.status_code == 403

    confirmed = client.post(
        f"/forum/structures/{slug}/ownership/transfers/{transfer_id}/confirm",
        headers=_headers(target_token),
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "COMPLETED"
    assert confirmed.json()["primaryOwnerUserId"] == target_id

    with Session(engine) as db:
        state = db.query(StructureOwnership).filter_by(organization_id=org_id).one()
        row = db.get(StructureOwnershipTransfer, transfer_id)
        old_membership = db.query(OrganizationMembership).filter_by(organization_id=org_id, user_id=owner_id).one()
        new_membership = db.query(OrganizationMembership).filter_by(organization_id=org_id, user_id=target_id).one()
        assert state.primary_owner_user_id == target_id
        assert row.status == "COMPLETED"
        assert row.confirmed_at is not None
        assert row.completed_at is not None
        assert old_membership.role == "ADMIN"
        assert new_membership.role == "OWNER"
        actions = {item.action for item in db.query(AuditLog).all()}
        assert "ownership.transfer.requested" in actions
        assert "ownership.transfer.confirmed" in actions
        assert "ownership.transfer.completed" in actions
        assert "ownership.changed" in actions


def test_expired_transfer_cannot_be_confirmed():
    owner_token, _ = _guest("expire-owner")
    target_token, target_id = _guest("expire-target")
    org_id, slug = _structure(owner_token, "Expiry Secure")
    _join(org_id, target_token, "expiry-target")
    requested = client.post(
        f"/forum/structures/{slug}/ownership/transfers",
        json={"to_user_id": target_id},
        headers=_headers(owner_token),
    )
    transfer_id = requested.json()["id"]
    with Session(engine) as db:
        row = db.get(StructureOwnershipTransfer, transfer_id)
        row.expires_at = now_utc() - timedelta(seconds=1)
        db.commit()

    response = client.post(
        f"/forum/structures/{slug}/ownership/transfers/{transfer_id}/confirm",
        headers=_headers(target_token),
    )
    assert response.status_code == 409
    with Session(engine) as db:
        assert db.get(StructureOwnershipTransfer, transfer_id).status == "EXPIRED"


def test_freeze_blocks_critical_admin_writes_and_admin_can_resolve_recovery_conflict():
    owner_token, owner_id = _guest("freeze-owner")
    recovery_token, recovery_id = _guest("freeze-recovery")
    org_id, slug = _structure(owner_token, "Freeze Secure")
    _join(org_id, recovery_token, "freeze-recovery")
    assert client.get(f"/forum/structures/{slug}/ownership", headers=_headers(owner_token)).status_code == 200
    assert client.put(
        f"/forum/structures/{slug}/ownership/recovery-owner",
        json={"user_id": recovery_id},
        headers=_headers(owner_token),
    ).status_code == 200

    frozen = client.post(
        f"/forum/admin/structures/{slug}/freeze",
        json={"reason": "Litige de propriété en cours; gel conservatoire.", "keep_public_visible": True},
        headers=_admin_headers(),
    )
    assert frozen.status_code == 200
    assert frozen.json()["frozen"] is True
    assert client.get(f"/forum/structures/{slug}").status_code == 200

    blocked = client.post(
        f"/forum/structures/{slug}/discussions",
        json={"title": "Mutation bloquée", "body": "Ce contenu ne doit pas être créé pendant le gel."},
        headers=_headers(owner_token, "frozen-discussion"),
    )
    assert blocked.status_code == 423

    blocked_transfer = client.post(
        f"/forum/structures/{slug}/ownership/transfers",
        json={"to_user_id": recovery_id},
        headers=_headers(owner_token),
    )
    assert blocked_transfer.status_code == 423

    recovery = client.post(
        f"/forum/structures/{slug}/ownership/recovery",
        json={"reason": "Le litige est gelé; je demande une validation TORÈ documentée."},
        headers=_headers(recovery_token),
    )
    assert recovery.status_code == 200
    recovery_request_id = recovery.json()["id"]

    resolved = client.post(
        f"/forum/admin/structures/{slug}/recoveries/{recovery_request_id}/resolve",
        json={"approve": True, "reason": "Identité et mandat vérifiés par l'administration TORÈ."},
        headers=_admin_headers(),
    )
    assert resolved.status_code == 200
    assert resolved.json()["primaryOwnerUserId"] == recovery_id

    with Session(engine) as db:
        state = db.query(StructureOwnership).filter_by(organization_id=org_id).one()
        request = db.get(StructureRecoveryRequest, recovery_request_id)
        old_membership = db.query(OrganizationMembership).filter_by(organization_id=org_id, user_id=owner_id).one()
        assert state.is_frozen is True
        assert state.primary_owner_user_id == recovery_id
        assert request.status == "APPROVED"
        assert old_membership.role == "ADMIN"
        actions = {item.action for item in db.query(AuditLog).all()}
        assert "ownership.freeze" in actions
        assert "ownership.freeze.blocked_operation" in actions
        assert "ownership.recovery.requested" in actions
        assert "ownership.recovery.admin_approved" in actions

    unfrozen = client.post(f"/forum/admin/structures/{slug}/unfreeze", headers=_admin_headers())
    assert unfrozen.status_code == 200
    assert unfrozen.json()["frozen"] is False


def test_freeze_can_hide_public_content():
    owner_token, _ = _guest("hide-owner")
    _, slug = _structure(owner_token, "Hidden Freeze")
    assert client.get(f"/forum/structures/{slug}/ownership", headers=_headers(owner_token)).status_code == 200
    assert client.post(
        f"/forum/admin/structures/{slug}/freeze",
        json={"reason": "Usurpation publique suspectée; masquer la vitrine.", "keep_public_visible": False},
        headers=_admin_headers(),
    ).status_code == 200
    hidden = client.get(f"/forum/structures/{slug}")
    assert hidden.status_code == 423
