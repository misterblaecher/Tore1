from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models import AppUser, AuditLog, Organization, StructureClaim
from app.legacy.monolith import get_current_user, get_db
from app.services.rate_limit_service import (
    RateLimitExceeded,
    enforce_rate_limit,
    standard_rate_limit_http_exception,
)
from app.services.structure_claim_service import (
    ACTIVE_CLAIM_STATUSES,
    claim_payload,
    cancel_claim,
    create_claim,
    resubmit_claim,
    review_claim,
    similar_structures,
)


router = APIRouter(prefix="/forum/structure-claims", tags=["forum-structure-claims"])


class StructureClaimCreateIn(BaseModel):
    structure_id: int = Field(gt=0)
    reason: str = Field(min_length=12, max_length=5000)
    evidence: list[str] = Field(default_factory=list, max_length=10)


class StructureClaimResubmitIn(BaseModel):
    reason: str = Field(min_length=12, max_length=5000)
    evidence: list[str] = Field(default_factory=list, max_length=10)


class StructureClaimReviewIn(BaseModel):
    status: Literal["NEEDS_INFO", "APPROVED", "REJECTED"]
    review_notes: Optional[str] = Field(default=None, max_length=5000)


def _require_reviewer(user: AppUser) -> None:
    # Ownership claims are a platform-governance action, not a structure-admin
    # shortcut. Existing structure roles therefore cannot self-approve a claim.
    if (user.global_role or "USER").upper() != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail={"reason": "STRUCTURE_CLAIM_REVIEW_REQUIRES_ADMIN"},
        )


def _rate_limit(scope: str, user_id: str) -> None:
    try:
        enforce_rate_limit(scope, user_id)
    except RateLimitExceeded as exc:
        raise standard_rate_limit_http_exception(
            exc.scope, exc.retry_after_seconds
        ) from exc


def _claim_with_structure(db: Session, claim: StructureClaim) -> dict:
    payload = claim_payload(claim)
    structure = db.query(Organization).filter(Organization.id == claim.structure_id).first()
    payload["structure"] = (
        {
            "id": structure.id,
            "slug": structure.slug,
            "name": structure.name,
            "city": structure.city,
            "type": (structure.org_type or "OTHER").upper(),
        }
        if structure
        else None
    )
    return payload


@router.get("/similar-structures")
def get_similar_structures(
    name: str = Query(min_length=2, max_length=140),
    city: Optional[str] = Query(default=None, max_length=120),
    limit: int = Query(default=8, ge=1, le=20),
    db: Session = Depends(get_db),
):
    return {
        "items": similar_structures(db, name=name, city=city, limit=limit),
    }


@router.post("")
def create_structure_claim(
    payload: StructureClaimCreateIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _rate_limit("structure_claim_create", user.id)
    structure = db.query(Organization).filter(Organization.id == payload.structure_id).first()
    if structure is None:
        raise HTTPException(status_code=404, detail="Structure not found")
    claim = create_claim(
        db,
        structure=structure,
        claimant=user,
        reason=payload.reason,
        evidence=payload.evidence,
    )
    return {"claim": _claim_with_structure(db, claim)}


@router.get("/mine")
def list_my_structure_claims(
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(StructureClaim)
        .filter(StructureClaim.claimant_user_id == user.id)
        .order_by(StructureClaim.created_at.desc(), StructureClaim.id.desc())
        .all()
    )
    return {"items": [_claim_with_structure(db, row) for row in rows]}


@router.get("/review-queue")
def list_structure_claim_review_queue(
    status: Optional[str] = Query(default=None, max_length=16),
    reviewer: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_reviewer(reviewer)
    query = db.query(StructureClaim)
    if status:
        wanted = status.upper()
        if wanted not in {"PENDING", "NEEDS_INFO", "APPROVED", "REJECTED", "CANCELLED"}:
            raise HTTPException(status_code=422, detail={"reason": "INVALID_CLAIM_STATUS"})
        query = query.filter(StructureClaim.status == wanted)
    else:
        query = query.filter(StructureClaim.status.in_(ACTIVE_CLAIM_STATUSES))
    rows = query.order_by(StructureClaim.created_at.asc(), StructureClaim.id.asc()).all()
    return {"items": [_claim_with_structure(db, row) for row in rows]}


@router.patch("/{claim_id}")
def resubmit_structure_claim(
    claim_id: int,
    payload: StructureClaimResubmitIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _rate_limit("structure_claim_update", user.id)
    claim = resubmit_claim(
        db,
        claim_id=claim_id,
        claimant=user,
        reason=payload.reason,
        evidence=payload.evidence,
    )
    return {"claim": _claim_with_structure(db, claim)}


@router.post("/{claim_id}/cancel")
def cancel_structure_claim(
    claim_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _rate_limit("structure_claim_update", user.id)
    claim = cancel_claim(db, claim_id=claim_id, claimant=user)
    return {"claim": _claim_with_structure(db, claim)}


@router.post("/{claim_id}/review")
def review_structure_claim(
    claim_id: int,
    payload: StructureClaimReviewIn,
    reviewer: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_reviewer(reviewer)
    _rate_limit("structure_claim_review", reviewer.id)
    claim = review_claim(
        db,
        claim_id=claim_id,
        reviewer=reviewer,
        target_status=payload.status,
        review_notes=payload.review_notes,
    )
    return {"claim": _claim_with_structure(db, claim)}


@router.get("/{claim_id}/audit")
def structure_claim_audit(
    claim_id: int,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    claim = db.query(StructureClaim).filter(StructureClaim.id == claim_id).first()
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.claimant_user_id != user.id and (user.global_role or "USER").upper() != "ADMIN":
        raise HTTPException(status_code=403, detail={"reason": "STRUCTURE_CLAIM_AUDIT_DENIED"})
    rows = (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_type == "structure_claim",
            AuditLog.entity_id == str(claim_id),
        )
        .order_by(AuditLog.ts.asc(), AuditLog.id.asc())
        .all()
    )
    return {
        "claimId": claim_id,
        "items": [
            {
                "id": row.id,
                "at": row.ts.isoformat() if row.ts else None,
                "actorUserId": row.actor_user_id,
                "actorRole": row.actor_role,
                "action": row.action,
                "payload": row.payload_json if isinstance(row.payload_json, dict) else {},
            }
            for row in rows
        ],
    }
