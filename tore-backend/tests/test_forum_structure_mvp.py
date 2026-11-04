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


def _headers(token: str, key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if key:
        headers["Idempotency-Key"] = key
    return headers


def _publish(token: str, slug: str, key: str) -> None:
    response = client.post(
        f"/forum/structures/{slug}/publish",
        json={"reason": "Publication explicite du test"},
        headers=_headers(token, key),
    )
    assert response.status_code == 200


def test_forum_and_mobile_share_published_structures_and_events():
    token, _ = _guest("shared-owner")
    created = client.post("/orgas", json={
        "name": "Comité synchronisé", "city": "Liège", "org_type": "COMMITTEE",
    }, headers=_headers(token, "shared-structure"))
    assert created.status_code == 200
    org = created.json()["orga"]
    slug = org["slug"]
    _publish(token, slug, "shared-structure-publish")
    visible_events = client.patch(f"/forum/structures/{slug}/visibility",
        json={"events": "PUBLIC"}, headers=_headers(token, "shared-events-visible"))
    assert visible_events.status_code == 200
    mobile_structures = client.get("/orgas", params={"q": "Comité synchronisé"})
    assert mobile_structures.status_code == 200
    assert any(item["id"] == org["id"] for item in mobile_structures.json()["items"])
    public_structure = client.get(f"/forum/structures/{slug}").json()
    assert public_structure["structure"]["id"] == org["id"]

    created_event = client.post(f"/forum/structures/{slug}/events", json={
        "name": "Soirée synchronisée", "city": "Liège",
        "starts_at": "2030-01-01T18:00:00Z", "ends_at": "2030-01-01T22:00:00Z",
    }, headers=_headers(token, "shared-event"))
    assert created_event.status_code == 200
    event_id = created_event.json()["id"]
    params = {"city": "Liège", "structure_id": org["id"]}
    assert client.get("/events", params=params).json() == []
    published = client.patch(f"/forum/structures/{slug}/events/{event_id}",
        json={"publication_status": "PUBLISHED", "visibility": "PUBLIC"},
        headers=_headers(token, "shared-event-publish"))
    assert published.status_code == 200
    mobile_events = client.get("/events", params=params)
    assert mobile_events.status_code == 200
    assert [event["id"] for event in mobile_events.json()] == [event_id]
    assert client.get("/events", params={**params, "city": "Namur"}).json() == []
    edited = client.patch(f"/forum/structures/{slug}/events/{event_id}",
        json={"name": "Soirée mise à jour"}, headers=_headers(token, "shared-edit"))
    assert edited.status_code == 200
    assert client.get("/events", params=params).json()[0]["name"] == "Soirée mise à jour"
    forum_events = client.get(f"/forum/structures/{slug}").json()["events"]
    assert any(event["id"] == event_id and event["name"] == "Soirée mise à jour" for event in forum_events)
    unpublished = client.patch(f"/forum/structures/{slug}/events/{event_id}",
        json={"publication_status": "DRAFT"}, headers=_headers(token, "shared-unpublish"))
    assert unpublished.status_code == 200
    assert client.get("/events", params=params).json() == []
    assert not any(event["id"] == event_id for event in client.get(f"/forum/structures/{slug}").json()["events"])


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
    assert structure["lifecycle"] == "SETUP"
    assert structure["visibility"] == "PRIVATE"

    assert client.get(f"/forum/structures/{slug}").status_code == 404
    _publish(owner_token, slug, "forum-orga-publish")
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


def test_structure_documents_and_events_are_isolated_and_persisted():
    owner_a, _ = _guest("forum-isolation-a")
    owner_b, _ = _guest("forum-isolation-b")
    created_a = client.post("/orgas", json={"name": "Structure A documents", "org_type": "COMMITTEE"}, headers=_headers(owner_a, "isolation-orga-a"))
    created_b = client.post("/orgas", json={"name": "Structure B documents", "org_type": "COMMITTEE"}, headers=_headers(owner_b, "isolation-orga-b"))
    assert created_a.status_code == 200 and created_b.status_code == 200
    slug_a = created_a.json()["orga"]["slug"]
    slug_b = created_b.json()["orga"]["slug"]
    _publish(owner_a, slug_a, "isolation-publish-a")

    document_b = client.post(
        f"/forum/structures/{slug_b}/documents",
        json={"title": "B privé", "file_url": "https://files.example/b.pdf", "visibility": "STRUCTURE_MEMBERS"},
        headers=_headers(owner_b, "isolation-doc-b"),
    )
    assert document_b.status_code == 200
    assert client.get(f"/forum/structures/{slug_b}/documents", headers={"Authorization": f"Bearer {owner_a}"}).status_code == 403
    assert client.post(
        f"/forum/structures/{slug_b}/documents",
        json={"title": "Écriture étrangère", "file_url": "https://files.example/a.pdf"},
        headers=_headers(owner_a, "isolation-doc-write"),
    ).status_code == 403
    assert client.get(
        f"/forum/structures/{slug_b}/stats",
        headers={"Authorization": f"Bearer {owner_a}"},
    ).status_code == 403

    event = client.post(
        f"/forum/structures/{slug_a}/events",
        json={"name": "Événement A", "starts_at": "2030-01-01T18:00:00Z", "ends_at": "2030-01-01T22:00:00Z", "description": "Publication de test"},
        headers=_headers(owner_a, "isolation-event-create"),
    )
    assert event.status_code == 200
    event_id = event.json()["id"]
    published = client.patch(
        f"/forum/structures/{slug_a}/events/{event_id}",
        json={"publication_status": "PUBLISHED", "visibility": "PUBLIC"},
        headers=_headers(owner_a, "isolation-event-publish"),
    )
    assert published.status_code == 200
    assert client.get(f"/forum/structures/{slug_a}/events", headers={"Authorization": f"Bearer {owner_a}"}).json()["items"][0]["publicationStatus"] == "PUBLISHED"
    assert client.get(f"/forum/structures/{slug_b}/events", headers={"Authorization": f"Bearer {owner_a}"}).status_code == 403

    page = client.post(
        f"/forum/structures/{slug_a}/pages",
        json={"title": "Histoire A", "content": "Mémoire privée", "category": "HISTORY", "visibility": "STRUCTURE_MEMBERS"},
        headers=_headers(owner_a, "isolation-page-create"),
    )
    assert page.status_code == 200
    page_id = page.json()["id"]
    assert client.get(f"/forum/structures/{slug_a}/pages", headers={"Authorization": f"Bearer {owner_a}"}).json()["items"][0]["title"] == "Histoire A"
    assert client.get(f"/forum/structures/{slug_a}/pages", headers={"Authorization": f"Bearer {owner_b}"}).status_code == 403
    published_page = client.patch(
        f"/forum/structures/{slug_a}/pages/{page_id}",
        json={"content": "Mémoire publiée", "published": True},
        headers=_headers(owner_a, "isolation-page-publish"),
    )
    assert published_page.status_code == 200
    assert published_page.json()["publishedAt"] is not None


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


def test_portal_settings_roundtrip_permissions_and_public_visibility():
    token, owner_id = _guest("portal-owner")
    outsider_token, _ = _guest("portal-outsider")
    created = client.post("/orgas", json={"name": "Portail de test", "org_type": "COMMITTEE"}, headers=_headers(token, "portal-create"))
    slug = created.json()["orga"]["slug"]
    path = f"/forum/structures/{slug}/settings"
    payload = {
        "org_type": "BAR", "logo_url": "https://example.test/logo.png",
        "history": "Histoire publiée", "sponsors": ["Partenaire déclaré"],
        "portal": {"about": "Présentation détaillée", "opening_hours": "Lundi : 16h–01h", "services": ["Concerts"], "announcement": "Nouvelle saison", "hidden_blocks": ["gallery"]},
    }
    assert client.patch(path, json=payload, headers=_headers(outsider_token, "portal-denied")).status_code == 403
    saved = client.patch(path, json=payload, headers=_headers(token, "portal-save"))
    assert saved.status_code == 200
    assert saved.json()["portal"]["services"] == ["Concerts"]
    assert client.get(path, headers={"Authorization": f"Bearer {token}"}).json()["portal"]["hidden_blocks"] == ["gallery"]
    _publish(token, slug, "portal-publish")
    # Current team must exclude ended mandates, even if their status still says ACTIVE.
    with Session(engine) as db:
        org = db.query(Organization).filter(Organization.slug == slug).one()
        org.visibility_settings_json = {"page": "PUBLIC", "description": "PRIVATE", "contact": "PRIVATE", "folklore": "PRIVATE", "members": "PUBLIC"}
        membership = db.query(OrganizationMembership).filter(OrganizationMembership.organization_id == org.id, OrganizationMembership.user_id == owner_id).one()
        membership.visibility = "PUBLIC"
        membership.ends_at = now_utc() - timedelta(days=1)
        db.commit()
    public = client.get(f"/forum/structures/{slug}").json()
    assert public["members"] == []
    assert not public["structure"].get("history")
    assert not public["structure"].get("sponsors")
    assert public["structure"]["portal"]["about"] == ""
    assert public["structure"]["portal"]["opening_hours"] == ""
    assert public["structure"]["portal"]["services"] == []
    assert public["structure"]["portal"]["announcement"] == ""
    assert public["structure"]["logoUrl"] == "https://example.test/logo.png"
