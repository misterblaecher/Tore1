from datetime import timedelta
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session, now_utc
from main import app
from models import Bar, Event, EventRuntimeState, Organization


def _seed_discovery_events() -> dict[str, int]:
    Base.metadata.create_all(engine)
    session = get_session()
    try:
        suffix = secrets.token_hex(4)
        bar = Bar(name=f"Reflektor {suffix}", city="Liege", partner_code=f"DISC{suffix}")
        session.add(bar)
        session.flush()
        org = Organization(
            name=f"Cercle Discovery {suffix}",
            slug=f"cercle-discovery-{suffix}",
            city="Liege",
            created_by_user_id=f"discovery-{suffix}",
        )
        session.add(org)
        session.flush()

        public = Event(
            bar_id=bar.id,
            name=f"Bal Discovery {suffix}",
            starts_at=now_utc() + timedelta(hours=2),
            ends_at=now_utc() + timedelta(hours=7),
            entry_price_cents=500,
            venue="Quai Discovery 12",
            host_type="orga",
            host_id=str(org.id),
            host_display_name=org.name,
            visibility="PUBLIC",
            publication_status="PUBLISHED",
        )
        private = Event(
            bar_id=bar.id,
            name=f"Private Discovery {suffix}",
            starts_at=now_utc() + timedelta(hours=3),
            ends_at=now_utc() + timedelta(hours=6),
            visibility="PRIVATE",
            publication_status="PUBLISHED",
        )
        draft = Event(
            bar_id=bar.id,
            name=f"Draft Discovery {suffix}",
            starts_at=now_utc() + timedelta(hours=4),
            ends_at=now_utc() + timedelta(hours=8),
            visibility="PUBLIC",
            publication_status="DRAFT",
        )
        ended = Event(
            bar_id=bar.id,
            name=f"Ended Discovery {suffix}",
            starts_at=now_utc() - timedelta(hours=8),
            ends_at=now_utc() - timedelta(hours=4),
            visibility="PUBLIC",
            publication_status="PUBLISHED",
        )
        session.add_all([public, private, draft, ended])
        session.flush()
        session.add(EventRuntimeState(event_id=public.id, state="LIVE"))
        session.commit()
        return {
            "event_id": public.id,
            "bar_id": bar.id,
            "org_id": org.id,
            "ended_id": ended.id,
            "private_id": private.id,
            "draft_id": draft.id,
        }
    finally:
        session.close()


def test_discovery_only_returns_public_published_non_ended_events():
    seeded = _seed_discovery_events()
    response = TestClient(app).get("/events", params={"bar_id": seeded["bar_id"]})

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload] == [seeded["event_id"]]
    event = payload[0]
    assert event["barName"].startswith("Reflektor")
    assert event["host"]["name"].startswith("Cercle Discovery")
    assert event["entry_price_cents"] == 500
    assert event["publicationStatus"] == "PUBLISHED"


def test_discovery_filters_by_search_structure_and_upcoming():
    seeded = _seed_discovery_events()
    client = TestClient(app)

    by_search = client.get("/events", params={"query": "Quai Discovery"})
    by_structure = client.get(
        "/events", params={"structure_id": seeded["org_id"], "status": "UPCOMING"}
    )

    assert by_search.status_code == 200
    assert seeded["event_id"] in [item["id"] for item in by_search.json()]
    assert by_structure.status_code == 200
    assert [item["id"] for item in by_structure.json()] == [seeded["event_id"]]


def test_discovery_filters_by_city():
    seeded = _seed_discovery_events()
    client = TestClient(app)

    matching = client.get("/events", params={"city": "Liege"})
    missing = client.get("/events", params={"city": "Bruxelles"})

    assert matching.status_code == 200
    assert seeded["event_id"] in [item["id"] for item in matching.json()]
    assert missing.status_code == 200
    assert seeded["event_id"] not in [item["id"] for item in missing.json()]


