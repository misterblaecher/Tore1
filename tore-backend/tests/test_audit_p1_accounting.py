"""P1 regression tests: tenant isolation and spreadsheet-safe exports."""
import csv
import io
import secrets

from fastapi.testclient import TestClient

from db import Base, engine, get_session
from main import app
from models import Event, EventStructure
from app.models.accounting import AccountingEntry


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _owner(client):
    response = client.post("/auth/guest", json={"display_name": "Audit treasury"})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["token"]}


def _org(client, headers, name):
    response = client.post("/orgas", json={"name": name, "org_type": "COMMITTEE"},
                           headers={**headers, "Idempotency-Key": secrets.token_hex(8)})
    assert response.status_code == 200, response.text
    return response.json()["orga"]


def test_finance_entries_reject_foreign_event_id():
    client = TestClient(app)
    headers = _owner(client)
    own = _org(client, headers, "Treasury A")
    foreign = _org(client, headers, "Treasury B")
    db = get_session()
    try:
        own_event = Event(name="Event A", host_type="orga", host_id=str(own["id"]))
        foreign_event = Event(name="Event B", host_type="orga", host_id=str(foreign["id"]))
        db.add_all([own_event, foreign_event])
        db.commit()
        own_event_id = own_event.id
        foreign_event_id = foreign_event.id
    finally:
        db.close()

    target = "/forum/structures/" + own["slug"] + "/accounting/entries"
    payload = {"category": "Sponsoring", "entry_type": "INCOME", "amount_cents": 3000}
    response = client.post(target, json={**payload, "event_id": foreign_event_id}, headers=headers)
    assert response.status_code == 404
    with get_session() as session:
        assert session.query(AccountingEntry).count() == 0
    valid = client.post(target, json={**payload, "event_id": own_event_id}, headers=headers)
    assert valid.status_code == 200, valid.text

    # Deny unprivileged cohosts even if an event is explicitly associated.
    db = get_session()
    try:
        relation = EventStructure(
            event_id=foreign_event_id,
            organization_id=own["id"],
            role="COHOST",
            can_finance=False,
        )
        db.add(relation)
        db.commit()
        relation_id = relation.id
    finally:
        db.close()
    denied = client.post(target, json={**payload, "event_id": foreign_event_id}, headers=headers)
    assert denied.status_code == 404

    # Finance access delegated by the host restores legitimate cohost accounting.
    db = get_session()
    try:
        relation = db.get(EventStructure, relation_id)
        relation.can_finance = True
        db.commit()
    finally:
        db.close()
    allowed = client.post(target, json={**payload, "event_id": foreign_event_id}, headers=headers)
    assert allowed.status_code == 200, allowed.text


def test_accounting_csv_quotes_and_neutralizes_formulas():
    client = TestClient(app)
    headers = _owner(client)
    org = _org(client, headers, "Treasury CSV")
    notes = '=HYPERLINK("https://malicious.example","x"), test\nsecond line'
    response = client.post(
        "/forum/structures/" + org["slug"] + "/accounting/entries",
        json={"category": "+SUM(A1:A2)", "entry_type": "INCOME",
              "amount_cents": 100, "notes": notes},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    csv_response = client.get("/forum/structures/" + org["slug"] + "/accounting/export.csv",
                              headers=headers)
    assert csv_response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(csv_response.text)))
    assert len(rows) == 1
    assert rows[0]["category"] == "'+SUM(A1:A2)"
    assert rows[0]["notes"] == "'" + notes
    assert rows[0]["amount_cents"] == "100"
