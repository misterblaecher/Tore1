from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from db import Base, engine, now_utc
from main import app
from models import Organization, OrganizationMembership


client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _guest(name: str) -> tuple[str, str]:
    response = client.post("/auth/guest", json={"display_name": name})
    assert response.status_code == 200
    token = response.json()["token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    return token, me.json()["id"]


def _headers(token: str, key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Idempotency-Key": key}


def test_forum_public_structure_and_private_scope_persist():
    owner_token, owner_id = _guest("forum-owner")
    outsider_token, _ = _guest("forum-outsider")
    created = client.post(
        "/orgas",
        json={"name": "Cercle Forum MVP", "city": "Liège", "org_type": "CIRCLE"},
        headers=_headers(owner_token, "forum-orga-create"),
    )
    assert created.status_code == 200
    structure = created.json()["orga"]
    slug = structure["slug"]

    public = client.get(f"/forum/structures/{slug}")
    assert public.status_code == 200
    assert public.json()["structure"]["name"] == "Cercle Forum MVP"
    assert public.json()["structure"]["city"] == "Liège"

    denied = client.get(f"/forum/structures/{slug}/dashboard", headers={"Authorization": f"Bearer {outsider_token}"})
    assert denied.status_code == 403

    dashboard = client.get(f"/forum/structures/{slug}/dashboard", headers={"Authorization": f"Bearer {owner_token}"})
    assert dashboard.status_code == 200
    assert dashboard.json()["membership"]["userId"] == owner_id

    discussion = client.post(
        f"/forum/structures/{slug}/discussions",
        json={"title": "Passation", "body": "Le document de passation est prêt."},
        headers=_headers(owner_token, "forum-discussion-1"),
    )
    assert discussion.status_code == 200
    refreshed = client.get(f"/forum/structures/{slug}/discussions", headers={"Authorization": f"Bearer {owner_token}"})
    assert refreshed.status_code == 200
    assert refreshed.json()["posts"][0]["title"] == "Passation"

    document = client.post(
        f"/forum/structures/{slug}/documents",
        json={"title": "PV", "file_url": "https://files.example/pv.pdf", "visibility": "STRUCTURE_MEMBERS"},
        headers=_headers(owner_token, "forum-document-1"),
    )
    assert document.status_code == 200
    assert client.get(f"/forum/structures/{slug}/documents", headers={"Authorization": f"Bearer {outsider_token}"}).status_code == 403

    album = client.post(
        f"/forum/structures/{slug}/albums",
        json={"title": "Rentrée"},
        headers=_headers(owner_token, "forum-album-1"),
    )
    assert album.status_code == 200
    assert album.json()["status"] == "DRAFT"

    audit = client.get(f"/forum/structures/{slug}/audit", headers={"Authorization": f"Bearer {owner_token}"})
    assert audit.status_code == 200
    actions = {item["action"] for item in audit.json()["items"]}
    assert "forum.discussion.create" in actions
    assert "forum.document.create" in actions
    assert "forum.album.create" in actions


def test_revoked_member_loses_forum_access():
    owner_token, _ = _guest("forum-owner-2")
    member_token, member_id = _guest("forum-member-2")
    created = client.post(
        "/orgas",
        json={"name": "Structure Accès", "org_type": "COMMITTEE"},
        headers=_headers(owner_token, "forum-orga-create-2"),
    )
    org_id = created.json()["orga"]["id"]
    slug = created.json()["orga"]["slug"]
    joined = client.post(f"/orgas/{org_id}/join", headers=_headers(member_token, "forum-join-2"))
    assert joined.status_code == 200
    assert client.get(f"/forum/structures/{slug}/dashboard", headers={"Authorization": f"Bearer {member_token}"}).status_code == 200

    revoked = client.delete(
        f"/forum/structures/{slug}/members/{member_id}?reason=fin%20de%20mandat",
        headers=_headers(owner_token, "forum-revoke-2"),
    )
    assert revoked.status_code == 200
    assert client.get(f"/forum/structures/{slug}/dashboard", headers={"Authorization": f"Bearer {member_token}"}).status_code == 403


def test_navigation_returns_only_current_authorized_structures_and_their_logos():
    token, user_id = _guest("sidebar-member")
    other_token, other_id = _guest("sidebar-outsider")
    stamp = now_utc()
    cases = [
        ("managed", user_id, "PRESIDENT", "ACTIVE", None, None, None),
        ("member", user_id, "MEMBER", "ACTIVE", stamp - timedelta(days=1), stamp + timedelta(days=1), None),
        ("treasury", user_id, "TREASURER", "ACTIVE", None, None, None),
        ("expired", user_id, "OWNER", "ACTIVE", None, stamp - timedelta(seconds=1), None),
        ("future", user_id, "OWNER", "ACTIVE", stamp + timedelta(days=1), None, None),
        ("pending", user_id, "OWNER", "PENDING", None, None, None),
        ("revoked", user_id, "OWNER", "ACTIVE", None, None, stamp),
        ("former", user_id, "ANCIEN", "ACTIVE", None, None, None),
        ("other-account", other_id, "OWNER", "ACTIVE", None, None, None),
    ]
    with Session(engine) as db:
        for slug, account_id, role, status, starts_at, ends_at, revoked_at in cases:
            org = Organization(name=slug, slug=slug, city="Liège", org_type="COMMITTEE", logo_url=f"https://example.test/{slug}.png", visibility="PRIVATE", created_by_user_id=account_id)
            db.add(org)
            db.flush()
            db.add(OrganizationMembership(organization_id=org.id, user_id=account_id, role=role, status=status, starts_at=starts_at, ends_at=ends_at, revoked_at=revoked_at, created_by_user_id=account_id))
        db.commit()

    assert client.get("/forum/me/structures").status_code == 401
    response = client.get("/forum/me/structures", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    items = {item["slug"]: item for item in response.json()["items"]}
    assert set(items) == {"managed", "member", "treasury"}
    assert items["managed"]["logoUrl"] == "https://example.test/managed.png"
    assert items["managed"]["city"] == "Liège"
    assert items["managed"]["canManage"] is True
    assert items["member"]["canManage"] is False
    assert items["member"]["canReadFinance"] is False
    assert items["treasury"]["canReadFinance"] is True
    assert items["treasury"]["canManage"] is False
    other_response = client.get("/forum/me/structures", headers={"Authorization": f"Bearer {other_token}"})
    assert [item["slug"] for item in other_response.json()["items"]] == ["other-account"]
