from fastapi.testclient import TestClient

from db import Base, engine
from main import app


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
    result = {"Authorization": f"Bearer {token}"}
    if key:
        result["Idempotency-Key"] = key
    return result


def _create_org(owner_token: str, name: str, key: str) -> tuple[int, str]:
    response = client.post(
        "/orgas",
        json={"name": name, "org_type": "COMMITTEE"},
        headers=_headers(owner_token, key),
    )
    assert response.status_code == 200
    return response.json()["orga"]["id"], response.json()["orga"]["slug"]


def _join(org_id: int, token: str, key: str) -> None:
    response = client.post(f"/orgas/{org_id}/join", headers=_headers(token, key))
    assert response.status_code == 200


def _role_id(owner_token: str, slug: str, code: str) -> int:
    response = client.get(f"/forum/structures/{slug}/roles", headers=_headers(owner_token))
    assert response.status_code == 200
    return next(item["id"] for item in response.json()["items"] if item["code"] == code)


def _assign_role(owner_token: str, slug: str, member_user_id: str, role_id: int) -> dict:
    response = client.put(
        f"/forum/structures/{slug}/members/{member_user_id}/roles",
        json={"role_ids": [role_id]},
        headers=_headers(owner_token),
    )
    assert response.status_code == 200
    return response.json()


def test_treasurer_has_finance_read_without_ownership_transfer():
    owner_token, _ = _guest("rbac-owner")
    treasurer_token, treasurer_id = _guest("rbac-treasurer")
    org_id, slug = _create_org(owner_token, "RBAC Treasury", "rbac-treasury-org")
    _join(org_id, treasurer_token, "rbac-treasury-join")

    _assign_role(owner_token, slug, treasurer_id, _role_id(owner_token, slug, "TREASURER"))
    workspace = client.get(f"/forum/structures/{slug}/workspace", headers=_headers(treasurer_token))
    assert workspace.status_code == 200
    capabilities = set(workspace.json()["capabilities"])
    assert "finance.read" in capabilities
    assert "ownership.transfer" not in capabilities
    assert client.get(f"/forum/structures/{slug}/accounting-summary", headers=_headers(treasurer_token)).status_code == 200


def test_communication_can_publish_content_but_has_no_finance_capability():
    owner_token, _ = _guest("communication-owner")
    communication_token, communication_id = _guest("communication-user")
    org_id, slug = _create_org(owner_token, "RBAC Communication", "rbac-communication-org")
    _join(org_id, communication_token, "rbac-communication-join")

    _assign_role(owner_token, slug, communication_id, _role_id(owner_token, slug, "COMMUNICATION"))
    workspace = client.get(f"/forum/structures/{slug}/workspace", headers=_headers(communication_token))
    assert workspace.status_code == 200
    capabilities = set(workspace.json()["capabilities"])
    assert {"structure.publish", "event.publish", "album.publish", "page.publish"} <= capabilities
    assert "finance.read" not in capabilities
    assert client.get(f"/forum/structures/{slug}/accounting-summary", headers=_headers(communication_token)).status_code == 403
    stats_publication = client.patch(
        f"/forum/structures/{slug}/visibility",
        json={"stats": "PUBLIC", "confirm_public_finance": True},
        headers=_headers(communication_token, "communication-finance-publication-denied"),
    )
    assert stats_publication.status_code == 403
    assert stats_publication.json()["detail"]["capability"] == "finance.read"


def test_member_keeps_acl_reads_but_cannot_manage_or_call_sensitive_api():
    owner_token, _ = _guest("member-owner")
    member_token, _ = _guest("member-user")
    org_id, slug = _create_org(owner_token, "RBAC Members", "rbac-member-org")
    _join(org_id, member_token, "rbac-member-join")

    workspace = client.get(f"/forum/structures/{slug}/workspace", headers=_headers(member_token))
    assert workspace.status_code == 200
    capabilities = set(workspace.json()["capabilities"])
    assert {"structure.read", "discussion.read", "document.read", "album.read", "page.read"} <= capabilities
    assert "member.manage" not in capabilities
    assert "visibility.manage" not in capabilities

    accounting = client.get(f"/forum/structures/{slug}/accounting-summary", headers=_headers(member_token))
    assert accounting.status_code == 403
    assert accounting.json()["detail"]["capability"] == "finance.read"
    visibility = client.patch(
        f"/forum/structures/{slug}/visibility",
        json={"members": "PUBLIC"},
        headers=_headers(member_token, "member-visibility-denied"),
    )
    assert visibility.status_code == 403
    assert visibility.json()["detail"]["capability"] == "visibility.manage"


def test_custom_role_is_structure_scoped_and_effective():
    owner_token, _ = _guest("custom-owner")
    member_token, member_id = _guest("custom-member")
    org_id, slug = _create_org(owner_token, "RBAC Custom", "rbac-custom-org")
    _join(org_id, member_token, "rbac-custom-join")

    created = client.post(
        f"/forum/structures/{slug}/roles",
        json={
            "name": "Responsable discussions",
            "code": "DISCUSSION_LEAD",
            "capabilities": ["structure.read", "discussion.read", "discussion.write", "discussion.manage", "channel.create"],
        },
        headers=_headers(owner_token),
    )
    assert created.status_code == 200
    _assign_role(owner_token, slug, member_id, created.json()["id"])

    workspace = client.get(f"/forum/structures/{slug}/workspace", headers=_headers(member_token))
    assert workspace.status_code == 200
    capabilities = set(workspace.json()["capabilities"])
    assert "discussion.manage" in capabilities
    assert "channel.create" in capabilities
    assert "finance.read" not in capabilities
    assert "member.role.manage" not in capabilities


def test_cross_structure_role_assignment_is_rejected():
    owner_a_token, _ = _guest("owner-a")
    owner_b_token, _ = _guest("owner-b")
    member_b_token, member_b_id = _guest("member-b")
    _, slug_a = _create_org(owner_a_token, "RBAC Structure A", "rbac-org-a")
    org_b_id, slug_b = _create_org(owner_b_token, "RBAC Structure B", "rbac-org-b")
    _join(org_b_id, member_b_token, "rbac-join-b")

    custom_a = client.post(
        f"/forum/structures/{slug_a}/roles",
        json={"name": "A only", "code": "A_ONLY", "capabilities": ["structure.read", "finance.read"]},
        headers=_headers(owner_a_token),
    )
    assert custom_a.status_code == 200

    cross = client.put(
        f"/forum/structures/{slug_b}/members/{member_b_id}/roles",
        json={"role_ids": [custom_a.json()["id"]]},
        headers=_headers(owner_b_token),
    )
    assert cross.status_code == 404

    workspace = client.get(f"/forum/structures/{slug_b}/workspace", headers=_headers(member_b_token))
    assert workspace.status_code == 200
    assert "finance.read" not in workspace.json()["capabilities"]
