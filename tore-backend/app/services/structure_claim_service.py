from __future__ import annotations

import unicodedata
from datetime import timedelta
from difflib import SequenceMatcher
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from db import now_utc
from models import (
    AppUser,
    Organization,
    OrganizationMembership,
    StructureClaim,
)
from app.services.audit_service import write_audit_log


CLAIM_STATUSES = {"PENDING", "NEEDS_INFO", "APPROVED", "REJECTED", "CANCELLED"}
ACTIVE_CLAIM_STATUSES = {"PENDING", "NEEDS_INFO"}
REVIEW_TARGET_STATUSES = {"NEEDS_INFO", "APPROVED", "REJECTED"}
TERMINAL_CLAIM_STATUSES = {"APPROVED", "REJECTED", "CANCELLED"}


def _normalize(value: str | None) -> str:
    raw = unicodedata.normalize("NFKD", (value or "").casefold())
    return " ".join("".join(ch for ch in raw if not unicodedata.combining(ch)).split())


def _audit(
    db: Session,
    *,
    claim: StructureClaim,
    actor: AppUser,
    action: str,
    from_status: Optional[str],
    to_status: str,
    payload: Optional[dict] = None,
) -> None:
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=actor.id,
        actor_role=(actor.global_role or "USER").upper(),
        action=action,
        entity_type="structure_claim",
        entity_id=str(claim.id),
        event_id=None,
        committee_id=None,
        bar_id=None,
        payload={
            "claim_id": claim.id,
            "structure_id": claim.structure_id,
            "claimant_user_id": claim.claimant_user_id,
            "from_status": from_status,
            "to_status": to_status,
            **(payload or {}),
        },
    )


def claim_payload(claim: StructureClaim) -> dict:
    evidence = claim.evidence_json if isinstance(claim.evidence_json, list) else []
    return {
        "id": claim.id,
        "structureId": claim.structure_id,
        "claimantUserId": claim.claimant_user_id,
        "reason": claim.reason,
        "evidence": evidence,
        "status": (claim.status or "PENDING").upper(),
        "reviewerUserId": claim.reviewer_user_id,
        "reviewNotes": claim.review_notes,
        "createdAt": claim.created_at.isoformat() if claim.created_at else None,
        "updatedAt": claim.updated_at.isoformat() if claim.updated_at else None,
        "reviewedAt": claim.reviewed_at.isoformat() if claim.reviewed_at else None,
        "decidedAt": claim.decided_at.isoformat() if claim.decided_at else None,
        "cancelledAt": claim.cancelled_at.isoformat() if claim.cancelled_at else None,
    }


def similar_structures(
    db: Session,
    *,
    name: str,
    city: str | None = None,
    limit: int = 8,
) -> list[dict]:
    wanted = _normalize(name)
    if len(wanted) < 2:
        return []
    city_normalized = _normalize(city)
    # The Forum directory is still intentionally small. Capping candidates keeps
    # this preflight predictable while avoiding a fuzzy-search dependency.
    candidates = db.query(Organization).order_by(Organization.id.desc()).limit(500).all()
    matches: list[dict] = []
    for org in candidates:
        if (org.visibility or "PRIVATE").upper() != "PUBLIC":
            continue
        candidate = _normalize(org.name)
        if not candidate:
            continue
        score = SequenceMatcher(None, wanted, candidate).ratio()
        if wanted in candidate or candidate in wanted:
            score = max(score, 0.92)
        if city_normalized and _normalize(org.city) == city_normalized:
            score = min(1.0, score + 0.05)
        if score < 0.45:
            continue
        matches.append(
            {
                "id": org.id,
                "slug": org.slug,
                "name": org.name,
                "city": org.city,
                "type": (org.org_type or "OTHER").upper(),
                "score": round(score, 3),
                "likelyDuplicate": score >= 0.86,
            }
        )
    matches.sort(key=lambda item: (-float(item["score"]), str(item["name"]).casefold()))
    return matches[: max(1, min(limit, 20))]


def create_claim(
    db: Session,
    *,
    structure: Organization,
    claimant: AppUser,
    reason: str,
    evidence: Iterable[str],
) -> StructureClaim:
    now = now_utc()
    recent_count = (
        db.query(StructureClaim)
        .filter(
            StructureClaim.claimant_user_id == claimant.id,
            StructureClaim.created_at >= now - timedelta(hours=1),
        )
        .count()
    )
    if recent_count >= 5:
        raise HTTPException(
            status_code=429,
            detail={
                "reason": "STRUCTURE_CLAIM_RATE_LIMITED",
                "retry_after_seconds": 3600,
            },
            headers={"Retry-After": "3600"},
        )

    duplicate = (
        db.query(StructureClaim)
        .filter(
            StructureClaim.structure_id == structure.id,
            StructureClaim.claimant_user_id == claimant.id,
            StructureClaim.status.in_(ACTIVE_CLAIM_STATUSES),
        )
        .order_by(StructureClaim.id.desc())
        .first()
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "reason": "STRUCTURE_CLAIM_ALREADY_ACTIVE",
                "claim_id": duplicate.id,
                "status": duplicate.status,
            },
        )

    claim = StructureClaim(
        structure_id=structure.id,
        claimant_user_id=claimant.id,
        reason=reason.strip(),
        evidence_json=[item.strip() for item in evidence if item and item.strip()],
        status="PENDING",
        created_at=now,
        updated_at=now,
    )
    db.add(claim)
    db.flush()
    _audit(
        db,
        claim=claim,
        actor=claimant,
        action="structure_claim.created",
        from_status=None,
        to_status="PENDING",
        payload={"evidence_count": len(claim.evidence_json or [])},
    )
    db.commit()
    db.refresh(claim)
    return claim


