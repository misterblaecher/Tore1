from tests.test_forum_structure_mvp import _guest, _headers, client, setup_function


def _structure(token: str, name: str, key: str) -> dict:
    response = client.post(
        "/orgas",
        json={"name": name, "org_type": "COMMITTEE"},
        headers=_headers(token, key),
    )
    assert response.status_code == 200
    return response.json()["orga"]


def _page(token: str, slug: str, title: str, content: str, key: str) -> None:
    response = client.post(
        f"/forum/structures/{slug}/pages",
        json={
            "title": title,
            "content": content,
            "visibility": "STRUCTURE_MEMBERS",
            "category": "HISTORY",
            "published": True,
        },
        headers=_headers(token, key),
    )
    assert response.status_code == 200


def test_global_search_indexes_page_content_without_cross_structure_leakage():
    owner_a, _ = _guest("search-owner-a")
    member_a, _ = _guest("search-member-a")
    owner_b, _ = _guest("search-owner-b")
    structure_a = _structure(owner_a, "Search Security A", "search-org-a")
    structure_b = _structure(owner_b, "Search Security B", "search-org-b")
    assert client.post(
        f"/orgas/{structure_a['id']}/join",
        headers=_headers(member_a, "search-member-a-join"),
    ).status_code == 200

    _page(owner_a, structure_a["slug"], "Mémoire locale", "needle-local-content", "search-page-a")
    _page(owner_b, structure_b["slug"], "Mémoire étrangère", "needle-foreign-content", "search-page-b")

    local = client.get(
        f"/forum/structures/{structure_a['slug']}/search?q=needle-local-content",
        headers=_headers(member_a, "unused"),
    )
    assert local.status_code == 200
    assert [(item["category"], item["title"]) for item in local.json()["results"]] == [
        ("folklore", "Mémoire locale")
    ]

    cross_structure = client.get(
        f"/forum/structures/{structure_a['slug']}/search?q=needle-foreign-content",
        headers=_headers(member_a, "unused-2"),
    )
    assert cross_structure.status_code == 200
    assert cross_structure.json()["results"] == []

    outsider = client.get(
        f"/forum/structures/{structure_a['slug']}/search?q=needle-local-content",
        headers=_headers(owner_b, "unused-3"),
    )
    assert outsider.status_code == 403
