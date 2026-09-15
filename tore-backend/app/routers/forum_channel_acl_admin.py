from __future__ import annotations

"""Management-only channel metadata for ACL configuration.

A user with ``channels.manage`` may need to edit a channel ACL without being a
member of that ACL. This endpoint deliberately exposes channel metadata only;
it does not grant or imply read access to channel content.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from models import AppUser, StructureDiscussionChannel
from app.legacy.monolith import get_current_user, get_db
from app.routers.forum_backend import _ctx, _organization
from app.services.forum_authorization import normalize_visibility
from app.services.forum_channel_acl import ChannelAclService


router = APIRouter(prefix="/forum/v2", tags=["forum-v2-channel-acl"])


@router.get("/structures/{slug}/channel-acl-options")
def list_channel_acl_options(
    slug: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _organization(db, slug)
    _ctx(db, org, user, "channels.manage")
    channels = db.query(StructureDiscussionChannel).filter_by(
        organization_id=org.id,
        is_archived=False,
    ).order_by(StructureDiscussionChannel.id).all()
    return {
        "items": [
            {
                "id": channel.id,
                "categoryId": channel.category_id,
                "name": channel.name,
                "visibility": normalize_visibility(channel.visibility),
                "aclExplicit": ChannelAclService.explicit_enabled(db, channel),
            }
            for channel in channels
        ]
    }
