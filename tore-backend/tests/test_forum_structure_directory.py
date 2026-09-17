from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from db import Base, engine, now_utc
from main import app
from models import AppUser, Event, Organization


client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _add_org(db: Session, *, name: str, slug: str, org_type: str, city: str = "Liège", visibility: str = "PUBLIC", **kwargs) -> Organization:
    creator = AppUser(id=f"creator-{slug}", display_name="Test creator")
    db.add(creator)
    db.flush()
    org = Organization(name=name, slug=slug, org_type=org_type, city=city, visibility=visibility, created_by_user_id=creator.id, **kwargs)
    db.add(org)
    db.flush()
    return org


def test_directory_supports_public_structure_type_filters_and_legacy_aliases():
    cases = [
        ("COMMITTEE", "COMMITTEE", "comite"),
        ("CIRCLE", "CERCLE", "cercle"),
        ("ORDER", "ORDRE", "ordre"),
        ("ASSOCIATION", "ASSOCIATION", "association"),
        ("BAR", "BAR", "bar"),
        ("PARTNER", "PARTNER", "partenaire"),
    ]
    with Session(engine) as db:
        for canonical, stored, slug in cases:
            _add_org(db, name=f"Structure {canonical}", slug=slug, org_type=stored)
        db.commit()

    for canonical, _, slug in cases:
        response = client.get(f"/forum/structures?type={canonical}&page_size=12")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["items"][0]["slug"] == slug
        assert payload["items"][0]["type"] == canonical


def test_directory_filters_by_name_city_and_paginates_on_the_server():
    with Session(engine) as db:
        for index in range(13):
            _add_org(db, name=f"Cercle Liège {index:02d}", slug=f"liege-{index:02d}", org_type="CIRCLE", city="Liège")
        for index in range(3):
            _add_org(db, name=f"Cercle Namur {index:02d}", slug=f"namur-{index:02d}", org_type="CIRCLE", city="Namur")
        _add_org(db, name="Cercle privé", slug="private", org_type="CIRCLE", city="Liège", visibility="PRIVATE")
        db.commit()

    response = client.get("/forum/structures?q=Cercle&type=CIRCLE&city=Li%C3%A8ge&page=2&page_size=5")
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 2
    assert payload["pageSize"] == 5
    assert payload["total"] == 13
    assert payload["totalPages"] == 3
    assert len(payload["items"]) == 5
    assert all(item["city"] == "Liège" for item in payload["items"])
    assert all(item["type"] == "CIRCLE" for item in payload["items"])
    assert "private" not in {item["slug"] for item in payload["items"]}


def test_directory_returns_branding_and_only_the_next_visible_public_event():
    now = now_utc()
    with Session(engine) as db:
        org = _add_org(
            db,
            name="Cercle Brandé",
            slug="cercle-brande",
            org_type="CIRCLE",
            logo_url="https://example.test/logo.png",
            banner_url="https://example.test/banner.jpg",
            primary_color="#123456",
            secondary_color="#fedcba",
            visibility_settings_json={"events": "PUBLIC"},
        )
        hidden_events_org = _add_org(
            db,
            name="Cercle sans events publics",
            slug="hidden-events",
            org_type="CIRCLE",
            visibility_settings_json={"events": "STRUCTURE_MEMBERS"},
        )
        db.add_all([
            Event(name="Ancien event", starts_at=now - timedelta(days=2), ends_at=now - timedelta(days=2, hours=-2), host_type="orga", host_id=str(org.id), timezone="Europe/Brussels", visibility="PUBLIC", publication_status="PUBLISHED"),
            Event(name="Event privé", starts_at=now + timedelta(hours=6), ends_at=now + timedelta(hours=8), host_type="orga", host_id=str(org.id), timezone="Europe/Brussels", visibility="PRIVATE", publication_status="DRAFT"),
            Event(name="Prochain event", starts_at=now + timedelta(days=1), ends_at=now + timedelta(days=1, hours=3), host_type="orga", host_id=str(org.id), timezone="Europe/Brussels", visibility="PUBLIC", publication_status="PUBLISHED", venue="Salle académique", city="Liège"),
            Event(name="Event suivant", starts_at=now + timedelta(days=3), ends_at=now + timedelta(days=3, hours=2), host_type="orga", host_id=str(org.id), timezone="Europe/Brussels", visibility="PUBLIC", publication_status="PUBLISHED"),
            Event(name="Event masqué par bloc", starts_at=now + timedelta(hours=2), ends_at=now + timedelta(hours=4), host_type="orga", host_id=str(hidden_events_org.id), timezone="Europe/Brussels", visibility="PUBLIC", publication_status="PUBLISHED"),
        ])
        db.commit()

    response = client.get("/forum/structures?type=CIRCLE&page_size=12")
    assert response.status_code == 200
    items = {item["slug"]: item for item in response.json()["items"]}
    branded = items["cercle-brande"]
    assert branded["logoUrl"] == "https://example.test/logo.png"
    assert branded["bannerUrl"] == "https://example.test/banner.jpg"
    assert branded["primaryColor"] == "#123456"
    assert branded["secondaryColor"] == "#fedcba"
    assert branded["nextPublicEvent"]["name"] == "Prochain event"
    assert branded["nextPublicEvent"]["venue"] == "Salle académique"
    assert items["hidden-events"]["nextPublicEvent"] is None
