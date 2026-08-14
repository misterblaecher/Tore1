from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import (
    AppUser,
    AppUserPrivacySetting,
    AuditLog,
    Event,
    EventJoin,
    EventStaff,
    Organization,
    OrganizationMembership,
)


client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _user(name: str, *, registered: bool = True) -> tuple[str, str]:
    response = client.post("/auth/guest", json={"display_name": name})
    assert response.status_code == 200
    token = response.json()["token"]
    user_id = response.json()["user"]["id"]
    if registered:
        with get_session() as db:
            row = db.get(AppUser, user_id)
            row.is_guest = False
            row.email = f"{name.lower().replace(' ', '.')}@private.example"
            row.phone = "+32000000000"
            row.address_text = "Sensitive street"
            db.commit()
    return token, user_id


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _set_privacy(user_id: str, **values):
    with get_session() as db:
        row = AppUserPrivacySetting(user_id=user_id, **values)
        db.add(row)
        db.commit()


def _organization(owner_id: str, name: str = "Structure TORÈ") -> int:
    with get_session() as db:
        org = Organization(
            name=name,
            slug=name.lower().replace(" ", "-"),
            created_by_user_id=owner_id,
        )
        db.add(org)
        db.flush()
        org_id = org.id
        db.commit()
        return org_id


