from __future__ import annotations

import base64
import logging
import os
from datetime import datetime, timedelta
from typing import Iterator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.schemas.p3 import (
    AuditLogOut,
    BattleCreateIn,
    BattleJoinIn,
    BattleSubmitIn,
    BattleValidateIn,
    BuddyEndIn,
    BuddyPingIn,
    BuddyStartIn,
    CheckinIn,
    WifiSetIn,
)
from app.services.audit_service import write_audit_log
from app.services.entry_service import get_owned_event_or_403
from app.services.p3_common import decode_cursor, effective_module_state, encode_cursor, ensure_event_action_allowed, ensure_event_module_enabled, is_event_live
from db import now_utc
from models import (
    AuditLog,
    Battle,
    BattleJoin,
    BattleSubmit,
    Drink,
    DrinkCheckin,
    Event,
    SafetyBuddySession,
    WifiConfig,
)
from partner_auth import current_identity, require_role

router = APIRouter(tags=["p3"])


def get_db() -> Iterator[Session]:
    from app.legacy.monolith import get_db as _get_db

    yield from _get_db()


security = HTTPBearer(auto_error=False)


def _ux_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})

def _app_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    from app.legacy.monolith import get_current_user

    return get_current_user(credentials=credentials, db=db)


def _scope_event_id(battle: Battle) -> Optional[int]:
    return battle.event_id


def _ensure_battles_enabled(db: Session, event_id: int) -> None:
    try:
        ensure_event_module_enabled(db, event_id, "battles_enabled")
    except HTTPException as exc:
        if exc.status_code == 412 and isinstance(exc.detail, dict) and exc.detail.get("reason") == "module_off":
            raise HTTPException(status_code=409, detail=exc.detail) from exc
        raise


def _xor_cipher(value: str, key: str) -> str:
    raw = value.encode("utf-8")
    key_b = key.encode("utf-8")
    out = bytes(raw[i] ^ key_b[i % len(key_b)] for i in range(len(raw)))
    return base64.urlsafe_b64encode(out).decode("utf-8")


def _xor_decipher(value: str, key: str) -> str:
    raw = base64.urlsafe_b64decode(value.encode("utf-8"))
    key_b = key.encode("utf-8")
    out = bytes(raw[i] ^ key_b[i % len(key_b)] for i in range(len(raw)))
    return out.decode("utf-8")


@router.post("/battles/create")
def battles_create(payload: BattleCreateIn, identity=Depends(require_role("manager")), db: Session = Depends(get_db)):
    if not payload.event_id and not payload.bar_id:
        raise HTTPException(422, "event_id or bar_id required")
    bar_id = payload.bar_id or identity["bar_id"]
    event_id = payload.event_id
    if event_id is not None:
        event = get_owned_event_or_403(db, event_id, identity["bar_id"])
        _ensure_battles_enabled(db, event_id)
        bar_id = event.bar_id
    elif bar_id != identity["bar_id"]:
        raise HTTPException(403, "Forbidden")

    battle = Battle(bar_id=bar_id, event_id=event_id, mode=payload.mode, title="Battle", created_by_user_id=str(identity["user_id"]), is_active=True)
    db.add(battle)
    db.commit()
    return {"id": battle.id, "event_id": battle.event_id, "bar_id": battle.bar_id, "mode": battle.mode, "status": "LIVE"}


@router.get("/battles/{battle_id}")
def battles_get(battle_id: int, db: Session = Depends(get_db)):
    battle = db.get(Battle, battle_id)
    if not battle:
        raise HTTPException(404, "Battle not found")
    if battle.event_id and not is_event_live(db, battle.event_id):
        return Response(status_code=204)
    return {"id": battle.id, "event_id": battle.event_id, "bar_id": battle.bar_id, "mode": battle.mode, "status": "LIVE" if battle.is_active else "DONE"}


