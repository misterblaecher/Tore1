from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import AuditLog, Event, Organization


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


def _create(owner_token: str, key: str = "lifecycle-create") -> dict:
    response = client.post(
        "/orgas",
        json={
            "name": "Structure lifecycle",
            "city": "Liège",
            "org_type": "COMMITTEE",
            # Legacy clients may still send PUBLIC; the server must ignore it on creation.
            "visibility": "PUBLIC",
        },
        headers=_headers(owner_token, key),
    )
    assert response.status_code == 200
    return response.json()["orga"]


def test_creation_is_setup_private_with_all_blocks_private_and_outsider_gets_nothing():
    owner_token, _ = _guest("lifecycle-owner")
    outsider_token, _ = _guest("lifecycle-outsider")
    org = _create(owner_token)

    assert org["lifecycle"] == "SETUP"
    assert org["visibility"] == "PRIVATE"

    lifecycle = client.get(
        f"/forum/structures/{org['slug']}/lifecycle",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert lifecycle.status_code == 200
    assert lifecycle.json()["lifecycle"] == "SETUP"
    assert lifecycle.json()["published"] is False
    assert lifecycle.json()["visibilitySettings"] == {
        "page": "PRIVATE",
        "description": "PRIVATE",
        "contact": "PRIVATE",
        "events": "PRIVATE",
        "members": "PRIVATE",
        "albums": "PRIVATE",
        "documents": "PRIVATE",
        "folklore": "PRIVATE",
        "stats": "PRIVATE",
    }

    assert client.get(f"/forum/structures/{org['slug']}").status_code == 404
    assert client.get(f"/orgas/{org['id']}").status_code == 404
    assert client.get(
        f"/orgas/{org['id']}", headers={"Authorization": f"Bearer {outsider_token}"}
    ).status_code == 404

    owner_view = client.get(
        f"/orgas/{org['id']}", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert owner_view.status_code == 200
    assert owner_view.json()["lifecycle"] == "SETUP"


def test_explicit_publish_exposes_shell_but_never_private_content_then_unpublish_hides_again():
    owner_token, _ = _guest("publish-owner")
    org = _create(owner_token, "publish-create")
    slug = org["slug"]

    document = client.post(
        f"/forum/structures/{slug}/documents",
        json={
            "title": "PV privé",
            "file_url": "https://files.example/private.pdf",
            "visibility": "STRUCTURE_MEMBERS",
        },
        headers=_headers(owner_token, "publish-private-document"),
    )
    assert document.status_code == 200

    album = client.post(
        f"/forum/structures/{slug}/albums",
        json={"title": "Album privé", "visibility": "STRUCTURE_MEMBERS"},
        headers=_headers(owner_token, "publish-private-album"),
    )
    assert album.status_code == 200

    published = client.post(
        f"/forum/structures/{slug}/publish",
        json={"reason": "Publication volontaire"},
        headers=_headers(owner_token, "structure-publish"),
    )
    assert published.status_code == 200
    assert published.json()["lifecycle"] == "ACTIVE"
    assert published.json()["published"] is True

    public = client.get(f"/forum/structures/{slug}")
    assert public.status_code == 200
    payload = public.json()
    assert payload["structure"]["name"] == "Structure lifecycle"
    assert payload["documents"] == []
    assert payload["albums"] == []
    assert payload["members"] == []
    assert payload["events"] == []
    assert payload["pages"] == []
    assert payload["stats"] is None
    assert payload["structure"]["description"] is None
    assert "contactEmail" not in payload["structure"]

    unpublished = client.post(
        f"/forum/structures/{slug}/unpublish",
        json={"reason": "Retour en privé"},
        headers=_headers(owner_token, "structure-unpublish"),
    )
    assert unpublished.status_code == 200
    assert unpublished.json()["lifecycle"] == "ACTIVE"
    assert unpublished.json()["published"] is False
    assert client.get(f"/forum/structures/{slug}").status_code == 404


def test_invalid_transitions_are_rejected_and_suspended_archived_structures_cannot_leak_events():
    owner_token, _ = _guest("transition-owner")
    org = _create(owner_token, "transition-create")
    slug = org["slug"]

    invalid_archive = client.post(
        f"/forum/structures/{slug}/archive",
        json={"reason": "Impossible directement"},
        headers=_headers(owner_token, "transition-invalid-archive"),
    )
    assert invalid_archive.status_code == 409
    assert invalid_archive.json()["detail"]["reason"] == "INVALID_LIFECYCLE_TRANSITION"

    published = client.post(
        f"/forum/structures/{slug}/publish",
        json={"reason": "Activation explicite"},
        headers=_headers(owner_token, "transition-publish"),
    )
    assert published.status_code == 200

    event = client.post(
        f"/forum/structures/{slug}/events",
        json={
            "name": "Event public avant suspension",
            "starts_at": "2030-01-01T18:00:00Z",
            "ends_at": "2030-01-01T22:00:00Z",
            "visibility": "PUBLIC",
            "publication_status": "PUBLISHED",
        },
        headers=_headers(owner_token, "transition-event-create"),
    )
    assert event.status_code == 200

    suspended = client.post(
        f"/forum/structures/{slug}/suspend",
        json={"reason": "Suspension de sécurité"},
        headers=_headers(owner_token, "transition-suspend"),
    )
    assert suspended.status_code == 200
    assert suspended.json()["lifecycle"] == "SUSPENDED"
    assert suspended.json()["published"] is False
    assert client.get(f"/forum/structures/{slug}").status_code == 404

    with get_session() as db:
        structure = db.query(Organization).filter(Organization.slug == slug).one()
        rows = db.query(Event).filter(Event.host_type == "orga", Event.host_id == str(structure.id)).all()
        assert rows
        assert all((row.visibility or "").upper() == "PRIVATE" for row in rows)
        assert all((row.publication_status or "").upper() == "DRAFT" for row in rows)

    cannot_publish = client.post(
        f"/forum/structures/{slug}/publish",
        json={"reason": "Publication invalide"},
        headers=_headers(owner_token, "transition-republish-suspended"),
    )
    assert cannot_publish.status_code == 409

    archived = client.post(
        f"/forum/structures/{slug}/archive",
        json={"reason": "Archivage final"},
        headers=_headers(owner_token, "transition-archive"),
    )
    assert archived.status_code == 200
    assert archived.json()["lifecycle"] == "ARCHIVED"
    assert archived.json()["published"] is False
    assert client.get(f"/forum/structures/{slug}").status_code == 404


def test_lifecycle_mutations_are_audited():
    owner_token, _ = _guest("audit-lifecycle-owner")
    org = _create(owner_token, "audit-lifecycle-create")
    slug = org["slug"]

    assert client.post(
        f"/forum/structures/{slug}/publish",
        json={"reason": "Audit publish"},
        headers=_headers(owner_token, "audit-lifecycle-publish"),
    ).status_code == 200
    assert client.post(
        f"/forum/structures/{slug}/unpublish",
        json={"reason": "Audit unpublish"},
        headers=_headers(owner_token, "audit-lifecycle-unpublish"),
    ).status_code == 200
    assert client.post(
        f"/forum/structures/{slug}/suspend",
        json={"reason": "Audit suspend"},
        headers=_headers(owner_token, "audit-lifecycle-suspend"),
    ).status_code == 200
    assert client.post(
        f"/forum/structures/{slug}/archive",
        json={"reason": "Audit archive"},
        headers=_headers(owner_token, "audit-lifecycle-archive"),
    ).status_code == 200

    with get_session() as db:
        actions = {
            row.action
            for row in db.query(AuditLog).filter(AuditLog.entity_type == "organization").all()
        }
    assert "organization.create" in actions
    assert f"forum.structure.publish:{org['id']}" in actions
    assert f"forum.structure.unpublish:{org['id']}" in actions
    assert f"forum.structure.suspend:{org['id']}" in actions
    assert f"forum.structure.archive:{org['id']}" in actions
