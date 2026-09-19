from datetime import timedelta

from fastapi.testclient import TestClient

from db import Base, SessionLocal, engine, now_utc
from main import app
from models import Event
from app.routers.forum_events import _event_slug, _is_public_event


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


def _create_structure(token: str, key: str, name: str = "Structure Event Public") -> dict:
    response = client.post(
        "/orgas",
        json={"name": name, "city": "Liège", "org_type": "COMMITTEE"},
        headers=_headers(token, key),
    )
    assert response.status_code == 200
    return response.json()["orga"]


def _create_event(
    token: str,
    structure_slug: str,
    *,
    key: str,
    visibility: str = "PUBLIC",
    name: str = "Recap Night",
) -> dict:
    now = now_utc()
    response = client.post(
        f"/forum/structures/{structure_slug}/events",
        json={
            "name": name,
            "starts_at": (now - timedelta(hours=3)).isoformat(),
            "ends_at": (now - timedelta(hours=1)).isoformat(),
            "venue": "Le Carré",
            "city": "Liège",
            "description": "Une soirée publique TORÈ.",
            "visibility": visibility,
            "publication_status": "PUBLISHED",
            "entry_price_cents": 500,
        },
        headers=_headers(token, key),
    )
    assert response.status_code == 200
    return response.json()


def test_public_event_page_keeps_recap_private_until_explicit_publish():
    owner_token, _ = _guest("event-page-owner")
    outsider_token, _ = _guest("event-page-outsider")
    structure = _create_structure(owner_token, "event-page-orga")
    published_structure = client.post(
        f"/forum/structures/{structure['slug']}/publish",
        json={"reason": "Publication explicite avant publication de l'événement"},
        headers=_headers(owner_token, "event-page-publish-structure"),
    )
    assert published_structure.status_code == 200
    event = _create_event(owner_token, structure["slug"], key="event-page-create")
    event_id = event["id"]
    public_slug = f"recap-night-{event_id}"

    public_before = client.get(f"/forum/events/{public_slug}")
    assert public_before.status_code == 200
    payload = public_before.json()
    assert payload["title"] == "Recap Night"
    assert payload["venue"] == "Le Carré"
    assert payload["entryPriceCents"] == 500
    assert payload["organizer"]["name"] == structure["name"]
    assert payload["appDeepLink"] == f"tore://event/{event_id}"
    assert payload["recap"] is None

    denied = client.get(
        f"/forum/structures/{structure['slug']}/events/{event_id}/recap",
        headers=_headers(outsider_token),
    )
    assert denied.status_code == 403

    private_recap = client.get(
        f"/forum/structures/{structure['slug']}/events/{event_id}/recap",
        headers=_headers(owner_token),
    )
    assert private_recap.status_code == 200
    assert private_recap.json()["event"]["runtimeState"] == "CLOSED"
    assert private_recap.json()["recap"]["status"] == "RECAP_DRAFT"

    public_still_draft = client.get(f"/forum/events/{public_slug}")
    assert public_still_draft.status_code == 200
    assert public_still_draft.json()["recap"] is None

    draft = client.put(
        f"/forum/structures/{structure['slug']}/events/{event_id}/recap",
        json={
            "summary": "Une édition complète, archivée après validation.",
            "stats": [
                {"label": "Entrées", "value": "420"},
                {"label": "Bénévoles", "value": "18"},
            ],
        },
        headers=_headers(owner_token, "event-recap-draft"),
    )
    assert draft.status_code == 200
    assert draft.json()["recap"]["status"] == "RECAP_DRAFT"

    no_confirmation = client.post(
        f"/forum/structures/{structure['slug']}/events/{event_id}/recap/publish",
        json={"confirm_publish": False},
        headers=_headers(owner_token, "event-recap-no-confirm"),
    )
    assert no_confirmation.status_code == 409

    published = client.post(
        f"/forum/structures/{structure['slug']}/events/{event_id}/recap/publish",
        json={"confirm_publish": True},
        headers=_headers(owner_token, "event-recap-publish"),
    )
    assert published.status_code == 200
    assert published.json()["recap"]["status"] == "RECAP_PUBLISHED"

    memory_page = client.get(f"/forum/events/{public_slug}")
    assert memory_page.status_code == 200
    memory = memory_page.json()
    assert memory["canonicalPath"] == f"/forum/events/{public_slug}"
    assert memory["lifecycleStatus"] == "RECAP_PUBLISHED"
    assert memory["recap"]["status"] == "RECAP_PUBLISHED"
    assert memory["recap"]["summary"] == "Une édition complète, archivée après validation."
    assert memory["recap"]["stats"] == [
        {"label": "Entrées", "value": "420"},
        {"label": "Bénévoles", "value": "18"},
    ]


def test_private_event_has_no_public_event_page():
    owner_token, _ = _guest("private-event-owner")
    structure = _create_structure(owner_token, "private-event-orga", "Structure Event Privé")
    event = _create_event(owner_token, structure["slug"], key="private-event-create", visibility="PRIVATE")

    response = client.get(f"/forum/events/recap-night-{event['id']}")
    assert response.status_code == 404


def test_public_event_slug_normalizes_accents():
    owner_token, _ = _guest("accented-event-owner")
    structure = _create_structure(owner_token, "accented-event-orga")
    published_structure = client.post(
        f"/forum/structures/{structure['slug']}/publish",
        json={"reason": "Publication explicite avant le test du slug accentué"},
        headers=_headers(owner_token, "accented-event-publish-structure"),
    )
    assert published_structure.status_code == 200
    event = _create_event(
        owner_token,
        structure["slug"],
        key="accented-event-create",
        name="Réunion générale",
    )

    with SessionLocal() as db:
        persisted = db.get(Event, event["id"])
        assert persisted is not None
        assert (persisted.visibility, persisted.publication_status) == ("PUBLIC", "PUBLISHED")
        assert _is_public_event(persisted)
        assert _event_slug(persisted) == f"reunion-generale-{event['id']}"

    response = client.get(f"/forum/events/reunion-generale-{event['id']}")

    assert response.status_code == 200, response.text
    assert response.json()["slug"] == f"reunion-generale-{event['id']}"
    assert response.json()["canonicalPath"] == f"/forum/events/reunion-generale-{event['id']}"

    # URLs emitted before accent normalization remain readable, but the payload
    # advertises the normalized canonical URL.
    legacy_slug = f"r-union-g-n-rale-{event['id']}"
    legacy = client.get(f"/forum/events/{legacy_slug}")
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()["slug"] == f"reunion-generale-{event['id']}"
    assert legacy.json()["canonicalPath"] == f"/forum/events/reunion-generale-{event['id']}"