@router.post("/battles/{battle_id}/join")
def battles_join(battle_id: int, payload: BattleJoinIn, user=Depends(_app_user), db: Session = Depends(get_db)):
    battle = db.get(Battle, battle_id)
    if not battle:
        raise HTTPException(404, "Battle not found")
    if battle.event_id:
        _ensure_battles_enabled(db, battle.event_id)
    existing = db.query(BattleJoin).filter(BattleJoin.battle_id == battle_id, BattleJoin.user_id == user.id).first()
    if existing:
        return {"ok": True, "idempotent": True, "battle_id": battle_id}
    db.add(BattleJoin(battle_id=battle_id, user_id=user.id, joined_at=now_utc()))
    db.commit()
    return {"ok": True, "idempotent": False, "battle_id": battle_id}


@router.post("/battles/{battle_id}/submit")
def battles_submit(battle_id: int, payload: BattleSubmitIn, user=Depends(_app_user), db: Session = Depends(get_db)):
    battle = db.get(Battle, battle_id)
    if not battle:
        raise HTTPException(404, "Battle not found")
    if battle.event_id:
        _ensure_battles_enabled(db, battle.event_id)
    recent_submit_count = (
        db.query(func.count(BattleSubmit.id))
        .filter(BattleSubmit.battle_id == battle_id, BattleSubmit.actor_user_id == user.id, BattleSubmit.created_at >= now_utc() - timedelta(seconds=10))
        .scalar()
        or 0
    )
    if int(recent_submit_count) >= 20:
        raise _ux_error(429, "BATTLES_RATE_LIMIT", "Trop d'actions, réessaie dans quelques secondes.")
    existing = db.query(BattleSubmit).filter(BattleSubmit.battle_id == battle_id, BattleSubmit.scan_id == payload.scan_id).first()
    if existing:
        return {"submit_id": existing.id, "idempotent": True}
    row = BattleSubmit(
        battle_id=battle_id,
        actor_user_id=user.id,
        scan_id=payload.scan_id,
        target_user_id=payload.target_user_id,
        points=max(1, payload.points),
    )
    db.add(row)
    db.commit()
    return {"submit_id": row.id, "idempotent": False}


@router.post("/battles/{battle_id}/validate")
def battles_validate(battle_id: int, payload: BattleValidateIn, identity=Depends(current_identity), db: Session = Depends(get_db)):
    if identity["role"] not in {"manager", "bartender"}:
        raise HTTPException(403, "Forbidden")
    battle = db.get(Battle, battle_id)
    if not battle:
        raise HTTPException(404, "Battle not found")
    if battle.event_id:
        get_owned_event_or_403(db, battle.event_id, identity["bar_id"])
    submit = db.get(BattleSubmit, payload.submit_id)
    if not submit or submit.battle_id != battle_id:
        raise HTTPException(404, "Submit not found")
    if submit.validated_at:
        raise HTTPException(409, "already validated")
    submit.validated_at = now_utc()
    submit.validated_by_partner_id = identity["user_id"]
    db.add(submit)
    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="battle.validate",
        entity_type="battle_submit",
        entity_id=str(submit.id),
        event_id=battle.event_id,
        bar_id=battle.bar_id,
        payload={"battle_id": battle_id, "submit_id": submit.id},
    )
    db.commit()
    return {"ok": True}


@router.get("/battles/{battle_id}/leaderboard")
def battles_leaderboard(battle_id: int, db: Session = Depends(get_db)):
    battle = db.get(Battle, battle_id)
    if not battle:
        raise HTTPException(404, "Battle not found")
    if battle.event_id and not is_event_live(db, battle.event_id):
        return Response(status_code=204)
    rows = (
        db.query(BattleSubmit.actor_user_id, func.coalesce(func.sum(BattleSubmit.points), 0).label("score"))
        .filter(BattleSubmit.battle_id == battle_id, BattleSubmit.validated_at.is_not(None))
        .group_by(BattleSubmit.actor_user_id)
        .order_by(func.coalesce(func.sum(BattleSubmit.points), 0).desc(), BattleSubmit.actor_user_id.asc())
        .all()
    )
    return {"battle_id": battle_id, "rows": [{"user_id": r[0], "score": int(r[1])} for r in rows]}


@router.get("/battles/event/{event_id}")
def battles_event_list(event_id: int, db: Session = Depends(get_db)):
    if not is_event_live(db, event_id):
        return Response(status_code=204)
    rows = db.query(Battle).filter(Battle.event_id == event_id).order_by(Battle.created_at.desc(), Battle.id.desc()).all()
    return [{"id": r.id, "mode": r.mode, "status": "LIVE" if r.is_active else "DONE"} for r in rows]


