from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from db import Base, engine, now_utc
from main import app
from models import AppUser, Event, EventStructure, Organization, StoredFile
from app.services.operational_access_service import event_capabilities


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


def _structure(token: str, name: str, key: str) -> dict:
    response = client.post(
        "/orgas",
        json={"name": name, "city": "Liège", "org_type": "COMMITTEE"},
        headers=_headers(token, key),
    )
    assert response.status_code == 200
    return response.json()["orga"]


def _permissions(**overrides) -> dict[str, bool]:
    base = {"edit": False, "publish": False, "staff": False, "documents": False, "finance": False, "recap": False}
    base.update(overrides)
    return base


def test_publication_requires_active_owner_and_persists_after_activation():
    token, _ = _guest("publication-lifecycle-owner")
    org = _structure(token, "Publication lifecycle", "publication-lifecycle")
    base = f"/forum/structures/{org['slug']}"
    created = client.post(f"{base}/event-manager", json={
        "name": "Lifecycle event",
        "starts_at": (now_utc() + timedelta(days=2)).isoformat(),
        "ends_at": (now_utc() + timedelta(days=2, hours=3)).isoformat(),
    }, headers=_headers(token))
    assert created.status_code == 201
    path = f"{base}/event-manager/{created.json()['id']}"
    for patch in ({"visibility": "PUBLIC"}, {"publication_status": "PUBLISHED", "visibility": "PUBLIC"}):
        blocked = client.patch(path, json=patch, headers=_headers(token))
        assert blocked.status_code == 409
        assert "SETUP" in blocked.json()["detail"]
    activated = client.post(f"{base}/publish", json={"reason": "Publication de la structure"}, headers=_headers(token, "activate-publication-lifecycle"))
    assert activated.status_code == 200
    published = client.patch(path, json={"publication_status": "PUBLISHED", "visibility": "PUBLIC"}, headers=_headers(token))
    assert published.status_code == 200
    detail = client.get(path, headers=_headers(token)).json()
    assert detail["visibility"] == "PUBLIC"
    assert detail["publicationStatus"] == "PUBLISHED"


def test_cohost_permissions_are_explicit_and_finance_never_leaks():
    owner_token, owner_user_id = _guest("event-owner")
    cohost_token, cohost_user_id = _guest("event-cohost")
    owner = _structure(owner_token, "Owner Structure", "owner-structure")
    cohost = _structure(cohost_token, "Cohost Structure", "cohost-structure")
    published_owner = client.post(
        f"/forum/structures/{owner['slug']}/publish",
        json={"reason": "Publication explicite avant publication de l'événement"},
        headers=_headers(owner_token, "publish-owner-structure"),
    )
    assert published_owner.status_code == 200

    created = client.post(
        f"/forum/structures/{owner['slug']}/event-manager",
        json={
            "name": "Soirée co-organisée",
            "description": "Description riche",
            "starts_at": (now_utc() + timedelta(days=2)).isoformat(),
            "ends_at": (now_utc() + timedelta(days=2, hours=6)).isoformat(),
            "venue": "Le Carré",
            "city": "Liège",
            "capacity": 450,
            "entry_price_cents": 600,
            "tariffs": [{"label": "Membre", "price_cents": 400}, {"label": "Public", "price_cents": 600}],
            "modules_on": {"entry": True, "broadcast": True},
            "visibility": "PRIVATE",
            "publication_status": "DRAFT",
        },
        headers=_headers(owner_token),
    )
    assert created.status_code == 201
    event_id = created.json()["id"]
    assert created.json()["capacity"] == 450
    assert created.json()["tariffs"][0]["label"] == "Membre"
    assert created.json()["eventState"] == "DRAFT"

    added = client.post(
        f"/forum/structures/{owner['slug']}/event-manager/{event_id}/cohosts",
        json={"structure_id": cohost["id"], "permissions": _permissions()},
        headers=_headers(owner_token),
    )
    assert added.status_code == 201
    assert added.json()["role"] == "COHOST"
    assert added.json()["permissions"]["finance"] is False

    detail = client.get(
        f"/forum/structures/{cohost['slug']}/event-manager/{event_id}",
        headers=_headers(cohost_token),
    )
    assert detail.status_code == 200
    assert detail.json()["finance"] is None
    assert detail.json()["canReadFinance"] is False
    assert detail.json()["staff"] is None
    assert detail.json()["documents"] is None
    assert detail.json()["albums"] is None

    denied_calls = [
        client.patch(
            f"/forum/structures/{cohost['slug']}/event-manager/{event_id}",
            json={"name": "Interdit"}, headers=_headers(cohost_token),
        ),
        client.patch(
            f"/forum/structures/{cohost['slug']}/event-manager/{event_id}",
            json={"publication_status": "PUBLISHED"}, headers=_headers(cohost_token),
        ),
        client.get(
            f"/forum/structures/{cohost['slug']}/event-manager/{event_id}/finance",
            headers=_headers(cohost_token),
        ),
        client.post(
            f"/forum/structures/{cohost['slug']}/event-manager/{event_id}/documents",
            json={"title": "Budget", "file_id": "missing-file"}, headers=_headers(cohost_token),
        ),
        client.post(
            f"/forum/structures/{cohost['slug']}/event-manager/{event_id}/albums",
            json={"title": "Recap"}, headers=_headers(cohost_token),
        ),
        client.post(
            f"/forum/structures/{cohost['slug']}/event-manager/{event_id}/staff-invitations",
            json={"target_user_id": owner_user_id, "role": "HELPER"},
            headers=_headers(cohost_token, "staff-denied"),
        ),
    ]
    assert all(response.status_code == 403 for response in denied_calls)

    granted = _permissions(edit=True, publish=True, staff=True, documents=True, finance=False, recap=True)
    updated = client.patch(
        f"/forum/structures/{owner['slug']}/event-manager/{event_id}/cohosts/{cohost['id']}",
        json={"permissions": granted}, headers=_headers(owner_token),
    )
    assert updated.status_code == 200
    assert updated.json()["permissions"] == granted

    edited = client.patch(
        f"/forum/structures/{cohost['slug']}/event-manager/{event_id}",
        json={"name": "Soirée éditée par le cohost"}, headers=_headers(cohost_token),
    )
    assert edited.status_code == 200
    published = client.patch(
        f"/forum/structures/{cohost['slug']}/event-manager/{event_id}",
        json={"publication_status": "PUBLISHED"}, headers=_headers(cohost_token),
    )
    assert published.status_code == 200
    assert published.json()["publicationStatus"] == "PUBLISHED"
    assert published.json()["finance"] is None
    assert client.get(
        f"/forum/structures/{cohost['slug']}/event-manager/{event_id}/finance",
        headers=_headers(cohost_token),
    ).status_code == 403

    with Session(engine) as db:
        db.add(StoredFile(
            id="cohost-document-file",
            owner_user_id=cohost_user_id,
            organization_id=cohost["id"],
            original_name="checklist.pdf",
            mime_type="application/pdf",
            size_bytes=123,
            storage_key="private/cohost/checklist.pdf",
            storage_backend="local",
            visibility="PRIVATE",
            checksum_sha256="a" * 64,
            purpose="DOCUMENT",
        ))
        db.commit()
        cohost_user = db.get(AppUser, cohost_user_id)
        capability = next(item for item in event_capabilities(db, cohost_user) if item["event_id"] == event_id)
        assert "event.manage_staff" in capability["actions"]
        assert capability["source"] == "EVENT_COHOST"

    document = client.post(
        f"/forum/structures/{cohost['slug']}/event-manager/{event_id}/documents",
        json={"title": "Checklist cohost", "file_id": "cohost-document-file"},
        headers=_headers(cohost_token),
    )
    assert document.status_code == 201
    album = client.post(
        f"/forum/structures/{cohost['slug']}/event-manager/{event_id}/albums",
        json={"title": "Recap cohost"}, headers=_headers(cohost_token),
    )
    assert album.status_code == 201

    finance_enabled = _permissions(edit=True, publish=True, staff=True, documents=True, finance=True, recap=True)
    assert client.patch(
        f"/forum/structures/{owner['slug']}/event-manager/{event_id}/cohosts/{cohost['id']}",
        json={"permissions": finance_enabled}, headers=_headers(owner_token),
    ).status_code == 200
    finance = client.get(
        f"/forum/structures/{cohost['slug']}/event-manager/{event_id}/finance",
        headers=_headers(cohost_token),
    )
    assert finance.status_code == 200
    assert finance.json()["canReadFinance"] is True

    audit = client.get(f"/forum/structures/{owner['slug']}/audit", headers=_headers(owner_token))
    assert audit.status_code == 200
    actions = {item["action"] for item in audit.json()["items"]}
    assert "event.cohost.add" in actions
    assert "event.cohost.permissions" in actions
    assert "event.manager.create" in actions


