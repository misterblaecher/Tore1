from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from db import Base, engine
from main import app
from models import AppUser, Organization, OrganizationMembership, StructureClaim


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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_admin(user_id: str) -> None:
    with Session(engine) as db:
        user = db.query(AppUser).filter(AppUser.id == user_id).one()
        user.global_role = "ADMIN"
        db.commit()


def _structure(created_by: str, *, name: str, slug: str) -> int:
    with Session(engine) as db:
        org = Organization(
            name=name,
            slug=slug,
            city="Liège",
            org_type="CIRCLE",
            visibility="PUBLIC",
            created_by_user_id=created_by,
        )
        db.add(org)
        db.commit()
        db.refresh(org)
        return org.id


def _membership(structure_id: int, user_id: str) -> OrganizationMembership | None:
    with Session(engine) as db:
        return (
            db.query(OrganizationMembership)
            .filter(
                OrganizationMembership.organization_id == structure_id,
                OrganizationMembership.user_id == user_id,
            )
            .first()
        )


def test_claim_is_pending_duplicate_is_controlled_and_claimant_gets_no_admin_rights():
    claimant_token, claimant_id = _guest("claimant-pending")
    _seed_token, seed_id = _guest("claim-seed")
    structure_id = _structure(seed_id, name="Cercle des Ingénieurs", slug="cercle-ingenieurs")

    similar = client.get(
        "/forum/structure-claims/similar-structures",
        params={"name": "Cercle Ingenieurs", "city": "Liège"},
    )
    assert similar.status_code == 200
    item = next(row for row in similar.json()["items"] if row["id"] == structure_id)
    assert item["likelyDuplicate"] is True

    created = client.post(
        "/forum/structure-claims",
        headers=_auth(claimant_token),
        json={
            "structure_id": structure_id,
            "reason": "Je représente actuellement cette structure et souhaite gérer sa page officielle.",
            "evidence": ["https://example.test/preuve"],
        },
    )
    assert created.status_code == 200
    claim = created.json()["claim"]
    assert claim["status"] == "PENDING"
    assert claim["claimantUserId"] == claimant_id

    # A claim is only a review request. It must not create any structure role.
    assert _membership(structure_id, claimant_id) is None
    denied = client.get(
        "/forum/structures/cercle-ingenieurs/dashboard",
        headers=_auth(claimant_token),
    )
    assert denied.status_code == 403

    self_approve = client.post(
        f"/forum/structure-claims/{claim['id']}/review",
        headers=_auth(claimant_token),
        json={"status": "APPROVED", "review_notes": "Auto-approbation interdite."},
    )
    assert self_approve.status_code == 403
    assert _membership(structure_id, claimant_id) is None

    duplicate = client.post(
        "/forum/structure-claims",
        headers=_auth(claimant_token),
        json={
            "structure_id": structure_id,
            "reason": "Deuxième demande qui ne doit pas créer un claim actif en doublon.",
            "evidence": [],
        },
    )
    assert duplicate.status_code == 409
    with Session(engine) as db:
        assert (
            db.query(StructureClaim)
            .filter(
                StructureClaim.structure_id == structure_id,
                StructureClaim.claimant_user_id == claimant_id,
            )
            .count()
            == 1
        )


def test_approval_is_the_only_transition_that_grants_owner_and_audit_is_complete():
    claimant_token, claimant_id = _guest("claimant-approved")
    reviewer_token, reviewer_id = _guest("claim-reviewer")
    _make_admin(reviewer_id)
    structure_id = _structure(reviewer_id, name="Ordre du Claim", slug="ordre-du-claim")

    created = client.post(
        "/forum/structure-claims",
        headers=_auth(claimant_token),
        json={
            "structure_id": structure_id,
            "reason": "Je suis le responsable mandaté et je fournis les éléments nécessaires à la vérification.",
            "evidence": ["PV de mandat 2026", "contact@ordre.test"],
        },
    )
    claim_id = created.json()["claim"]["id"]
    assert _membership(structure_id, claimant_id) is None

    approved = client.post(
        f"/forum/structure-claims/{claim_id}/review",
        headers=_auth(reviewer_token),
        json={"status": "APPROVED", "review_notes": "Mandat et contact vérifiés."},
    )
    assert approved.status_code == 200
    claim = approved.json()["claim"]
    assert claim["status"] == "APPROVED"
    assert claim["reviewerUserId"] == reviewer_id
    assert claim["decidedAt"]

    membership = _membership(structure_id, claimant_id)
    assert membership is not None
    assert membership.role == "OWNER"
    assert membership.status == "ACTIVE"
    assert membership.validation_source == "STRUCTURE_CLAIM"
    assert membership.validated_by_user_id == reviewer_id

    dashboard = client.get(
        "/forum/structures/ordre-du-claim/dashboard",
        headers=_auth(claimant_token),
    )
    assert dashboard.status_code == 200

    audit = client.get(
        f"/forum/structure-claims/{claim_id}/audit",
        headers=_auth(claimant_token),
    )
    assert audit.status_code == 200
    actions = [row["action"] for row in audit.json()["items"]]
    assert actions == ["structure_claim.created", "structure_claim.approved"]
    assert audit.json()["items"][-1]["payload"]["ownership_granted"] is True
    assert audit.json()["items"][-1]["payload"]["granted_role"] == "OWNER"