@router.post("/drinks/checkin")
def drinks_checkin(payload: CheckinIn, user=Depends(_app_user), db: Session = Depends(get_db)):
    if not payload.drink_id and not payload.free_text_name:
        raise HTTPException(422, "drink_id or free_text_name required")
    name = payload.free_text_name or ""
    if payload.drink_id:
        drink = db.get(Drink, payload.drink_id)
        if not drink:
            raise HTTPException(404, "Drink not found")
        name = drink.name
    if payload.event_id:
        ensure_event_module_enabled(db, payload.event_id, "checkins_enabled")
    recent_checkins = (
        db.query(func.count(DrinkCheckin.id))
        .filter(DrinkCheckin.user_id == user.id, DrinkCheckin.ts >= now_utc() - timedelta(minutes=1))
        .scalar()
        or 0
    )
    if int(recent_checkins) >= 12:
        raise _ux_error(429, "CHECKIN_RATE_LIMIT", "Tu vas trop vite, attends quelques secondes.")
    row = DrinkCheckin(user_id=user.id, drink_id=payload.drink_id, name_snapshot=name, rating=payload.rating, comment=payload.comment, event_id=payload.event_id, bar_id=payload.bar_id)
    db.add(row)
    db.commit()
    return {"id": row.id, "name_snapshot": row.name_snapshot}


@router.get("/drinks/checkins/me")
def drinks_checkins_me(cursor: Optional[str] = Query(default=None), limit: int = Query(default=20, ge=1, le=100), user=Depends(_app_user), db: Session = Depends(get_db)):
    c_ts, c_id = decode_cursor(cursor)
    q = db.query(DrinkCheckin).filter(DrinkCheckin.user_id == user.id)
    if c_ts and c_id:
        q = q.filter(or_(DrinkCheckin.ts < c_ts, and_(DrinkCheckin.ts == c_ts, DrinkCheckin.id < c_id)))
    rows = q.order_by(DrinkCheckin.ts.desc(), DrinkCheckin.id.desc()).limit(limit + 1).all()
    next_cursor = None
    if len(rows) > limit:
        tail = rows[limit - 1]
        next_cursor = encode_cursor(tail.ts, tail.id)
        rows = rows[:limit]
    return {"items": [{"id": r.id, "name_snapshot": r.name_snapshot, "rating": r.rating, "ts": r.ts.isoformat()} for r in rows], "next_cursor": next_cursor}


@router.get("/drinks/checkins/event/{event_id}")
def drinks_checkins_event(event_id: int, db: Session = Depends(get_db)):
    if not is_event_live(db, event_id):
        return Response(status_code=204)
    rows = db.query(DrinkCheckin.name_snapshot, func.count(DrinkCheckin.id)).filter(DrinkCheckin.event_id == event_id).group_by(DrinkCheckin.name_snapshot).order_by(func.count(DrinkCheckin.id).desc(), DrinkCheckin.name_snapshot.asc()).all()
    return {"event_id": event_id, "top_drinks": [{"name": r[0], "count": int(r[1])} for r in rows]}


@router.get("/partner/portal/checkins/logs")
def portal_checkins_logs(
    event_id: int,
    search: Optional[str] = Query(default=None),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    get_owned_event_or_403(db, event_id, identity["bar_id"])
    c_ts, c_id = decode_cursor(cursor)
    q = db.query(DrinkCheckin).filter(DrinkCheckin.event_id == event_id)
    if search:
        q = q.filter(DrinkCheckin.name_snapshot.ilike(f"%{search.strip()}%"))
    if c_ts and c_id:
        q = q.filter(or_(DrinkCheckin.ts < c_ts, and_(DrinkCheckin.ts == c_ts, DrinkCheckin.id < c_id)))
    rows = q.order_by(DrinkCheckin.ts.desc(), DrinkCheckin.id.desc()).limit(limit + 1).all()
    next_cursor = None
    if len(rows) > limit:
        tail = rows[limit - 1]
        next_cursor = encode_cursor(tail.ts, tail.id)
        rows = rows[:limit]
    return {
        "items": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "name_snapshot": r.name_snapshot,
                "rating": r.rating,
                "comment": r.comment,
                "ts": r.ts.isoformat(),
            }
            for r in rows
        ],
        "next_cursor": next_cursor,
    }


