from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Literal, Optional
from sqlalchemy.orm import Session
from db import now_utc
from models import AppUser, Organization, OrganizationMembership, StructureClaim
from app.core.security.user_auth import get_current_user
from app.deps.db import get_db
from app.ownership_models import StructureOwnership
from app.routers.forum_ownership import _complete_ownership_change
from app.services.structure_claim_service import _audit, claim_payload

router=APIRouter(prefix="/forum/structure-claims",tags=["forum-structure-claims"])
class ReviewIn(BaseModel):
    status: Literal["NEEDS_INFO","APPROVED","REJECTED"]
    review_notes: Optional[str]=None

def _member(db,c,reviewer,now):
    m=db.query(OrganizationMembership).filter_by(organization_id=c.structure_id,user_id=c.claimant_user_id).with_for_update().first()
    if not m:
        m=OrganizationMembership(organization_id=c.structure_id,user_id=c.claimant_user_id,role="MEMBER",status="ACTIVE",joined_at=now,starts_at=now,visibility="PRIVATE",validation_source="STRUCTURE_CLAIM",validated_by_user_id=reviewer.id,validated_at=now,metadata_json={"structure_claim_id":c.id},updated_at=now,created_at=now,created_by_user_id=reviewer.id); db.add(m); db.flush()
    else:
        m.status="ACTIVE"; m.starts_at=m.starts_at or now; m.ends_at=None; m.validation_source="STRUCTURE_CLAIM"; m.validated_by_user_id=reviewer.id; m.validated_at=now; m.revoked_at=None; m.updated_at=now
    return m

@router.post("/{claim_id}/review")
def review_claim_with_ownership(claim_id:int,payload:ReviewIn,reviewer:AppUser=Depends(get_current_user),db:Session=Depends(get_db)):
    if (reviewer.global_role or "USER").upper()!="ADMIN": raise HTTPException(403,detail={"reason":"STRUCTURE_CLAIM_REVIEW_REQUIRES_ADMIN"})
    c=db.query(StructureClaim).filter_by(id=claim_id).with_for_update().first()
    if not c: raise HTTPException(404,detail="Claim not found")
    old=(c.status or "").upper(); target=payload.status
    if old not in {"PENDING","NEEDS_INFO"}: raise HTTPException(409,detail={"reason":"STRUCTURE_CLAIM_ALREADY_DECIDED","status":old})
    org=db.query(Organization).filter_by(id=c.structure_id).first()
    if not org: raise HTTPException(404,detail="Structure not found")
    now=now_utc(); c.status=target; c.reviewer_user_id=reviewer.id; c.review_notes=(payload.review_notes or "").strip() or None; c.reviewed_at=now; c.updated_at=now; granted=False
    if target=="APPROVED":
        m=_member(db,c,reviewer,now); state=db.query(StructureOwnership).filter_by(organization_id=org.id).with_for_update().first()
        if state is None:
            owners=db.query(OrganizationMembership).filter_by(organization_id=org.id,role="OWNER",status="ACTIVE").all()
            if len(owners)>1: raise HTTPException(409,detail={"reason":"ownership_ambiguous"})
            if owners: state=StructureOwnership(organization_id=org.id,primary_owner_user_id=owners[0].user_id,updated_at=now); db.add(state); db.flush()
            else: m.role="OWNER"; state=StructureOwnership(organization_id=org.id,primary_owner_user_id=c.claimant_user_id,updated_at=now); db.add(state); db.flush()
        if state.primary_owner_user_id!=c.claimant_user_id: _complete_ownership_change(db,org,state,new_owner_user_id=c.claimant_user_id,actor_user_id=reviewer.id,actor_role="ADMIN",source="STRUCTURE_CLAIM",source_id=c.id)
        else: m.role="OWNER"
        c.decided_at=now; granted=True
    elif target=="REJECTED": c.decided_at=now
    _audit(db,claim=c,actor=reviewer,action={"APPROVED":"structure_claim.approved","REJECTED":"structure_claim.rejected","NEEDS_INFO":"structure_claim.needs_info"}[target],from_status=old,to_status=target,payload={"ownership_granted":granted,"granted_role":"OWNER" if granted else None,"review_notes":c.review_notes})
    db.commit(); db.refresh(c); out=claim_payload(c); out["structure"]={"id":org.id,"slug":org.slug,"name":org.name,"city":org.city,"type":(org.org_type or "OTHER").upper()}; return {"claim":out}