def resubmit_claim(
    db: Session,
    *,
    claim_id: int,
    claimant: AppUser,
    reason: str,
    evidence: Iterable[str],
) -> StructureClaim:
    claim = (
        db.query(StructureClaim)
        .filter(StructureClaim.id == claim_id)
        .with_for_update()
        .first()
    )
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.claimant_user_id != claimant.id:
        raise HTTPException(status_code=403, detail={"reason": "STRUCTURE_CLAIM_NOT_OWNED"})
    current = (claim.status or "").upper()
    if current != "NEEDS_INFO":
        raise HTTPException(
            status_code=409,
            detail={"reason": "STRUCTURE_CLAIM_NOT_RESUBMITTABLE", "status": current},
        )
    previous_review_notes = claim.review_notes
    claim.reason = reason.strip()
    claim.evidence_json = [item.strip() for item in evidence if item and item.strip()]
    claim.status = "PENDING"
    claim.updated_at = now_utc()
    claim.review_notes = None
    _audit(
        db,
        claim=claim,
        actor=claimant,
        action="structure_claim.resubmitted",
        from_status=current,
        to_status="PENDING",
        payload={
            "evidence_count": len(claim.evidence_json or []),
            "previous_review_notes": previous_review_notes,
        },
    )
    db.commit()
    db.refresh(claim)
    return claim


def cancel_claim(db: Session, *, claim_id: int, claimant: AppUser) -> StructureClaim:
    claim = (
        db.query(StructureClaim)
        .filter(StructureClaim.id == claim_id)
        .with_for_update()
        .first()
    )
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.claimant_user_id != claimant.id:
        raise HTTPException(status_code=403, detail={"reason": "STRUCTURE_CLAIM_NOT_OWNED"})
    current = (claim.status or "").upper()
    if current not in ACTIVE_CLAIM_STATUSES:
        raise HTTPException(
            status_code=409,
            detail={"reason": "STRUCTURE_CLAIM_NOT_CANCELLABLE", "status": current},
        )
    now = now_utc()
    claim.status = "CANCELLED"
    claim.cancelled_at = now
    claim.updated_at = now
    _audit(
        db,
        claim=claim,
        actor=claimant,
        action="structure_claim.cancelled",
        from_status=current,
        to_status="CANCELLED",
    )
    db.commit()
    db.refresh(claim)
    return claim


def review_claim(
    db: Session,
    *,
    claim_id: int,
    reviewer: AppUser,
    target_status: str,
    review_notes: str | None,
) -> StructureClaim:
    target = target_status.upper()
    if target not in REVIEW_TARGET_STATUSES:
        raise HTTPException(status_code=422, detail={"reason": "INVALID_CLAIM_REVIEW_STATUS"})
    claim = (
        db.query(StructureClaim)
        .filter(StructureClaim.id == claim_id)
        .with_for_update()
        .first()
    )
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    current = (claim.status or "").upper()
    if current not in ACTIVE_CLAIM_STATUSES:
        raise HTTPException(
            status_code=409,
            detail={"reason": "STRUCTURE_CLAIM_ALREADY_DECIDED", "status": current},
        )
    structure = db.query(Organization).filter(Organization.id == claim.structure_id).first()
    if structure is None:
        raise HTTPException(status_code=404, detail="Structure not found")

    now = now_utc()
    claim.status = target
    claim.reviewer_user_id = reviewer.id
    claim.review_notes = (review_notes or "").strip() or None
    claim.reviewed_at = now
    claim.updated_at = now

    ownership_granted = False
    if target == "APPROVED":
        membership = (
            db.query(OrganizationMembership)
            .filter(
                OrganizationMembership.organization_id == claim.structure_id,
                OrganizationMembership.user_id == claim.claimant_user_id,
            )
            .with_for_update()
            .first()
        )
        if membership is None:
            membership = OrganizationMembership(
                organization_id=claim.structure_id,
                user_id=claim.claimant_user_id,
                role="OWNER",
                status="ACTIVE",
                joined_at=now,
                starts_at=now,
                visibility="PRIVATE",
                validation_source="STRUCTURE_CLAIM",
                validated_by_user_id=reviewer.id,
                validated_at=now,
                metadata_json={"structure_claim_id": claim.id},
                updated_at=now,
                created_at=now,
                created_by_user_id=reviewer.id,
            )
            db.add(membership)
        else:
            membership.role = "OWNER"
            membership.status = "ACTIVE"
            membership.starts_at = membership.starts_at or now
            membership.ends_at = None
            membership.validation_source = "STRUCTURE_CLAIM"
            membership.validated_by_user_id = reviewer.id
            membership.validated_at = now
            membership.revoked_at = None
            membership.revoked_by_user_id = None
            membership.revoke_reason = None
            membership.updated_at = now
            metadata = membership.metadata_json if isinstance(membership.metadata_json, dict) else {}
            membership.metadata_json = {**metadata, "structure_claim_id": claim.id}
        claim.decided_at = now
        ownership_granted = True
    elif target == "REJECTED":
        claim.decided_at = now

    action = {
        "APPROVED": "structure_claim.approved",
        "REJECTED": "structure_claim.rejected",
        "NEEDS_INFO": "structure_claim.needs_info",
    }[target]
    _audit(
        db,
        claim=claim,
        actor=reviewer,
        action=action,
        from_status=current,
        to_status=target,
        payload={
            "ownership_granted": ownership_granted,
            "granted_role": "OWNER" if ownership_granted else None,
            "review_notes": claim.review_notes,
        },
    )
    db.commit()
    db.refresh(claim)
    return claim