@router.get("/drinks/checkins/global/top")
def drinks_checkins_global(db: Session = Depends(get_db)):
    rows = db.query(DrinkCheckin.name_snapshot, func.count(DrinkCheckin.id)).group_by(DrinkCheckin.name_snapshot).order_by(func.count(DrinkCheckin.id).desc(), DrinkCheckin.name_snapshot.asc()).limit(100).all()
    return {"items": [{"name": r[0], "count": int(r[1])} for r in rows]}


@router.post("/partner/portal/wifi/set")
def wifi_set(payload: WifiSetIn, identity=Depends(require_role("manager")), db: Session = Depends(get_db)):
    if payload.bar_id != identity["bar_id"]:
        raise HTTPException(403, "Forbidden")
    if payload.event_id:
        get_owned_event_or_403(db, payload.event_id, identity["bar_id"])
        ensure_event_module_enabled(db, payload.event_id, "wifi_enabled")
    key = os.getenv("WIFI_CRED_KEY", "")
    if not key:
        logging.warning("WIFI_CRED_KEY missing: wifi password stored with reversible dev obfuscation")
        key = "dev-key"
    enc = _xor_cipher(payload.password, key)
    row = db.query(WifiConfig).filter(WifiConfig.bar_id == payload.bar_id, WifiConfig.event_id == payload.event_id).first()
    if not row:
        row = WifiConfig(bar_id=payload.bar_id, event_id=payload.event_id, ssid=payload.ssid, password_enc=enc, note=payload.note, created_by=identity["user_id"], updated_by=identity["user_id"], updated_at=now_utc())
    else:
        row.ssid = payload.ssid
        row.password_enc = enc
        row.note = payload.note
        row.updated_by = identity["user_id"]
        row.updated_at = now_utc()
    db.add(row)
    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="wifi.set",
        entity_type="wifi_config",
        entity_id=str(row.id if row.id else "new"),
        event_id=payload.event_id,
        bar_id=payload.bar_id,
        payload={"ssid": payload.ssid, "note": payload.note},
    )
    db.commit()
    return {"ok": True, "id": row.id}


@router.get("/public/wifi")
def wifi_public(bar_id: int, event_id: Optional[int] = None, db: Session = Depends(get_db)):
    if event_id:
        if not is_event_live(db, event_id):
            return Response(status_code=204)
        state, reason = effective_module_state(db, event_id, "wifi_enabled")
        if state == "OFF" and reason == "module_off":
            return Response(status_code=204)
        ensure_event_action_allowed(db, event_id, "wifi_enabled", write=True)
    row = db.query(WifiConfig).filter(WifiConfig.bar_id == bar_id, WifiConfig.event_id == event_id).first()
    if not row:
        return Response(status_code=204)
    key = os.getenv("WIFI_CRED_KEY", "") or "dev-key"
    return {"ssid": row.ssid, "password": _xor_decipher(row.password_enc, key), "note": row.note, "expires_at": None}


@router.post("/safety/buddy/start")
def safety_start(payload: BuddyStartIn, user=Depends(_app_user), db: Session = Depends(get_db)):
    if payload.event_id:
        ensure_event_action_allowed(db, payload.event_id, "safety_enabled", write=True)
    now = now_utc()
    row = SafetyBuddySession(event_id=payload.event_id, user_id=user.id, buddy_user_id=payload.buddy_user_id, status="ACTIVE", started_at=now, expires_at=now + timedelta(minutes=max(1, payload.expires_minutes)))
    db.add(row)
    db.commit()
    return {"session_id": row.id, "status": row.status}


@router.post("/safety/buddy/ping")
def safety_ping(payload: BuddyPingIn, user=Depends(_app_user), db: Session = Depends(get_db)):
    row = db.get(SafetyBuddySession, payload.session_id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "Session not found")
    if row.status != "ACTIVE":
        raise HTTPException(409, "Session not active")
    if row.event_id:
        ensure_event_action_allowed(db, row.event_id, "safety_enabled", write=True)
    now = now_utc()
    if row.expires_at and (now + timedelta(minutes=29, seconds=55)) <= row.expires_at <= (now + timedelta(minutes=30)):
        raise _ux_error(429, "BUDDY_PING_RATE_LIMIT", "Ping trop fréquent, attends 5 secondes.")
    row.expires_at = now + timedelta(minutes=30)
    db.add(row)
    db.commit()
    return {"ok": True}


