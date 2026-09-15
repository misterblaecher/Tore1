import hashlib
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from db import Base, engine, now_utc
from main import app
from models import AppUser, OrganizationMembership, StructureInvitation
from app.routers import forum_invitations
from app.services import rate_limit_service


client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    rate_limit_service._store.clear()


def _guest(name: str) -> tuple[str, str]:
    response = client.post("/auth/guest", json={"display_name": name})
    assert response.status_code == 200
    token = response.json()["token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    return token, me.json()["id"]


def _headers(token: str, key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if key:
        headers["Idempotency-Key"] = key
    return headers


def _structure(owner_token: str, suffix: str) -> tuple[int, str]:
    response = client.post(
        "/orgas",
        json={"name": f"Invitation Structure {suffix}", "city": "Liège", "org_type": "COMMITTEE"},
        headers=_headers(owner_token, f"invite-orga-{suffix}"),
    )
    assert response.status_code == 200
    org = response.json()["orga"]
    return org["id"], org["slug"]


def _set_email(user_id: str, email: str) -> None:
    with Session(engine) as db:
        user = db.get(AppUser, user_id)
        assert user is not None
        user.email = email.lower()
        db.commit()


def _token_from(response_json: dict) -> str:
    return response_json["inviteUrl"].rsplit("/", 1)[-1]


def _disable_mail(monkeypatch) -> None:
    monkeypatch.setattr(forum_invitations, "send_structure_invitation_email", lambda **_: "TEST")


def test_invitation_uses_email_hashed_token_qr_and_does_not_require_account(monkeypatch):
    _disable_mail(monkeypatch)
    owner_token, _ = _guest("invite-owner")
    _, slug = _structure(owner_token, "email")

    response = client.post(
        f"/forum/structures/{slug}/invitations",
        json={"email": "prenom.nom@example.com", "invited_role": "MEMBER"},
        headers=_headers(owner_token),
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["email"] == "prenom.nom@example.com"
    assert payload["status"] == "PENDING"
    assert payload["deliveryStatus"] == "TEST"
    assert payload["inviteUrl"].startswith("http")
    assert payload["qrSvgDataUri"].startswith("data:image/svg+xml;base64,")
    assert "userId" not in payload

    token = _token_from(payload)
    with Session(engine) as db:
        invitation = db.get(StructureInvitation, payload["id"])
        assert invitation is not None
        assert invitation.token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()
        assert invitation.token_hash != token
        assert not hasattr(invitation, "token")

    listing = client.get(f"/forum/structures/{slug}/invitations", headers=_headers(owner_token))
    assert listing.status_code == 200
    assert listing.json()["items"][0]["status"] == "PENDING"
    assert "inviteUrl" not in listing.json()["items"][0]

    audit = client.get(f"/forum/structures/{slug}/audit", headers=_headers(owner_token))
    assert audit.status_code == 200
    assert "forum.invitation.create" in {item["action"] for item in audit.json()["items"]}


def test_invitation_accept_is_single_use_and_creates_rbac_membership(monkeypatch):
    _disable_mail(monkeypatch)
    owner_token, _ = _guest("invite-owner-accept")
    target_token, target_id = _guest("invite-target")
    target_email = "invite.target@example.com"
    _set_email(target_id, target_email)
    org_id, slug = _structure(owner_token, "accept")

    created = client.post(
        f"/forum/structures/{slug}/invitations",
        json={"email": target_email, "invited_role": "TREASURER"},
        headers=_headers(owner_token),
    )
    assert created.status_code == 202
    invite_token = _token_from(created.json())

    preview = client.get(f"/forum/invitations/{invite_token}")
    assert preview.status_code == 200
    assert preview.json()["status"] == "PENDING"
    assert preview.json()["emailMasked"].endswith("@example.com")

    accepted = client.post(f"/forum/invitations/{invite_token}/accept", headers=_headers(target_token))
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "ACCEPTED"
    assert accepted.json()["role"] == "TREASURER"

    with Session(engine) as db:
        membership = db.query(OrganizationMembership).filter(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.user_id == target_id,
        ).one()
        assert membership.status == "ACTIVE"
        assert membership.role == "TREASURER"
        invitation = db.get(StructureInvitation, created.json()["id"])
        assert invitation is not None and invitation.accepted_at is not None

    replay = client.post(f"/forum/invitations/{invite_token}/accept", headers=_headers(target_token))
    assert replay.status_code == 410

    listing = client.get(f"/forum/structures/{slug}/invitations?status=ACCEPTED", headers=_headers(owner_token))
    assert listing.status_code == 200
    assert [item["status"] for item in listing.json()["items"]] == ["ACCEPTED"]


def test_resend_rotates_token_and_revoke_decline_expiry_are_enforced(monkeypatch):
    _disable_mail(monkeypatch)
    owner_token, _ = _guest("invite-owner-lifecycle")
    target_token, target_id = _guest("invite-lifecycle-target")
    _set_email(target_id, "lifecycle@example.com")
    _, slug = _structure(owner_token, "lifecycle")

    created = client.post(
        f"/forum/structures/{slug}/invitations",
        json={"email": "lifecycle@example.com", "invited_role": "MEMBER"},
        headers=_headers(owner_token),
    )
    assert created.status_code == 202
    invitation_id = created.json()["id"]
    old_token = _token_from(created.json())

    resent = client.post(f"/forum/structures/{slug}/invitations/{invitation_id}/resend", headers=_headers(owner_token))
    assert resent.status_code == 202
    new_token = _token_from(resent.json())
    assert new_token != old_token
    assert client.get(f"/forum/invitations/{old_token}").status_code == 410
    assert client.get(f"/forum/invitations/{new_token}").status_code == 200

    revoked = client.post(f"/forum/structures/{slug}/invitations/{invitation_id}/revoke", headers=_headers(owner_token))
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "REVOKED"
    assert client.post(f"/forum/invitations/{new_token}/accept", headers=_headers(target_token)).status_code == 410

    declined_create = client.post(
        f"/forum/structures/{slug}/invitations",
        json={"email": "decline@example.com", "invited_role": "STAFF"},
        headers=_headers(owner_token),
    )
    decline_token = _token_from(declined_create.json())
    declined = client.post(f"/forum/invitations/{decline_token}/decline")
    assert declined.status_code == 200
    assert declined.json()["status"] == "DECLINED"
    assert client.post(f"/forum/invitations/{decline_token}/decline").status_code == 410

    expired_create = client.post(
        f"/forum/structures/{slug}/invitations",
        json={"email": "expired@example.com", "invited_role": "MEMBER"},
        headers=_headers(owner_token),
    )
    expired_token = _token_from(expired_create.json())
    with Session(engine) as db:
        invitation = db.get(StructureInvitation, expired_create.json()["id"])
        assert invitation is not None
        invitation.expires_at = now_utc() - timedelta(seconds=1)
        db.commit()
    assert client.get(f"/forum/invitations/{expired_token}").json()["status"] == "EXPIRED"
    assert client.post(f"/forum/invitations/{expired_token}/accept", headers=_headers(target_token)).status_code == 410


def test_invitation_accept_rejects_authenticated_account_with_other_email(monkeypatch):
    _disable_mail(monkeypatch)
    owner_token, _ = _guest("invite-owner-mismatch")
    wrong_token, wrong_id = _guest("wrong-invite-user")
    _set_email(wrong_id, "wrong@example.com")
    _, slug = _structure(owner_token, "mismatch")

    created = client.post(
        f"/forum/structures/{slug}/invitations",
        json={"email": "right@example.com", "invited_role": "MEMBER"},
        headers=_headers(owner_token),
    )
    invite_token = _token_from(created.json())
    mismatch = client.post(f"/forum/invitations/{invite_token}/accept", headers=_headers(wrong_token))
    assert mismatch.status_code == 403
    assert mismatch.json()["detail"]["reason"] == "INVITATION_ACCOUNT_MISMATCH"