def test_owner_profile_patch_unique_username_and_mass_assignment_rejected():
    first_token, first_id = _user("First")
    second_token, _ = _user("Second")

    owner = client.get("/me/profile", headers=_headers(first_token))
    assert owner.status_code == 200
    assert owner.json()["id"] == first_id
    assert owner.json()["privacy"]["profile"] == "PRIVATE"

    updated = client.patch(
        "/me/profile",
        headers=_headers(first_token),
        json={
            "username": "first.user",
            "display_name": "First User",
            "bio": "A real short bio",
            "city": "Liège",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["username"] == "first.user"

    privacy_updated = client.patch(
        "/me/privacy",
        headers=_headers(first_token),
        json={"bio": "TORE_USERS", "event_history_opt_in": True},
    )
    assert privacy_updated.status_code == 200

    conflict = client.patch(
        "/me/profile",
        headers=_headers(second_token),
        json={"username": "FIRST.USER"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["reason"] == "username_already_used"

    assert client.patch(
        "/me/profile",
        headers=_headers(first_token),
        json={"display_name": "   "},
    ).status_code == 422
    assert client.patch(
        "/me/privacy",
        headers=_headers(first_token),
        json={"bio": None},
    ).status_code == 422

    for forbidden in ("roles", "is_admin", "capabilities", "affiliations", "global_role"):
        response = client.patch(
            "/me/profile",
            headers=_headers(first_token),
            json={forbidden: ["ADMIN"]},
        )
        assert response.status_code == 422

    with get_session() as db:
        row = db.get(AppUser, first_id)
        assert row.global_role == "USER"
        audit = db.query(AuditLog).filter(AuditLog.action == "user.profile.update").first()
        assert audit is not None
        assert audit.payload_json == {"fields": ["bio", "city", "display_name", "username"]}
        privacy_audit = db.query(AuditLog).filter(AuditLog.action == "user.privacy.update").first()
        assert privacy_audit is not None
        assert privacy_audit.payload_json == {"fields": ["bio", "event_history_opt_in"]}


def test_public_tore_users_private_visibility_and_sensitive_filtering():
    owner_token, owner_id = _user("Owner")
    viewer_token, _ = _user("Viewer")
    _set_privacy(
        owner_id,
        visibility="PUBLIC",
        photo_visibility="TORE_USERS",
        bio_visibility="PRIVATE",
        affiliations_visibility="PUBLIC",
    )
    client.patch(
        "/me/profile",
        headers=_headers(owner_token),
        json={"username": "owner", "avatar_url": "https://cdn.example/avatar.png", "bio": "private bio"},
    )

    anonymous = client.get(f"/profiles/{owner_id}")
    assert anonymous.status_code == 200
    assert "avatar_url" not in anonymous.json()
    assert "bio" not in anonymous.json()

    connected = client.get(f"/profiles/{owner_id}", headers=_headers(viewer_token))
    assert connected.status_code == 200
    assert connected.json()["avatar_url"] == "https://cdn.example/avatar.png"
    assert "bio" not in connected.json()

    forbidden_fields = {
        "email", "phone", "address_text", "password_hash", "tokens",
        "global_role", "account_mode", "moderation_notes", "payment",
    }
    assert forbidden_fields.isdisjoint(connected.json())

    privacy = client.patch(
        "/me/privacy",
        headers=_headers(owner_token),
        json={"profile": "TORE_USERS"},
    )
    assert privacy.status_code == 200
    assert client.get(f"/profiles/{owner_id}").status_code == 403
    assert client.get(f"/profiles/{owner_id}", headers=_headers(viewer_token)).status_code == 200

    client.patch("/me/privacy", headers=_headers(owner_token), json={"profile": "PRIVATE"})
    assert client.get(f"/profiles/{owner_id}", headers=_headers(viewer_token)).status_code == 403
    assert client.get(f"/profiles/{owner_id}", headers=_headers(owner_token)).status_code == 200


def test_event_history_requires_opt_in_and_filters_private_events():
    token, user_id = _user("History")
    _set_privacy(
        user_id,
        visibility="PUBLIC",
        event_history_visibility="PUBLIC",
        event_history_opt_in=False,
    )
    with get_session() as db:
        public = Event(
            name="Public event",
            visibility="PUBLIC",
            publication_status="PUBLISHED",
            starts_at=now_utc(),
            ends_at=now_utc() + timedelta(hours=2),
        )
        private = Event(
            name="Private event",
            visibility="PRIVATE",
            publication_status="PUBLISHED",
            starts_at=now_utc(),
            ends_at=now_utc() + timedelta(hours=2),
        )
        db.add_all([public, private])
        db.flush()
        db.add_all([
            EventJoin(event_id=public.id, user_id=user_id),
            EventJoin(event_id=private.id, user_id=user_id),
        ])
        db.commit()

    hidden = client.get(f"/profiles/{user_id}").json()
    assert "event_history" not in hidden

    client.patch(
        "/me/privacy",
        headers=_headers(token),
        json={"event_history_opt_in": True},
    )
    visible = client.get(f"/profiles/{user_id}").json()["event_history"]
    assert [event["name"] for event in visible] == ["Public event"]


def test_affiliation_states_visibility_capabilities_and_immediate_revoke():
    owner_token, owner_id = _user("Aff Owner")
    member_token, member_id = _user("Aff Member")
    org_id = _organization(owner_id)
    now = now_utc()
    with get_session() as db:
        db.add(OrganizationMembership(
            organization_id=org_id,
            user_id=owner_id,
            role="OWNER",
            status="ACTIVE",
            starts_at=now,
            joined_at=now,
            visibility="PRIVATE",
            validation_source="OWNER_CREATION",
            created_by_user_id=owner_id,
        ))
        db.add(OrganizationMembership(
            organization_id=org_id,
            user_id=member_id,
            role="BUREAU",
            status="ACTIVE",
            starts_at=now,
            joined_at=now,
            visibility="PUBLIC",
            validation_source="AUTHORIZED_APPROVAL",
            validated_by_user_id=owner_id,
            created_by_user_id=owner_id,
        ))
        db.commit()

    _set_privacy(member_id, visibility="PUBLIC", affiliations_visibility="PUBLIC")
    affiliations = client.get("/me/affiliations", headers=_headers(member_token))
    assert affiliations.status_code == 200
    assert affiliations.json()["items"][0]["role"] == "BUREAU"
    assert affiliations.json()["items"][0]["status"] == "ACTIVE"

    capabilities = client.get("/me/capabilities", headers=_headers(member_token)).json()
    assert capabilities["modes"]["organizer"] is True
    assert capabilities["structures"][0]["role"] == "BUREAU"

    affiliation_id = affiliations.json()["items"][0]["id"]
    revoked = client.post(
        f"/affiliations/{affiliation_id}/revoke",
        headers=_headers(owner_token),
        json={"reason": "Mandate ended"},
    )
    assert revoked.status_code == 200
    assert revoked.json()["affiliation"]["status"] == "REVOKED"
    assert revoked.json()["capabilities_effective_immediately"] is True
    after = client.get("/me/capabilities", headers=_headers(member_token)).json()
    assert after["modes"]["organizer"] is False
    assert after["structures"] == []
    public = client.get(f"/profiles/{member_id}").json()
    assert public.get("affiliations", []) == []

    with get_session() as db:
        audit = db.query(AuditLog).filter(AuditLog.action == "organization.affiliation.revoke").one()
        assert audit.actor_user_id == owner_id


def test_pending_ended_revoked_affiliations_are_owner_only():
    token, user_id = _user("States")
    org_id = _organization(user_id, "States Org")
    now = now_utc()
    with get_session() as db:
        for status, suffix in (("PENDING", "pending"), ("LEFT", "ended"), ("REVOKED", "revoked")):
            org = Organization(
                name=f"Org {suffix}",
                slug=f"org-{suffix}",
                created_by_user_id=user_id,
            )
            db.add(org)
            db.flush()
            db.add(OrganizationMembership(
                organization_id=org.id,
                user_id=user_id,
                role="MEMBER",
                status=status,
                starts_at=now,
                joined_at=now,
                revoked_at=now if status == "REVOKED" else None,
                visibility="PUBLIC",
                validation_source="LEGACY",
                created_by_user_id=user_id,
            ))
        db.commit()
    _set_privacy(user_id, visibility="PUBLIC", affiliations_visibility="PUBLIC")

    owner_items = client.get("/me/affiliations", headers=_headers(token)).json()["items"]
    assert {item["status"] for item in owner_items} >= {"PENDING", "ENDED", "REVOKED"}
    public_items = client.get(f"/profiles/{user_id}").json().get("affiliations", [])
    assert public_items == []


def test_temporary_event_role_expires_and_guest_has_no_fake_capability():
    token, user_id = _user("Temporary")
    guest_token, _ = _user("Actual Guest", registered=False)
    with get_session() as db:
        event = Event(
            name="Temporary event",
            starts_at=now_utc(),
            ends_at=now_utc() + timedelta(hours=2),
        )
        db.add(event)
        db.flush()
        db.add(EventStaff(
            event_id=event.id,
            user_id=user_id,
            role="manager",
            is_active=True,
            expires_at=now_utc() - timedelta(seconds=1),
        ))
        db.commit()

    expired = client.get("/me/capabilities", headers=_headers(token)).json()
    assert expired["events"] == []
    assert expired["modes"]["organizer"] is False

    guest = client.get("/me/capabilities", headers=_headers(guest_token))
    assert guest.status_code == 200
    assert guest.json()["global_roles"] == []
    assert guest.json()["structures"] == []
    assert guest.json()["events"] == []
    assert guest.json()["bars"] == []
    assert guest.json()["modes"] == {"organizer": False, "bar": False}
    assert client.patch("/me/profile", headers=_headers(guest_token), json={"display_name": "No"}).status_code == 403


def test_expired_staff_and_revoked_affiliation_do_not_leak_private_events():
    token, user_id = _user("No Leak")
    owner_token, owner_id = _user("Host")
    org_id = _organization(owner_id, "Private Host")
    now = now_utc()
    with get_session() as db:
        org_event = Event(
            name="Revoked org event",
            host_type="orga",
            host_id=str(org_id),
            visibility="PRIVATE",
            publication_status="PUBLISHED",
            starts_at=now,
            ends_at=now + timedelta(hours=2),
        )
        staff_event = Event(
            name="Expired staff event",
            host_type="user",
            host_id=owner_id,
            visibility="PRIVATE",
            publication_status="PUBLISHED",
            starts_at=now,
            ends_at=now + timedelta(hours=2),
        )
        db.add_all([org_event, staff_event])
        db.flush()
        db.add(OrganizationMembership(
            organization_id=org_id,
            user_id=user_id,
            role="MANAGER",
            status="REVOKED",
            starts_at=now - timedelta(days=2),
            revoked_at=now - timedelta(minutes=1),
            joined_at=now - timedelta(days=2),
            validation_source="AUTHORIZED_APPROVAL",
            created_by_user_id=owner_id,
        ))
        db.add(EventStaff(
            event_id=staff_event.id,
            user_id=user_id,
            role="admin",
            is_active=True,
            expires_at=now - timedelta(minutes=1),
        ))
        db.commit()

    response = client.get("/me/events", headers=_headers(token))
    assert response.status_code == 200
    assert all(not items for items in response.json().values())
    capabilities = client.get("/me/capabilities", headers=_headers(token)).json()
    assert capabilities["structures"] == []
    assert capabilities["events"] == []
    assert capabilities["modes"] == {"organizer": False, "bar": False}


def test_server_side_preview_uses_real_visibility_rules():
    token, user_id = _user("Preview")
    _set_privacy(user_id, visibility="PRIVATE", bio_visibility="PUBLIC")
    public = client.get("/me/profile/preview?as=PUBLIC", headers=_headers(token))
    assert public.status_code == 200
    assert public.json() == {"visible": False, "profile": None, "viewer_context": "PUBLIC"}
    owner = client.get("/me/profile/preview?as=OWNER", headers=_headers(token))
    assert owner.status_code == 200
    assert owner.json()["visible"] is True
    assert owner.json()["profile"]["id"] == user_id


def test_admin_can_read_private_profile_and_revoke_affiliation():
    admin_token, admin_id = _user("Admin")
    member_token, member_id = _user("Private Member")
    org_id = _organization(admin_id, "Admin Org")
    now = now_utc()
    with get_session() as db:
        admin = db.get(AppUser, admin_id)
        admin.global_role = "ADMIN"
        membership = OrganizationMembership(
            organization_id=org_id,
            user_id=member_id,
            role="MEMBER",
            status="ACTIVE",
            starts_at=now,
            joined_at=now,
            visibility="PRIVATE",
            validation_source="AUTHORIZED_APPROVAL",
            created_by_user_id=admin_id,
        )
        db.add(membership)
        db.flush()
        affiliation_id = membership.id
        db.commit()
    _set_privacy(member_id, visibility="PRIVATE", affiliations_visibility="PRIVATE")

    assert client.get(f"/profiles/{member_id}", headers=_headers(admin_token)).status_code == 200
    revoked = client.post(
        f"/affiliations/{affiliation_id}/revoke",
        headers=_headers(admin_token),
        json={"reason": "Administrative revoke"},
    )
    assert revoked.status_code == 200
    assert client.get("/me/capabilities", headers=_headers(member_token)).json()["structures"] == []
    with get_session() as db:
        audit = db.query(AuditLog).filter(
            AuditLog.action == "organization.affiliation.revoke",
            AuditLog.entity_id == str(affiliation_id),
        ).one()
        assert audit.actor_user_id == admin_id
        assert audit.payload_json == {
            "organization_id": org_id,
            "reason": "Administrative revoke",
        }