def test_rejection_changes_no_permission_and_is_audited():
    claimant_token, claimant_id = _guest("claimant-rejected")
    reviewer_token, reviewer_id = _guest("claim-reviewer-reject")
    _make_admin(reviewer_id)
    structure_id = _structure(reviewer_id, name="Cercle Refus", slug="cercle-refus")

    created = client.post(
        "/forum/structure-claims",
        headers=_auth(claimant_token),
        json={
            "structure_id": structure_id,
            "reason": "Je demande la gestion de cette structure avec les preuves disponibles pour review.",
            "evidence": ["preuve insuffisante"],
        },
    )
    claim_id = created.json()["claim"]["id"]
    rejected = client.post(
        f"/forum/structure-claims/{claim_id}/review",
        headers=_auth(reviewer_token),
        json={"status": "REJECTED", "review_notes": "Les preuves ne permettent pas de valider la demande."},
    )
    assert rejected.status_code == 200
    assert rejected.json()["claim"]["status"] == "REJECTED"
    assert _membership(structure_id, claimant_id) is None
    assert client.get(
        "/forum/structures/cercle-refus/dashboard",
        headers=_auth(claimant_token),
    ).status_code == 403

    audit = client.get(
        f"/forum/structure-claims/{claim_id}/audit",
        headers=_auth(claimant_token),
    ).json()["items"]
    assert [row["action"] for row in audit] == [
        "structure_claim.created",
        "structure_claim.rejected",
    ]
    assert audit[-1]["payload"]["ownership_granted"] is False


def test_needs_info_can_be_resubmitted_then_cancelled_without_permissions():
    claimant_token, claimant_id = _guest("claimant-needs-info")
    reviewer_token, reviewer_id = _guest("claim-reviewer-needs-info")
    _make_admin(reviewer_id)
    structure_id = _structure(reviewer_id, name="Comité Infos", slug="comite-infos")

    created = client.post(
        "/forum/structure-claims",
        headers=_auth(claimant_token),
        json={
            "structure_id": structure_id,
            "reason": "Première demande complète en apparence mais nécessitant encore une preuve.",
            "evidence": [],
        },
    )
    claim_id = created.json()["claim"]["id"]
    needs_info = client.post(
        f"/forum/structure-claims/{claim_id}/review",
        headers=_auth(reviewer_token),
        json={"status": "NEEDS_INFO", "review_notes": "Merci de joindre le PV du mandat."},
    )
    assert needs_info.status_code == 200
    assert needs_info.json()["claim"]["status"] == "NEEDS_INFO"
    assert _membership(structure_id, claimant_id) is None

    resubmitted = client.patch(
        f"/forum/structure-claims/{claim_id}",
        headers=_auth(claimant_token),
        json={
            "reason": "Je complète ma demande avec le PV de mandat demandé par la review TORÈ.",
            "evidence": ["PV mandat 2026"],
        },
    )
    assert resubmitted.status_code == 200
    assert resubmitted.json()["claim"]["status"] == "PENDING"
    assert _membership(structure_id, claimant_id) is None

    cancelled = client.post(
        f"/forum/structure-claims/{claim_id}/cancel",
        headers=_auth(claimant_token),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["claim"]["status"] == "CANCELLED"
    assert _membership(structure_id, claimant_id) is None

    audit = client.get(
        f"/forum/structure-claims/{claim_id}/audit",
        headers=_auth(claimant_token),
    ).json()["items"]
    assert [row["action"] for row in audit] == [
        "structure_claim.created",
        "structure_claim.needs_info",
        "structure_claim.resubmitted",
        "structure_claim.cancelled",
    ]


def test_claim_creation_is_rate_limited_per_user():
    claimant_token, claimant_id = _guest("claimant-rate-limit")
    _seed_token, seed_id = _guest("claim-rate-limit-seed")
    for index in range(6):
        structure_id = _structure(
            seed_id,
            name=f"Structure Rate {index}",
            slug=f"structure-rate-{index}",
        )
        response = client.post(
            "/forum/structure-claims",
            headers=_auth(claimant_token),
            json={
                "structure_id": structure_id,
                "reason": f"Demande de revendication numéro {index} avec justification suffisante.",
                "evidence": [],
            },
        )
        if index < 5:
            assert response.status_code == 200
        else:
            assert response.status_code == 429
            assert response.json()["detail"]["reason"] == "STRUCTURE_CLAIM_RATE_LIMITED"

    with Session(engine) as db:
        assert (
            db.query(StructureClaim)
            .filter(StructureClaim.claimant_user_id == claimant_id)
            .count()
            == 5
        )
