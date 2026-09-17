from datetime import datetime

from app.routers.forum_archives import _entry, _mandate_for_date, _matches


def test_mandate_projection_uses_real_period_without_persisting_archive_copy():
    mandates = [
        {
            "id": 1,
            "label": "Bureau 2025-2026",
            "role": "PRESIDENT",
            "startsAt": "2025-09-01T00:00:00",
            "endsAt": "2026-06-30T23:59:59",
        }
    ]
    at = datetime.fromisoformat("2026-03-12T20:00:00")
    assert _mandate_for_date(mandates, at) == mandates[0]
    assert _mandate_for_date(mandates, datetime.fromisoformat("2026-09-01T00:00:00")) is None


def test_archive_filters_combine_year_mandate_event_category_and_search():
    event = type("EventStub", (), {
        "id": 42,
        "name": "Bal 2026",
        "starts_at": datetime.fromisoformat("2026-03-12T20:00:00"),
        "ends_at": datetime.fromisoformat("2026-03-13T02:00:00"),
        "venue": "Le Carré",
        "city": "Liège",
        "public_description": None,
        "visibility": "PUBLIC",
        "publication_status": "PUBLISHED",
        "entry_price_cents": None,
        "banner_url": None,
    })()
    mandate = {"id": 1, "label": "Bureau 2025-2026"}
    item = _entry(
        category="DOCUMENT",
        object_id=4,
        title="PV de passation",
        subtitle="Bureau",
        archived_at=datetime.fromisoformat("2026-06-30T10:00:00"),
        event=event,
        mandate=mandate,
        target="/forum/structures/embuscade/documents",
    )
    assert _matches(item, search="passation", year=2026, mandate="2025-2026", event_id=42, category="DOCUMENT")
    assert not _matches(item, search="passation", year=2025, mandate="2025-2026", event_id=42, category="DOCUMENT")
    assert not _matches(item, search="passation", year=2026, mandate="2025-2026", event_id=42, category="ALBUM")
