from fastapi.testclient import TestClient

from db import Base, engine
from main import app


client = TestClient(app)
PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDAT\x08\xd7c\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _owner() -> tuple[str, str]:
    response = client.post("/auth/guest", json={"display_name": "branding-owner"})
    assert response.status_code == 200
    token = response.json()["token"]
    created = client.post(
        "/orgas",
        json={"name": "Branding Structure", "city": "Liège", "org_type": "CIRCLE"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "branding-create"},
    )
    assert created.status_code == 200
    return token, created.json()["orga"]["slug"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_logo_and_banner_use_managed_upload_and_can_be_published():
    token, slug = _owner()
    public_urls = {}

    for purpose in ("LOGO", "BANNER"):
        uploaded = client.post(
            f"/forum/structures/{slug}/files",
            headers=_auth(token),
            data={"purpose": purpose},
            files={"file": (f"{purpose.lower()}.png", PNG_1X1, "image/png")},
        )
        assert uploaded.status_code == 201
        payload = uploaded.json()
        assert payload["purpose"] == purpose
        assert payload["visibility"] == "PRIVATE"

        published = client.patch(
            f"/forum/structures/{slug}/files/{payload['id']}/visibility",
            headers=_auth(token),
            json={"visibility": "PUBLIC", "confirm_public": True},
        )
        assert published.status_code == 200
        assert published.json()["visibility"] == "PUBLIC"
        public_file = client.get(f"/forum/public/files/{payload['id']}")
        assert public_file.status_code == 200
        assert public_file.content == PNG_1X1
        assert public_file.headers["x-content-type-options"] == "nosniff"
        public_urls[purpose] = f"http://testserver/forum/public/files/{payload['id']}"

    settings = client.patch(
        f"/forum/structures/{slug}/settings",
        headers={**_auth(token), "Idempotency-Key": "branding-settings"},
        json={
            "logo_url": public_urls["LOGO"],
            "banner_url": public_urls["BANNER"],
            "primary_color": "#BA1733",
            "secondary_color": "#F4C430",
        },
    )
    assert settings.status_code == 200
    assert settings.json()["logoUrl"] == public_urls["LOGO"]
    assert settings.json()["bannerUrl"] == public_urls["BANNER"]
    assert settings.json()["primaryColor"] == "#BA1733"
    assert settings.json()["secondaryColor"] == "#F4C430"


def test_structure_branding_rejects_invalid_hex():
    token, slug = _owner()
    response = client.patch(
        f"/forum/structures/{slug}/settings",
        headers={**_auth(token), "Idempotency-Key": "branding-invalid-hex"},
        json={"primary_color": "red"},
    )
    assert response.status_code == 422
