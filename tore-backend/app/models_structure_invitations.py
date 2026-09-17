from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from db import Base, now_utc
class StructureInvitation(Base):
    __tablename__="structure_invitations"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    structure_id:Mapped[int]=mapped_column(ForeignKey("organizations.id"),index=True)
    email:Mapped[str]=mapped_column(String(255),index=True)
    token_hash:Mapped[str]=mapped_column(String(64),unique=True,index=True)
    invited_role:Mapped[str]=mapped_column(String(64),default="MEMBER",index=True)
    invited_role_id:Mapped[Optional[int]]=mapped_column(ForeignKey("structure_roles.id"),nullable=True,index=True)
    invited_by:Mapped[str]=mapped_column(ForeignKey("app_users.id"),index=True)
    expires_at:Mapped[datetime]=mapped_column(DateTime,index=True)
    accepted_at:Mapped[Optional[datetime]]=mapped_column(DateTime,nullable=True,index=True)
    declined_at:Mapped[Optional[datetime]]=mapped_column(DateTime,nullable=True,index=True)
    revoked_at:Mapped[Optional[datetime]]=mapped_column(DateTime,nullable=True,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=now_utc,index=True)
