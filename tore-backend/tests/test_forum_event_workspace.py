from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from db import Base, engine
from main import app
from models import EventRuntimeState


client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _guest(name: str) -> tuple[str, str]:
    response = client.post("/auth/guest", json={"display_name": name})
    assert response.status_code == 200
    token = response.json()["token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    return token, me.json()["id"]


def _headers(token: str, key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Idempotency-Key": key}


def _structure(token: str, name: str, key: str) -> str:
    response = client.post(
        "/orgas",
        json={"name": name, "city": "Liège", "org_type": "COMMITTEE"},
        headers=_headers(token, key),
    )
    assert response.status_code == 200
    return response.json()["orga"]["slug"]


def test_rich_event_fields_persist_and_draft_is_not_live():
    token, _ = _guest("workspace-owner")
    slug = _structure(token, "Workspace Event", "workspace-org")
    created = client.post(
        f"/forum/structures/{slug}/event-workspace",
        json={
            "name": "Bal complet",
            "starts_at": "2030-02-01T19:00:00Z",
            "ends_at": "2030-02-02T03:00:00Z",
            "venue": "Le Carré",
            "city": "Liège",
            "description": "Description serveur",
            "capacity": 420,
            "entry_price_cents": 750,
            "banner_url": "https://example.test/cover.jpg",
            "modules": ["entry", "music", "photos"],
            "co_organizers": ["Cercle A", "Comité B"],
            "recap": "Récap privé en préparation",
            "visibility": "PRIVATE",
            "publication_status": "DRAFT",
        },
        headers=_headers(token, "workspace-event-create"),
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["capacity"] == 420
    assert body["entryPriceCents"] == 750
    assert body["coverUrl"] == "https://example.test/cover.jpg"
    assert body["modules"] == ["entry", "music", "photos"]
    assert body["coOrganizers"] == ["Cercle A", "Comité B"]
    assert body["recap"] == "Récap privé en préparation"
    assert body["lifecycleStatus"] == "DRAFT"
    event_id = body["id"]

    with Session(engine) as db:
        runtime = db.query(EventRuntimeState).filter(EventRuntimeState.event_id == event_id).one()
        assert runtime.state == "DRAFT"

    refreshed = client.get(
        f"/forum/structures/{slug}/event-workspace",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["items"][0]["recap"] == "Récap privé en préparation"
    assert refreshed.json()["items"][0]["coOrganizers"] == ["Cercle A", "Comité B"]

    # Publishing an event must never publish its owning structure implicitly.
    assert client.get(f"/forum/structures/{slug}").status_code == 404
    structure_published = client.post(
        f"/forum/structures/{slug}/publish",
        json={"reason": "Publication explicite avant publication de l’event"},
        headers=_headers(token, "workspace-structure-publish"),
    )
    assert structure_published.status_code == 200
    assert structure_published.json()["published"] is True

    published = client.patch(
        f"/forum/structures/{slug}/event-workspace/{event_id}",
        json={"visibility": "PUBLIC", "lifecycle_status": "PUBLISHED"},
        headers=_headers(token, "workspace-event-publish"),
    )
    assert published.status_code == 200
    assert published.json()["publicationStatus"] == "PUBLISHED"
    public = client.get(f"/forum/structures/{slug}")
    assert public.status_code == 200
    public_event = public.json()["events"][0]
    assert public_event["name"] == "Bal complet"
    assert "recap" not in public_event
    assert "coOrganizers" not in public_event


def test_event_workspace_enforces_structure_isolation_and_transition_order():
    owner_a, _ = _guest("workspace-a")
    owner_b, _ = _guest("workspace-b")
    slug_a = _structure(owner_a, "Workspace A", "workspace-a-org")
    slug_b = _structure(owner_b, "Workspace B", "workspace-b-org")

    event = client.post(
        f"/forum/structures/{slug_a}/event-workspace",
        json={
            "name": "Event A",
            "starts_at": "2031-01-01T18:00:00Z",
            "ends_at": "2031-01-01T22:00:00Z",
        },
        headers=_headers(owner_a, "workspace-a-event"),
    )
    assert event.status_code == 200
    event_id = event.json()["id"]

    assert client.get(
        f"/forum/structures/{slug_b}/event-workspace",
        headers={"Authorization": f"Bearer {owner_a}"},
    ).status_code == 403

    # The historical /forum scope helper answers 400 when an event exists but is
    # outside the URL structure. The important invariant is that the mutation is
    # rejected and the owning structure still reads the original value.
    cross_tenant = client.patch(
        f"/forum/structures/{slug_b}/event-workspace/{event_id}",
        json={"description": "Tentative cross-tenant"},
        headers=_headers(owner_b, "workspace-cross-tenant"),
    )
    assert cross_tenant.status_code == 400
    owner_view = client.get(
        f"/forum/structures/{slug_a}/event-workspace",
        headers={"Authorization": f"Bearer {owner_a}"},
    )
    assert owner_view.status_code == 200
    assert owner_view.json()["items"][0]["description"] != "Tentative cross-tenant"

    invalid = client.patch(
        f"/forum/structures/{slug_a}/event-workspace/{event_id}",
        json={"lifecycle_status": "LIVE"},
        headers=_headers(owner_a, "workspace-invalid-transition"),
    )
    assert invalid.status_code == 409
    assert invalid.json()["detail"]["reason"] == "INVALID_EVENT_TRANSITION"
