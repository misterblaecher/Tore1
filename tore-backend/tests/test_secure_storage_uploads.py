import io
import zipfile

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
PDF_MIN = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"


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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_structure(token: str, name: str, key: str) -> str:
    response = client.post(
        "/orgas",
        json={"name": name, "city": "Liège", "org_type": "CIRCLE"},
        headers={**_auth(token), "Idempotency-Key": key},
    )
    assert response.status_code == 200
    return response.json()["orga"]["slug"]


def _join_structure(slug: str, owner_token: str, member_token: str, key: str) -> tuple[int, str]:
    lifecycle = client.get(f"/forum/structures/{slug}/lifecycle", headers=_auth(owner_token))
    assert lifecycle.status_code == 200
    organization_id = lifecycle.json()["organizationId"]
    me = client.get("/auth/me", headers=_auth(member_token))
    assert me.status_code == 200
    joined = client.post(f"/orgas/{organization_id}/join", headers={**_auth(member_token), "Idempotency-Key": key})
    assert joined.status_code == 200
    return organization_id, me.json()["id"]


def _assign_system_role(slug: str, owner_token: str, member_id: str, code: str) -> None:
    roles = client.get(f"/forum/structures/{slug}/roles", headers=_auth(owner_token))
    assert roles.status_code == 200
    role_id = next(item["id"] for item in roles.json()["items"] if item["code"] == code)
    assigned = client.put(
        f"/forum/structures/{slug}/members/{member_id}/roles",
        json={"role_ids": [role_id]},
        headers=_auth(owner_token),
    )
    assert assigned.status_code == 200


def _attach_document(slug: str, owner_token: str, file_id: str, visibility: str, key: str) -> None:
    response = client.post(
        f"/forum/structures/{slug}/documents",
        json={
            "title": f"Document {visibility}",
            "file_url": f"/forum/structures/{slug}/files/{file_id}/content",
            "visibility": visibility,
        },
        headers={**_auth(owner_token), "Idempotency-Key": key},
    )
    assert response.status_code == 200


def _upload(slug: str, token: str, filename: str, body: bytes, content_type: str, purpose: str = "DOCUMENT"):
    return client.post(
        f"/forum/structures/{slug}/files",
        headers=_auth(token),
        data={"purpose": purpose},
        files={"file": (filename, body, content_type)},
    )


def test_mime_interdit():
    token, _ = _guest("upload-owner-forbidden")
    slug = _create_structure(token, "Upload Forbidden", "upload-forbidden")
    response = _upload(slug, token, "payload.exe", b"MZ\x90\x00malware", "application/octet-stream")
    assert response.status_code == 415
    assert response.json()["detail"]["reason"] == "MIME_NOT_ALLOWED"


def test_taille_excessive(monkeypatch):
    monkeypatch.setenv("TORE_UPLOAD_MAX_BYTES", "8")
    token, _ = _guest("upload-owner-large")
    slug = _create_structure(token, "Upload Large", "upload-large")
    response = _upload(slug, token, "photo.png", PNG_1X1, "image/png", purpose="IMAGE")
    assert response.status_code == 413
    assert response.json()["detail"]["reason"] == "FILE_TOO_LARGE"


def test_extension_mensongere():
    token, _ = _guest("upload-owner-lie")
    slug = _create_structure(token, "Upload Lie", "upload-lie")
    response = _upload(slug, token, "photo.jpg", PDF_MIN, "image/jpeg")
    assert response.status_code == 415
    assert response.json()["detail"]["reason"] == "FILE_EXTENSION_MISMATCH"
    assert response.json()["detail"]["detectedMime"] == "application/pdf"


def test_upload_image_valide_et_prive_par_defaut():
    token, user_id = _guest("upload-owner-image")
    slug = _create_structure(token, "Upload Image", "upload-image")
    response = _upload(slug, token, "..\\photo finale.png", PNG_1X1, "image/png", purpose="IMAGE")
    assert response.status_code == 201
    payload = response.json()
    assert payload["ownerId"] == user_id
    assert payload["mime"] == "image/png"
    assert payload["size"] == len(PNG_1X1)
    assert payload["visibility"] == "PRIVATE"
    assert payload["storageKey"].startswith("private/structures/")
    assert "photo finale" not in payload["storageKey"]
    assert len(payload["checksum"]) == 64
    assert client.get(f"/forum/public/files/{payload['id']}").status_code == 404


def test_pdf_valide():
    token, _ = _guest("upload-owner-pdf")
    slug = _create_structure(token, "Upload PDF", "upload-pdf")
    response = _upload(slug, token, "pv.pdf", PDF_MIN, "application/pdf")
    assert response.status_code == 201
    payload = response.json()
    assert payload["mime"] == "application/pdf"
    content = client.get(f"/forum/structures/{slug}/files/{payload['id']}/content", headers=_auth(token))
    assert content.status_code == 200
    assert content.content == PDF_MIN
    assert content.headers["x-content-type-options"] == "nosniff"


def test_acces_prive_et_autre_structure_idor():
    owner_token, _ = _guest("upload-owner-private")
    outsider_token, _ = _guest("upload-outsider-private")
    slug = _create_structure(owner_token, "Private Structure A", "private-a")
    other_slug = _create_structure(outsider_token, "Private Structure B", "private-b")
    uploaded = _upload(slug, owner_token, "secret.pdf", PDF_MIN, "application/pdf").json()

    assert client.get(f"/forum/structures/{slug}/files/{uploaded['id']}/content").status_code == 401
    denied = client.get(f"/forum/structures/{slug}/files/{uploaded['id']}/content", headers=_auth(outsider_token))
    assert denied.status_code == 403
    cross_tenant = client.get(f"/forum/structures/{other_slug}/files/{uploaded['id']}", headers=_auth(outsider_token))
    assert cross_tenant.status_code == 404


