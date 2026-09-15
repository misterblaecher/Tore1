from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from db import Base, engine
from main import app
from models import AppUser, AuditLog, OrganizationMembership
from app.forum_models import StructureAuditContext


client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _user(name: str) -> tuple[str, str]:
    response = client.post("/auth/guest", json={"display_name": name})
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    user_id = me.json()["id"]
    # Forum v2 private authority intentionally requires a registered account.
    with Session(engine) as db:
        user = db.get(AppUser, user_id)
        assert user is not None
        user.is_guest = False
        user.is_deleted = False
        user.deleted_at = None
        user.account_status = "ACTIVE"
        db.commit()
    return token, user_id


def _h(token: str, idem: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if idem:
        headers["Idempotency-Key"] = idem
    return headers


def _create_structure(token: str, name: str) -> dict:
    response = client.post(
        "/forum/v2/structures",
        json={"name": name, "org_type": "COMMITTEE"},
        headers=_h(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _join(org_id: int, token: str, key: str) -> None:
    response = client.post(f"/orgas/{org_id}/join", headers=_h(token, key))
    assert response.status_code == 200, response.text


def _membership_id(org_id: int, user_id: str) -> int:
    with Session(engine) as db:
        return db.query(OrganizationMembership).filter_by(
            organization_id=org_id,
            user_id=user_id,
        ).one().id


def _role(owner: str, slug: str, name: str, permissions: list[str]) -> int:
    response = client.post(
        f"/forum/v2/structures/{slug}/roles",
        json={
            "name": name,
            "audience_level": "BUREAU",
            "permissions": permissions,
        },
        headers=_h(owner),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _assign(owner: str, slug: str, org_id: int, user_id: str, role_id: int) -> None:
    response = client.patch(
        f"/forum/v2/structures/{slug}/members/{_membership_id(org_id, user_id)}",
        json={"role_id": role_id},
        headers=_h(owner),
    )
    assert response.status_code == 200, response.text


def _put_acl(owner: str, slug: str, channel_id: int, *, roles=None, capabilities=None, members=None, enabled=True):
    response = client.put(
        f"/forum/v2/structures/{slug}/channels/{channel_id}/acl",
        json={
            "enabled": enabled,
            "role_ids": roles or [],
            "capabilities": capabilities or [],
            "member_user_ids": members or [],
        },
        headers=_h(owner),
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_explicit_channel_acl_protects_every_descendant_and_revokes_immediately():
    owner, _ = _user("acl-owner")
    president, president_id = _user("acl-president")
    communication, communication_id = _user("acl-communication")
    alice, alice_id = _user("Alice Dupont")
    outsider, outsider_id = _user("acl-bureau-outsider")

    structure = _create_structure(owner, "ACL Structure")
    slug, org_id = structure["slug"], structure["id"]
    for token, key in (
        (president, "join-president"),
        (communication, "join-communication"),
        (alice, "join-alice"),
        (outsider, "join-outsider"),
    ):
        _join(org_id, token, key)

    president_role = _role(
        owner,
        slug,
        "PRESIDENT",
        ["structure.read", "channels.read", "channels.post"],
    )
    communication_role = _role(
        owner,
        slug,
        "COMMUNICATION",
        ["structure.read", "channels.read", "channels.post", "publications.manage"],
    )
    _assign(owner, slug, org_id, president_id, president_role)
    _assign(owner, slug, org_id, communication_id, communication_role)

    # Force the remaining members through the new role assignment bootstrap.
    assert client.get(f"/forum/v2/structures/{slug}/context", headers=_h(alice)).status_code == 200
    assert client.get(f"/forum/v2/structures/{slug}/context", headers=_h(outsider)).status_code == 200

    channel = client.post(
        f"/forum/v2/structures/{slug}/channels",
        json={"name": "Sponsors", "visibility": "MEMBERS"},
        headers=_h(owner),
    )
    assert channel.status_code == 201, channel.text
    channel_id = channel.json()["id"]

    acl = _put_acl(
        owner,
        slug,
        channel_id,
        roles=[president_role],
        capabilities=["publications.manage"],
    )
    assert acl["enabled"] is True
    assert acl["roleIds"] == [president_role]
    assert acl["capabilities"] == ["publications.manage"]

    # Role and capability grants are independently sufficient.
    assert client.get(f"/forum/v2/structures/{slug}/channels/{channel_id}", headers=_h(president)).status_code == 200
    assert client.get(f"/forum/v2/structures/{slug}/channels/{channel_id}", headers=_h(communication)).status_code == 200

    # A normal Bureau/member-level actor is neither listed nor able to probe the id.
    visible = client.get(f"/forum/v2/structures/{slug}/channels", headers=_h(outsider))
    assert visible.status_code == 200
    assert channel_id not in {item["id"] for item in visible.json()["items"]}
    assert client.get(f"/forum/v2/structures/{slug}/channels/{channel_id}", headers=_h(outsider)).status_code == 404
    assert client.get(f"/forum/v2/structures/{slug}/channels/{channel_id}/messages", headers=_h(outsider)).status_code == 404

    document = client.post(
        f"/forum/v2/structures/{slug}/documents",
        json={"title": "Sponsor contract", "visibility": "MEMBERS"},
        headers=_h(owner),
    )
    assert document.status_code == 201, document.text
    document_id = document.json()["id"]
    uploaded = client.post(
        f"/forum/v2/structures/{slug}/documents/{document_id}/versions",
        files={"file": ("sponsor.txt", b"secret sponsor terms", "text/plain")},
        headers=_h(owner),
    )
    assert uploaded.status_code == 201, uploaded.text

    root = client.post(
        f"/forum/v2/structures/{slug}/channels/{channel_id}/messages",
        json={"body": "Sponsor negotiations", "document_ids": [document_id]},
        headers=_h(owner),
    )
    assert root.status_code == 201, root.text
    root_id = root.json()["id"]
    reply = client.post(
        f"/forum/v2/structures/{slug}/channels/{channel_id}/messages",
        json={"body": "Private reply", "parent_message_id": root_id},
        headers=_h(owner),
    )
    assert reply.status_code == 201, reply.text

    # Direct message/thread/reaction/attachment probes all inherit the channel ACL.
    assert client.get(f"/forum/v2/structures/{slug}/messages/{root_id}", headers=_h(outsider)).status_code == 404
    assert client.get(f"/forum/v2/structures/{slug}/messages/{root_id}/thread", headers=_h(outsider)).status_code == 404
    assert client.post(
        f"/forum/v2/structures/{slug}/messages/{root_id}/reactions",
        json={"emoji": "👍", "active": True},
        headers=_h(outsider),
    ).status_code == 404
    assert client.get(
        f"/forum/v2/structures/{slug}/messages/{root_id}/attachments/{document_id}",
        headers=_h(outsider),
    ).status_code == 404
    assert client.get(
        f"/forum/v2/structures/{slug}/messages/{root_id}/attachments/{document_id}/download",
        headers=_h(outsider),
    ).status_code == 404
    # The document-library id is not an attachment bypass either.
    assert client.get(f"/forum/v2/structures/{slug}/documents/{document_id}", headers=_h(outsider)).status_code == 404
    assert client.get(f"/forum/v2/structures/{slug}/documents/{document_id}/download", headers=_h(outsider)).status_code == 404

    # Search must not reveal the forbidden message or attachment title.
    search = client.get(f"/forum/v2/structures/{slug}/search?q=Sponsor", headers=_h(outsider))
    assert search.status_code == 200, search.text
    assert not any(item.get("id") in {root_id, document_id} for item in search.json()["items"])

    # Explicit member grant works without changing Alice's structure role.
    _put_acl(
        owner,
        slug,
        channel_id,
        roles=[president_role],
        capabilities=["publications.manage"],
        members=[alice_id],
    )
    assert client.get(f"/forum/v2/structures/{slug}/messages/{root_id}", headers=_h(alice)).status_code == 200
    assert client.get(
        f"/forum/v2/structures/{slug}/messages/{root_id}/attachments/{document_id}",
        headers=_h(alice),
    ).status_code == 200

    # Removing the member grant revokes access on the very next request; no cache.
    _put_acl(
        owner,
        slug,
        channel_id,
        roles=[president_role],
        capabilities=["publications.manage"],
        members=[],
    )
    assert client.get(f"/forum/v2/structures/{slug}/messages/{root_id}", headers=_h(alice)).status_code == 404

    # ACL writes are auditable with before/after snapshots.
    with Session(engine) as db:
        logs = db.query(AuditLog).filter_by(action="forum.channel.acl.update").all()
        assert len(logs) >= 3
        contexts = db.query(StructureAuditContext).filter(
            StructureAuditContext.audit_log_id.in_([log.id for log in logs])
        ).all()
        assert contexts
        assert any((row.after_json or {}).get("channelId") == channel_id for row in contexts)


def test_empty_explicit_acl_stays_closed_and_cross_structure_ids_never_match():
    owner_a, _ = _user("acl-owner-a")
    member_a, _ = _user("acl-member-a")
    owner_b, _ = _user("acl-owner-b")
    structure_a = _create_structure(owner_a, "ACL Tenant A")
    structure_b = _create_structure(owner_b, "ACL Tenant B")
    _join(structure_a["id"], member_a, "join-member-a")
    assert client.get(
        f"/forum/v2/structures/{structure_a['slug']}/context",
        headers=_h(member_a),
    ).status_code == 200

    channel = client.post(
        f"/forum/v2/structures/{structure_a['slug']}/channels",
        json={"name": "Owner only", "visibility": "MEMBERS"},
        headers=_h(owner_a),
    )
    assert channel.status_code == 201
    channel_id = channel.json()["id"]
    _put_acl(owner_a, structure_a["slug"], channel_id, roles=[], capabilities=[], members=[])

    # Explicit empty is deny-all except owner; deleting grants never falls back.
    assert client.get(
        f"/forum/v2/structures/{structure_a['slug']}/channels/{channel_id}",
        headers=_h(member_a),
    ).status_code == 404
    assert client.get(
        f"/forum/v2/structures/{structure_a['slug']}/channels/{channel_id}",
        headers=_h(owner_a),
    ).status_code == 200

    # Reusing a foreign channel id under another tenant cannot resolve it.
    assert client.get(
        f"/forum/v2/structures/{structure_b['slug']}/channels/{channel_id}",
        headers=_h(owner_b),
    ).status_code == 404
    assert client.get(
        f"/forum/v2/structures/{structure_b['slug']}/channels/{channel_id}/acl",
        headers=_h(owner_b),
    ).status_code == 404