def test_discovery_nearby_filters_and_sorts_by_actual_distance_before_limit():
    seeded = _seed_discovery_events()
    session = get_session()
    try:
        near = session.get(Event, seeded["event_id"])
        near.lat, near.lng = 50.64, 5.57
        farther = Event(
            bar_id=seeded["bar_id"],
            name="Farther Discovery",
            starts_at=now_utc() + timedelta(hours=1),
            ends_at=now_utc() + timedelta(hours=8),
            lat=50.70,
            lng=5.57,
            visibility="PUBLIC",
            publication_status="PUBLISHED",
        )
        no_coordinates = Event(
            name="Unlocated Discovery",
            starts_at=now_utc() + timedelta(minutes=30),
            ends_at=now_utc() + timedelta(hours=8),
            visibility="PUBLIC",
            publication_status="PUBLISHED",
        )
        session.add_all([farther, no_coordinates])
        session.commit()
        farther_id, no_coordinates_id = farther.id, no_coordinates.id
    finally:
        session.close()

    client = TestClient(app)
    params = {"lat": 50.64, "lng": 5.57, "radius": 20, "bar_id": seeded["bar_id"]}
    response = client.get("/events", params=params)
    limited = client.get("/events", params={**params, "limit": 1})

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert ids == [seeded["event_id"], farther_id]
    assert response.json()[0]["distanceKm"] == 0
    assert response.json()[1]["distanceKm"] > 0
    assert no_coordinates_id not in [
        item["id"] for item in client.get("/events", params={
            "lat": 50.64, "lng": 5.57, "radius": 20,
        }).json()
    ]
    assert [item["id"] for item in limited.json()] == [seeded["event_id"]]
    assert client.get("/events", params={**params, "radius": 1}).json()[0]["id"] == seeded["event_id"]
    assert farther_id not in [item["id"] for item in client.get("/events", params={**params, "radius": 1}).json()]


def test_discovery_nearby_requires_complete_valid_coordinates():
    client = TestClient(app)
    for params in ({"lat": 50.64}, {"lat": 50.64, "lng": 5.57},
                   {"lat": 91, "lng": 5.57, "radius": 20},
                   {"lat": 50.64, "lng": 5.57, "radius": 0}):
        assert client.get("/events", params=params).status_code == 422


def test_discovery_nearby_uses_bar_coordinates_only_as_a_complete_pair():
    seeded = _seed_discovery_events()
    session = get_session()
    try:
        bar = session.get(Bar, seeded["bar_id"])
        bar.lat, bar.lng = 50.64, 5.57
        event = session.get(Event, seeded["event_id"])
        event.lat = 51.0  # Partial event coordinates must not mix with bar longitude.
        session.commit()
    finally:
        session.close()

    response = TestClient(app).get("/events", params={
        "lat": 50.64, "lng": 5.57, "radius": 1, "bar_id": seeded["bar_id"],
    })
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [seeded["event_id"]]
    assert response.json()[0]["lat"] == 50.64
    assert response.json()[0]["lng"] == 5.57
    assert response.json()[0]["distanceKm"] == 0


def test_event_detail_exposes_real_pricing_access_and_bar_metadata():
    seeded = _seed_discovery_events()
    response = TestClient(app).get(f"/events/{seeded['event_id']}/public")

    assert response.status_code == 200
    payload = response.json()
    assert payload["pricing"] == {
        "entryPriceCents": 500,
        "isFree": False,
        "currency": "EUR",
    }
    assert payload["accessPolicy"]["visibility"] == "PUBLIC"
    assert payload["description"] is None
    assert payload["venue"]["barId"] == seeded["bar_id"]
    assert payload["venue"]["city"] == "Liege"


def test_all_anonymous_event_reads_hide_private_draft_and_ended_rows():
    seeded = _seed_discovery_events()
    client = TestClient(app)

    for event_id in (seeded["private_id"], seeded["draft_id"], seeded["ended_id"]):
        assert client.get(f"/events/{event_id}/public").status_code == 404
        assert client.get(f"/events/{event_id}/share").status_code == 404
        assert client.get(f"/open?type=event&id={event_id}").status_code == 404

    assert client.get(f"/events/{seeded['event_id']}").status_code == 401