def test_fichier_document_respecte_audience_effective_et_uuid_direct():
    owner_token, _ = _guest("storage-parent-owner")
    member_token, member_id = _guest("storage-parent-member")
    treasurer_token, treasurer_id = _guest("storage-parent-treasurer")
    office_token, office_id = _guest("storage-parent-office")
    slug = _create_structure(owner_token, "Storage Parent Policy", "storage-parent-create")
    _join_structure(slug, owner_token, member_token, "storage-parent-member-join")
    _join_structure(slug, owner_token, treasurer_token, "storage-parent-treasurer-join")
    _join_structure(slug, owner_token, office_token, "storage-parent-office-join")
    _assign_system_role(slug, owner_token, treasurer_id, "TREASURER")
    _assign_system_role(slug, owner_token, office_id, "MANAGER")

    treasury = _upload(slug, owner_token, "treasury.pdf", PDF_MIN, "application/pdf").json()
    _attach_document(slug, owner_token, treasury["id"], "TREASURY", "storage-parent-treasury-doc")
    treasury_url = f"/forum/structures/{slug}/files/{treasury['id']}/content"
    assert client.get(treasury_url, headers=_auth(member_token)).status_code == 403
    assert client.get(treasury_url, headers=_auth(treasurer_token)).status_code == 200

    members = _upload(slug, owner_token, "members.pdf", PDF_MIN, "application/pdf").json()
    _attach_document(slug, owner_token, members["id"], "STRUCTURE_MEMBERS", "storage-parent-members-doc")
    assert client.get(
        f"/forum/structures/{slug}/files/{members['id']}/content",
        headers=_auth(member_token),
    ).status_code == 200

    office = _upload(slug, owner_token, "office.pdf", PDF_MIN, "application/pdf").json()
    _attach_document(slug, owner_token, office["id"], "OFFICE", "storage-parent-office-doc")
    office_url = f"/forum/structures/{slug}/files/{office['id']}/content"
    assert client.get(office_url, headers=_auth(member_token)).status_code == 403
    assert client.get(office_url, headers=_auth(office_token)).status_code == 200


def test_fichier_prive_non_lie_n_est_pas_accessible_a_tout_membre():
    owner_token, _ = _guest("storage-unbound-owner")
    member_token, _ = _guest("storage-unbound-member")
    slug = _create_structure(owner_token, "Storage Unbound Policy", "storage-unbound-create")
    _join_structure(slug, owner_token, member_token, "storage-unbound-member-join")
    uploaded = _upload(slug, owner_token, "unbound.pdf", PDF_MIN, "application/pdf").json()

    direct = client.get(
        f"/forum/structures/{slug}/files/{uploaded['id']}/content",
        headers=_auth(member_token),
    )
    assert direct.status_code == 403


def test_suppression_non_autorisee():
    owner_token, _ = _guest("upload-owner-delete")
    outsider_token, _ = _guest("upload-outsider-delete")
    slug = _create_structure(owner_token, "Delete Structure", "delete-structure")
    uploaded = _upload(slug, owner_token, "secret.pdf", PDF_MIN, "application/pdf").json()

    denied = client.delete(f"/forum/structures/{slug}/files/{uploaded['id']}", headers=_auth(outsider_token))
    assert denied.status_code == 403
    assert client.get(f"/forum/structures/{slug}/files/{uploaded['id']}", headers=_auth(owner_token)).status_code == 200


def test_publication_requiert_action_et_confirmation_explicites():
    token, _ = _guest("upload-owner-publish")
    slug = _create_structure(token, "Publish Structure", "publish-structure")
    uploaded = _upload(slug, token, "photo.png", PNG_1X1, "image/png", purpose="ALBUM_MEDIA").json()

    missing_confirmation = client.patch(
        f"/forum/structures/{slug}/files/{uploaded['id']}/visibility",
        headers=_auth(token),
        json={"visibility": "PUBLIC"},
    )
    assert missing_confirmation.status_code == 409
    assert client.get(f"/forum/public/files/{uploaded['id']}").status_code == 404

    structure_published = client.post(
        f"/forum/structures/{slug}/publish",
        headers={**_auth(token), "Idempotency-Key": "publish-storage-structure"},
        json={"reason": "Publication explicite avant exposition du fichier"},
    )
    assert structure_published.status_code == 200

    published = client.patch(
        f"/forum/structures/{slug}/files/{uploaded['id']}/visibility",
        headers=_auth(token),
        json={"visibility": "PUBLIC", "confirm_public": True},
    )
    assert published.status_code == 200
    assert published.json()["visibility"] == "PUBLIC"
    public_content = client.get(f"/forum/public/files/{uploaded['id']}")
    assert public_content.status_code == 200
    assert public_content.content == PNG_1X1


def test_docx_valide_est_detecte_par_conteneur_reel():
    token, _ = _guest("upload-owner-docx")
    slug = _create_structure(token, "Upload DOCX", "upload-docx")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    response = _upload(
        slug,
        token,
        "passation.docx",
        buffer.getvalue(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert response.status_code == 201
    assert response.json()["mime"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