def test_legacy_co_organizers_are_migrated_without_permissions():
    owner_token, _ = _guest("legacy-owner")
    cohost_token, _ = _guest("legacy-cohost")
    owner = _structure(owner_token, "Legacy Owner", "legacy-owner-structure")
    cohost = _structure(cohost_token, "Legacy Cohost", "legacy-cohost-structure")

    with Session(engine) as db:
        event = Event(
            host_type="orga",
            host_id=str(owner["id"]),
            host_display_name=owner["name"],
            name="Legacy co-organized event",
            starts_at=now_utc() + timedelta(days=1),
            ends_at=now_utc() + timedelta(days=1, hours=5),
            event_state="DRAFT",
            rules_flags={"co_organizers": [cohost["slug"], "Structure introuvable"]},
            visibility="PRIVATE",
            publication_status="DRAFT",
        )
        db.add(event)
        db.commit()
        event_id = event.id

    owner_list = client.get(
        f"/forum/structures/{owner['slug']}/event-manager", headers=_headers(owner_token)
    )
    assert owner_list.status_code == 200
    assert any(item["id"] == event_id for item in owner_list.json()["items"])

    with Session(engine) as db:
        relation = db.query(EventStructure).filter(
            EventStructure.event_id == event_id,
            EventStructure.organization_id == cohost["id"],
        ).one()
        assert relation.role == "COHOST"
        assert relation.can_edit is False
        assert relation.can_publish is False
        assert relation.can_staff is False
        assert relation.can_documents is False
        assert relation.can_finance is False
        assert relation.can_recap is False
        migrated_event = db.get(Event, event_id)
        assert "co_organizers" not in (migrated_event.rules_flags or {})
        assert migrated_event.rules_flags["legacy_unresolved_co_organizers"] == ["Structure introuvable"]

    detail = client.get(
        f"/forum/structures/{cohost['slug']}/event-manager/{event_id}", headers=_headers(cohost_token)
    )
    assert detail.status_code == 200
    assert detail.json()["finance"] is None
    assert detail.json()["canReadFinance"] is False
    assert client.get(
        f"/forum/structures/{cohost['slug']}/event-manager/{event_id}/finance", headers=_headers(cohost_token)
    ).status_code == 403
