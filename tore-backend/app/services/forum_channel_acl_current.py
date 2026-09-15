from __future__ import annotations

from sqlalchemy.orm import Session
from models import OrganizationMembership, StructureDiscussionChannel
from app.forum_acl_models import StructureChannelAcl, StructureChannelAclGrant
from app.models.structure_rbac import StructureMembershipRole, StructureRole
from app.services.structure_rbac import capabilities_for_membership

ROLE_RANK={"FOLLOWER":0,"ANCIEN":0,"MEMBER":1,"STAFF":2,"COMMUNICATION":2,"ARCHIVIST":2,"TREASURER":3,"TRESORIER":3,"SECRETARY":3,"BUREAU":4,"VICE_PRESIDENT":4,"PRESIDENT":4,"MANAGER":4,"ADMIN":5,"OWNER":6}

def _fallback(level: str, membership: OrganizationMembership) -> bool:
    role=(membership.role or "MEMBER").upper(); rank=ROLE_RANK.get(role,0); level=(level or "STRUCTURE_MEMBERS").upper()
    return {"PUBLIC":True,"TORE_USERS":True,"STRUCTURE_MEMBERS":rank>=1,"STAFF":rank>=2,"OFFICE":rank>=4,"TREASURY":rank>=3,"ADMINS":rank>=5}.get(level,False)

def explicit_enabled(db: Session, channel_id: int) -> bool:
    row=db.get(StructureChannelAcl,channel_id); return bool(row and row.enabled)

def membership_role_ids(db: Session, membership: OrganizationMembership) -> set[int]:
    ids={x[0] for x in db.query(StructureMembershipRole.role_id).filter(StructureMembershipRole.membership_id==membership.id).all()}
    code=(membership.role or "MEMBER").upper()
    system=db.query(StructureRole.id).filter(StructureRole.scope_key==f"system:{code}").first()
    if system: ids.add(system[0])
    return ids

def can_read(db: Session, channel: StructureDiscussionChannel, membership: OrganizationMembership) -> bool:
    if (membership.role or "").upper()=="OWNER": return True
    acl=db.get(StructureChannelAcl,channel.id)
    if not acl or not acl.enabled: return _fallback(channel.visibility,membership)
    grants=db.query(StructureChannelAclGrant).filter(StructureChannelAclGrant.organization_id==channel.organization_id,StructureChannelAclGrant.channel_id==channel.id).all()
    if not grants: return False
    role_ids={str(x) for x in membership_role_ids(db,membership)}
    caps=capabilities_for_membership(db,membership)
    for grant in grants:
        if grant.subject_type=="MEMBER" and grant.subject_key==membership.user_id: return True
        if grant.subject_type=="ROLE" and grant.subject_key in role_ids: return True
        if grant.subject_type=="CAPABILITY" and grant.subject_key in caps: return True
    return False
