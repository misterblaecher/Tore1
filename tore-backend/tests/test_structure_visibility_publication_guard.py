from fastapi.testclient import TestClient

from db import Base, engine
from db import get_session
from main import app
from models import Organization


client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _guest(name: str) -> str:
    response = client.post("/auth/guest", json={"display_name": name})
    assert response.status_code == 200
    return response.json()["token"]


def _headers(token: str, key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Idempotency-Key": key}


def test_visibility_center_can_stage_public_blocks_but_cannot_publish_structure():
    token = _guest("visibility-owner")
    created = client.post(
        "/orgas",
        json={"name": "Visibility staged structure"},
        headers=_headers(token, "visibility-create"),
    )
    assert created.status_code == 200
    slug = created.json()["orga"]["slug"]

    staged = client.patch(
        f"/forum/structures/{slug}/visibility",
        json={"page": "PUBLIC", "description": "PUBLIC", "members": "PRIVATE"},
        headers=_headers(token, "visibility-stage"),
    )
    assert staged.status_code == 200
    assert staged.json()["settings"]["page"] == "PUBLIC"
    assert staged.json()["settings"]["members"] == "PRIVATE"
    assert staged.json()["structureVisibility"] == "PRIVATE"
    assert staged.json()["lifecycle"] == "SETUP"
    assert staged.json()["published"] is False
    assert client.get(f"/forum/structures/{slug}").status_code == 404


def test_public_slug_guard_rejects_non_active_structure_even_if_visibility_bits_are_public():
    token = _guest("visibility-corrupt-owner")
    created = client.post(
        "/orgas",
        json={"name": "Visibility lifecycle guard"},
        headers=_headers(token, "visibility-corrupt-create"),
    )
    assert created.status_code == 200
    slug = created.json()["orga"]["slug"]

    # Reproduce a stale/imported row whose public bits disagree with its SETUP lifecycle.
    with get_session() as db:
        org = db.query(Organization).filter(Organization.slug == slug).one()
        org.visibility = "PUBLIC"
        org.visibility_settings_json = {**org.visibility_settings_json, "page": "PUBLIC"}
        db.commit()

    assert client.get(f"/forum/structures/{slug}").status_code == 404

    published = client.post(
        f"/forum/structures/{slug}/publish",
        json={"reason": "Publication explicite après préparation"},
        headers=_headers(token, "visibility-publish"),
    )
    assert published.status_code == 200
    assert published.json()["published"] is True
    public = client.get(f"/forum/structures/{slug}")
    assert public.status_code == 200
    assert public.json()["structure"]["description"] is None

    private_again = client.patch(
        f"/forum/structures/{slug}/visibility",
        json={"page": "PRIVATE", "description": "PRIVATE"},
        headers=_headers(token, "visibility-private-again"),
    )
    assert private_again.status_code == 200
    assert private_again.json()["structureVisibility"] == "PRIVATE"
    assert private_again.json()["published"] is False
    assert client.get(f"/forum/structures/{slug}").status_code == 404
