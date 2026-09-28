from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import AppUser
from app.legacy.monolith import get_current_user
from app.deps.db import get_db
from app.routers.forum import _structure_or_404
from app.models.notifications import StructureNotification
from app.services.structure_rbac import capabilities_for_user
router = APIRouter(prefix="/forum", tags=["forum-notifications"])
def _visible(db, org_id, user, row):
    try: _, caps = capabilities_for_user(db, org_id, user.id)
    except HTTPException: return False
    return not row.target_permission or row.target_permission in caps
def _out(row):
    return {"id": row.id, "type": row.type, "title": row.title, "body": row.body, "targetPath": row.target_path, "targetId": row.target_id, "createdAt": row.created_at.isoformat(), "readAt": row.read_at.isoformat() if row.read_at else None}
@router.get("/structures/{slug}/notifications")
def list_notifications(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); rows = db.query(StructureNotification).filter_by(organization_id=org.id, user_id=user.id).order_by(StructureNotification.created_at.desc()).limit(50).all(); visible = [row for row in rows if _visible(db, org.id, user, row)]
    return {"items": [_out(row) for row in visible], "unreadCount": sum(row.read_at is None for row in visible)}
@router.patch("/structures/{slug}/notifications/{notification_id}/read")
def mark_notification_read(slug: str, notification_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); row = db.query(StructureNotification).filter_by(id=notification_id, organization_id=org.id, user_id=user.id).first()
    if row is None or not _visible(db, org.id, user, row): raise HTTPException(404, "Notification not found")
    row.read_at = row.read_at or datetime.utcnow(); db.commit(); return _out(row)
@router.post("/structures/{slug}/notifications/read-all")
def mark_all_notifications_read(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); rows = db.query(StructureNotification).filter_by(organization_id=org.id, user_id=user.id, read_at=None).all(); now = datetime.utcnow()
    for row in rows:
        if _visible(db, org.id, user, row): row.read_at = now
    db.commit(); return {"ok": True}