@router.post("/safety/buddy/end")
def safety_end(payload: BuddyEndIn, user=Depends(_app_user), db: Session = Depends(get_db)):
    row = db.get(SafetyBuddySession, payload.session_id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "Session not found")
    if row.status != "ACTIVE":
        return {"ok": True, "idempotent": True}
    if row.event_id:
        ensure_event_action_allowed(db, row.event_id, "safety_enabled", write=True)
    row.status = "ENDED"
    row.ended_at = now_utc()
    db.add(row)
    db.commit()
    return {"ok": True, "idempotent": False}


@router.get("/safety/buddy/me")
def safety_me(user=Depends(_app_user), db: Session = Depends(get_db)):
    rows = db.query(SafetyBuddySession).filter(SafetyBuddySession.user_id == user.id, SafetyBuddySession.status == "ACTIVE").order_by(SafetyBuddySession.started_at.desc()).all()
    return {"items": [{"id": r.id, "buddy_user_id": r.buddy_user_id, "expires_at": r.expires_at.isoformat()} for r in rows]}


@router.get("/partner/portal/safety/event/{event_id}/stats")
def safety_stats(event_id: int, identity=Depends(require_role("manager")), db: Session = Depends(get_db)):
    event = get_owned_event_or_403(db, event_id, identity["bar_id"])
    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="safety.stats.view",
        entity_type="event",
        entity_id=str(event_id),
        event_id=event_id,
        bar_id=event.bar_id,
        payload={},
    )
    db.commit()
    total = db.query(func.count(SafetyBuddySession.id)).filter(SafetyBuddySession.event_id == event_id).scalar() or 0
    active = db.query(func.count(SafetyBuddySession.id)).filter(SafetyBuddySession.event_id == event_id, SafetyBuddySession.status == "ACTIVE").scalar() or 0
    recent = (
        db.query(SafetyBuddySession)
        .filter(SafetyBuddySession.event_id == event_id)
        .order_by(SafetyBuddySession.started_at.desc(), SafetyBuddySession.id.desc())
        .limit(10)
        .all()
    )
    return {
        "event_id": event_id,
        "total": int(total),
        "active": int(active),
        "recent_sessions": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "buddy_user_id": r.buddy_user_id,
                "status": r.status,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                "ended_at": r.ended_at.isoformat() if r.ended_at else None,
            }
            for r in recent
        ],
    }


@router.get("/partner/portal/audit/logs")
def portal_audit_logs(
    event_id: Optional[int] = None,
    actor_id: Optional[int] = None,
    type: Optional[str] = None,
    after: Optional[datetime] = None,
    before: Optional[datetime] = None,
    cursor: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    if event_id:
        get_owned_event_or_403(db, event_id, identity["bar_id"])
    c_ts, c_id = decode_cursor(cursor)
    q = db.query(AuditLog).filter(AuditLog.bar_id == identity["bar_id"])
    if event_id:
        q = q.filter(AuditLog.event_id == event_id)
    if actor_id:
        q = q.filter(AuditLog.actor_partner_id == actor_id)
    if type:
        q = q.filter(AuditLog.action == type)
    if after:
        q = q.filter(AuditLog.ts >= after)
    if before:
        q = q.filter(AuditLog.ts <= before)
    if c_ts and c_id:
        q = q.filter(or_(AuditLog.ts < c_ts, and_(AuditLog.ts == c_ts, AuditLog.id < c_id)))
    rows = q.order_by(AuditLog.ts.desc(), AuditLog.id.desc()).limit(limit + 1).all()
    next_cursor = None
    if len(rows) > limit:
        tail = rows[limit - 1]
        next_cursor = encode_cursor(tail.ts, tail.id)
        rows = rows[:limit]
    return {"items": [AuditLogOut.model_validate(r, from_attributes=True).model_dump() for r in rows], "next_cursor": next_cursor}
