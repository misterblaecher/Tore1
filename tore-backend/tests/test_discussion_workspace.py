from tests.test_forum_structure_mvp import client, setup_function, _guest, _headers
from sqlalchemy.orm import Session
from db import engine
from models import OrganizationMembership


def test_channels_threads_documents_reactions_and_scope():
    owner, owner_id = _guest("Workspace owner")
    member, member_id = _guest("Workspace member")
    outsider, _ = _guest("Outside")
    org = client.post("/orgas", json={"name": "Discussion workspace", "org_type": "BAR"}, headers=_headers(owner, "org")).json()["orga"]
    with Session(engine) as db:
        db.add(OrganizationMembership(organization_id=org["id"], user_id=member_id, role="MEMBER", status="ACTIVE", created_by_user_id=owner_id))
        db.commit()
    base = f'/forum/structures/{org["slug"]}'
    def create(path, data, key, token=owner):
        return client.post(base + path, json=data, headers=_headers(token, key))
    office = create("/channels", {"name": "Bureau", "visibility": "OFFICE"}, "office")
    assert office.status_code == 200
    assert create("/channels", {"name": "Bureau", "visibility": "OFFICE"}, "office").json() == office.json()
    assert create("/channels", {"name": "Bureau"}, "duplicate").status_code == 409
    assert create("/channels", {"name": "Forbidden"}, "member-channel", member).status_code == 403
    channel = create("/channels", {"name": "Communication"}, "public-channel").json()["id"]
    secret = create("/discussions", {"title": "Secret bureau", "body": "Confidentiel", "channel_id": office.json()["id"]}, "secret").json()
    assert create("/discussions", {"title": "Denied", "body": "No", "channel_id": office.json()["id"]}, "denied", member).status_code == 404
    assert create("/discussions", {"title": "Invalid", "body": "No", "channel_id": 999999}, "invalid").status_code == 404
    doc = create("/documents", {"title": "Agenda", "file_url": "https://example.com/agenda.pdf", "visibility": "STRUCTURE_MEMBERS"}, "doc").json()
    root = create("/discussions", {"title": "Réunion", "body": "Préparons la réunion", "channel_id": channel, "document_ids": [doc["id"]]}, "root").json()
    assert root["documents"][0]["id"] == doc["id"]
    reply = create("/discussions", {"title": "Re: Réunion", "body": "D’accord", "channel_id": channel, "parent_id": root["id"]}, "reply", member)
    assert reply.status_code == 200 and reply.json()["parentId"] == root["id"]
    assert create("/discussions", {"title": "Bad thread", "body": "No", "channel_id": channel, "parent_id": secret["id"]}, "cross-thread").status_code == 400
    assert create("/discussions", {"title": "Invalid doc", "body": "No", "channel_id": channel, "document_ids": [999999]}, "invalid-doc").status_code == 404
    for key in ["react", "react-again"]:
        reacted = client.patch(base + f'/discussions/{root["id"]}', json={"emoji": "👍", "active": True}, headers=_headers(member, key))
        assert reacted.status_code == 200
        assert reacted.json()["reactions"] == [{"emoji": "👍", "count": 1, "mine": True}]
    denied = client.patch(base + f'/discussions/{root["id"]}', json={"pinned": True}, headers=_headers(member, "pin-denied"))
    assert denied.status_code == 403
    assert client.patch(base + f'/discussions/{root["id"]}', json={"pinned": True}, headers=_headers(owner, "pin")).json()["pinned"]
    assert client.get(base + "/discussions", headers=_headers(outsider, "read")).status_code == 403
    feed = client.get(base + "/discussions", headers=_headers(member, "feed")).json()
    assert len(feed["channels"]) == 1
    assert all(p["channelId"] == channel for p in feed["posts"])
    dashboard = client.get(base + "/dashboard", headers=_headers(member, "dashboard")).json()
    assert all(p["id"] != secret["id"] for p in dashboard["recentPosts"])
    for key in ["legacy-one", "legacy-two"]:
        assert create("/discussions", {"title": "Legacy", "body": "General channel"}, key).status_code == 200
