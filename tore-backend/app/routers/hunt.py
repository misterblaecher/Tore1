from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Iterator, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.routers.wallet import get_current_user
from app.schemas.hunt import (
    HuntCreateIn,
    HuntEventOut,
    HuntOut,
    HuntPatchIn,
    HuntPointCreateIn,
    HuntPointOut,
    HuntPointPatchIn,
    HuntPointPublicOut,
    HuntScanIn,
    HuntScanOut,
    HuntStatsOut,
)
from app.services.audit_service import write_audit_log
from app.services.authz_service import ensure_partner_role
from app.services.hunt_service import (
    build_progress,
    generate_secret_code,
    get_event_for_bar,
    get_hunt_for_bar,
    hunt_stats,
    qr_payload,
    require_manager,
    route_front,
    scan_point,
)
from app.services.p3_common import effective_module_state, get_event_runtime_state
from app.services.qr_signing_service import sign_payload
from app.services.wallet_service import apply_wallet_tx
from db import now_utc
from models import (
    AppUserPrivacySetting,
    Event,
    EventHunt,
    EventHuntCheckpoint,
    EventHuntClaim,
    EventHuntIdempotency,
    EventHuntScore,
    EventHuntSteal,
    EventQrToken,
    Hunt,
    HuntPoint,
)
from partner_auth import current_identity as current_partner_identity

router = APIRouter()


class CheckpointIn(BaseModel):
    label: str = Field(min_length=1, max_length=180)
    points: int = Field(ge=1, le=200)
    rewardTickets: Optional[int] = Field(default=None, ge=0, le=500)
    orderIndex: int = Field(default=0, ge=0)


class HuntCreateV1In(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: Optional[str] = None
    startsAt: datetime
    endsAt: datetime
    rulesText: Optional[str] = None
    checkpoints: list[CheckpointIn] = Field(default_factory=list)


class HuntClaimIn(BaseModel):
    checkpointId: int
    token: str


class HuntStealIn(BaseModel):
    victimUserId: str


class HuntCloseOut(BaseModel):
    ok: bool
    huntId: int
    isActive: bool


def get_db() -> Iterator[Session]:
    from app.legacy.monolith import get_db as _get_db

    yield from _get_db()


def _require_orga_manager_identity(identity=Depends(current_partner_identity)):
    ensure_partner_role(identity, {"manager", "owner"})
    return identity


def _require_idempotency(idempotency_key: str | None) -> str:
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"reason": "missing_idempotency", "message": "Idempotency-Key required"})
    key = idempotency_key.strip()
    if len(key) < 4:
        raise HTTPException(status_code=400, detail={"reason": "invalid_idempotency"})
    return key


def _event_for_identity(db: Session, event_id: int, identity: dict) -> Event:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail={"reason": "event_not_found"})
    if event.bar_id != identity.get("bar_id"):
        raise HTTPException(status_code=403, detail={"reason": "forbidden"})
    return event


def _hunt_module_guard(db: Session, event_id: int, *, write: bool, critical: bool = False) -> None:
    state, reason = effective_module_state(db, event_id, "hunt_enabled")
    if state == "OFF":
        raise HTTPException(status_code=404, detail={"reason": "MODULE_OFF", "message": "Hunt module off"})
    if state == "READ_ONLY" and write:
        raise HTTPException(status_code=423, detail={"reason": reason or "read_only", "message": "Writes blocked"})
    if write and critical and get_event_runtime_state(db, event_id) == "DEGRADED":
        raise HTTPException(status_code=423, detail={"reason": "event_degraded_critical", "message": "Critical hunt write blocked in degraded mode"})


def _iso_z(value: datetime) -> str:
    normalized = value.replace(microsecond=0)
    if normalized.tzinfo is None:
        normalized = normalized.replace(tzinfo=timezone.utc)
    else:
        normalized = normalized.astimezone(timezone.utc)
    return normalized.isoformat().replace("+00:00", "Z")


def _token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _anonymous_label(user_id: str) -> str:
    return f"Anonymous-{hashlib.sha1(user_id.encode('utf-8')).hexdigest()[:4]}"


def _is_private(db: Session, user_id: str) -> bool:
    row = db.query(AppUserPrivacySetting).filter(AppUserPrivacySetting.user_id == user_id).first()
    return bool(row and (row.visibility or "").lower() == "private")


def _score_row(db: Session, hunt_id: int, user_id: str) -> EventHuntScore:
    row = db.query(EventHuntScore).filter(EventHuntScore.hunt_id == hunt_id, EventHuntScore.user_id == user_id).first()
    if row:
        return row
    row = EventHuntScore(hunt_id=hunt_id, user_id=user_id, score=0, last_updated_at=now_utc())
    db.add(row)
    db.flush()
    return row


def _build_checkpoint_qr(event_id: int, hunt_id: int, checkpoint_id: int, *, token_id: str, token: str, issued_at: datetime, expires_at: datetime) -> tuple[str, str, str]:
    qr_type = "hunt_checkpoint"
    issued_at_iso = _iso_z(issued_at)
    expires_at_iso = _iso_z(expires_at)
    nonce = secrets.token_urlsafe(12)
    signature = sign_payload(qr_type, event_id, issued_at_iso, expires_at_iso, token_id, nonce)
    params = {
        "type": qr_type,
        "event_id": event_id,
        "hunt_id": hunt_id,
        "checkpoint_id": checkpoint_id,
        "token_id": token_id,
        "token": token,
        "issued_at": issued_at_iso,
        "expires_at": expires_at_iso,
        "nonce": nonce,
        "sig": signature,
    }
    return f"tore://qr?{urlencode(params)}", signature, nonce


def _hunt_for_event(db: Session, event_id: int, hunt_id: int) -> EventHunt:
    hunt = db.get(EventHunt, hunt_id)
    if not hunt or hunt.event_id != event_id:
        raise HTTPException(status_code=404, detail={"reason": "hunt_not_found"})
    return hunt


@router.post("/partner/portal/orga/events/{event_id}/hunts")
def create_event_hunt(
    event_id: int,
    payload: HuntCreateV1In,
    identity=Depends(_require_orga_manager_identity),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    key = _require_idempotency(idempotency_key)
    event = _event_for_identity(db, event_id, identity)
    _hunt_module_guard(db, event_id, write=True)

    existing = db.query(EventHuntIdempotency).filter(
        EventHuntIdempotency.event_id == event_id,
        EventHuntIdempotency.action == "hunt_create",
        EventHuntIdempotency.idempotency_key == key,
    ).first()
    if existing:
        return existing.response_json

    hunt = EventHunt(
        event_id=event_id,
        title=payload.title,
        description=payload.description,
        starts_at=payload.startsAt,
        ends_at=payload.endsAt,
        is_active=True,
        rules_text=payload.rulesText,
        created_by=identity["user_id"],
    )
    db.add(hunt)
    db.flush()

    checkpoints_out = []
    for cp in payload.checkpoints:
        token_raw = secrets.token_urlsafe(24)
        token_id = secrets.token_urlsafe(12)
        checkpoint = EventHuntCheckpoint(
            hunt_id=hunt.id,
            label=cp.label,
            points=cp.points,
            reward_tickets=cp.rewardTickets,
            qr_token_id=token_id,
            qr_token_hash=_token_hash(token_raw),
            order_index=cp.orderIndex,
        )
        db.add(checkpoint)
        db.flush()
        deeplink, signature, nonce = _build_checkpoint_qr(
            event.id,
            hunt.id,
            checkpoint.id,
            token_id=token_id,
            token=token_raw,
            issued_at=now_utc(),
            expires_at=payload.endsAt,
        )
        db.add(
            EventQrToken(
                event_id=event.id,
                qr_type="hunt_checkpoint",
                role="user",
                token_id=token_id,
                nonce=nonce,
                payload=deeplink,
                signature=signature,
                issued_at=now_utc(),
                expires_at=payload.endsAt,
                created_by_user_id=identity["user_id"],
            )
        )
        checkpoints_out.append(
            {
                "checkpointId": checkpoint.id,
                "label": checkpoint.label,
                "points": checkpoint.points,
                "rewardTickets": checkpoint.reward_tickets,
                "deeplink": deeplink,
                "expiresAt": _iso_z(payload.endsAt),
            }
        )

    response = {
        "id": hunt.id,
        "eventId": event_id,
        "title": hunt.title,
        "description": hunt.description,
        "startsAt": _iso_z(hunt.starts_at),
        "endsAt": _iso_z(hunt.ends_at),
        "isActive": hunt.is_active,
        "rulesText": hunt.rules_text,
        "checkpoints": checkpoints_out,
    }
    db.add(EventHuntIdempotency(event_id=event_id, action="hunt_create", idempotency_key=key, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=identity.get("user_id"),
        actor_role=identity.get("role"),
        action="orga.hunt.create",
        entity_type="event_hunt",
        entity_id=str(hunt.id),
        event_id=event_id,
        bar_id=identity.get("bar_id"),
        idempotency_key=key,
        payload={"title": hunt.title, "checkpoints": len(checkpoints_out)},
    )
    db.commit()
    return response


@router.get("/partner/portal/orga/events/{event_id}/hunts")
def list_event_hunts(
    event_id: int,
    identity=Depends(_require_orga_manager_identity),
    db: Session = Depends(get_db),
):
    _event_for_identity(db, event_id, identity)
    _hunt_module_guard(db, event_id, write=False)
    rows = db.query(EventHunt).filter(EventHunt.event_id == event_id).order_by(EventHunt.id.desc()).all()
    return [{
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "startsAt": row.starts_at,
        "endsAt": row.ends_at,
        "isActive": row.is_active,
        "rulesText": row.rules_text,
    } for row in rows]


@router.get("/partner/portal/orga/hunts/{hunt_id}/qr_pack")
def get_hunt_qr_pack(
    hunt_id: int,
    identity=Depends(_require_orga_manager_identity),
    db: Session = Depends(get_db),
):
    hunt = db.get(EventHunt, hunt_id)
    if not hunt:
        raise HTTPException(status_code=404, detail={"reason": "hunt_not_found"})
    _event_for_identity(db, hunt.event_id, identity)
    _hunt_module_guard(db, hunt.event_id, write=False)
    checkpoints = db.query(EventHuntCheckpoint).filter(EventHuntCheckpoint.hunt_id == hunt_id).order_by(EventHuntCheckpoint.order_index.asc(), EventHuntCheckpoint.id.asc()).all()
    tokens = {
        row.token_id: row
        for row in db.query(EventQrToken).filter(EventQrToken.event_id == hunt.event_id, EventQrToken.qr_type == "hunt_checkpoint").all()
    }
    items = []
    for cp in checkpoints:
        token_row = tokens.get(cp.qr_token_id)
        items.append(
            {
                "checkpointId": cp.id,
                "label": cp.label,
                "points": cp.points,
                "rewardTickets": cp.reward_tickets,
                "deeplink": token_row.payload if token_row else None,
                "expiresAt": token_row.expires_at if token_row else hunt.ends_at,
            }
        )
    return {"huntId": hunt.id, "title": hunt.title, "items": items, "printable": {"eventId": hunt.event_id, "huntTitle": hunt.title}}


@router.post("/partner/portal/orga/hunts/{hunt_id}/close", response_model=HuntCloseOut)
def close_hunt(
    hunt_id: int,
    identity=Depends(_require_orga_manager_identity),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    key = _require_idempotency(idempotency_key)
    hunt = db.get(EventHunt, hunt_id)
    if not hunt:
        raise HTTPException(status_code=404, detail={"reason": "hunt_not_found"})
    _event_for_identity(db, hunt.event_id, identity)
    _hunt_module_guard(db, hunt.event_id, write=True)

    existing = db.query(EventHuntIdempotency).filter(
        EventHuntIdempotency.event_id == hunt.event_id,
        EventHuntIdempotency.action == f"hunt_close:{hunt_id}",
        EventHuntIdempotency.idempotency_key == key,
    ).first()
    if existing:
        return existing.response_json

    hunt.is_active = False
    response = {"ok": True, "huntId": hunt.id, "isActive": False}
    db.add(EventHuntIdempotency(event_id=hunt.event_id, action=f"hunt_close:{hunt_id}", idempotency_key=key, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=identity.get("user_id"),
        actor_role=identity.get("role"),
        action="orga.hunt.close",
        entity_type="event_hunt",
        entity_id=str(hunt.id),
        event_id=hunt.event_id,
        bar_id=identity.get("bar_id"),
        idempotency_key=key,
        payload={},
    )
    db.commit()
    return response


@router.get("/events/{event_id}/hunts/active")
def user_active_hunt(
    event_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _hunt_module_guard(db, event_id, write=False)
    now = now_utc()
    hunt = db.query(EventHunt).filter(
        EventHunt.event_id == event_id,
        EventHunt.is_active.is_(True),
        EventHunt.starts_at <= now,
        EventHunt.ends_at >= now,
    ).order_by(EventHunt.id.desc()).first()
    if not hunt:
        raise HTTPException(status_code=404, detail={"reason": "hunt_not_found"})
    score = db.query(EventHuntScore).filter(EventHuntScore.hunt_id == hunt.id, EventHuntScore.user_id == user.id).first()
    count = db.query(func.count(EventHuntCheckpoint.id)).filter(EventHuntCheckpoint.hunt_id == hunt.id).scalar() or 0
    return {
        "id": hunt.id,
        "title": hunt.title,
        "description": hunt.description,
        "endsAt": hunt.ends_at,
        "checkpointsCount": int(count),
        "myScore": int(score.score if score else 0),
    }


@router.post("/events/{event_id}/hunts/{hunt_id}/claim")
def claim_hunt_checkpoint(
    event_id: int,
    hunt_id: int,
    payload: HuntClaimIn,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    key = _require_idempotency(idempotency_key)
    _hunt_module_guard(db, event_id, write=True, critical=True)
    hunt = _hunt_for_event(db, event_id, hunt_id)

    existing = db.query(EventHuntIdempotency).filter(
        EventHuntIdempotency.event_id == event_id,
        EventHuntIdempotency.action == f"claim:{hunt_id}:{user.id}",
        EventHuntIdempotency.idempotency_key == key,
    ).first()
    if existing:
        return existing.response_json

    checkpoint = db.get(EventHuntCheckpoint, payload.checkpointId)
    if not checkpoint or checkpoint.hunt_id != hunt.id:
        raise HTTPException(status_code=404, detail={"reason": "checkpoint_not_found"})

    token_row = db.query(EventQrToken).filter(EventQrToken.token_id == checkpoint.qr_token_id).first()
    if not token_row or token_row.event_id != event_id or token_row.revoked_at is not None:
        raise HTTPException(status_code=400, detail={"reason": "invalid_token"})
    if token_row.expires_at <= now_utc():
        raise HTTPException(status_code=400, detail={"reason": "expired_token"})
    if checkpoint.qr_token_hash != _token_hash(payload.token):
        raise HTTPException(status_code=400, detail={"reason": "invalid_token"})

    claim = EventHuntClaim(
        hunt_id=hunt.id,
        checkpoint_id=checkpoint.id,
        user_id=user.id,
        claimed_at=now_utc(),
        points_awarded=checkpoint.points,
    )
    db.add(claim)
    already_claimed = False
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        already_claimed = True

    score_row = _score_row(db, hunt.id, user.id)
    points_awarded = 0 if already_claimed else checkpoint.points
    reward_tickets_awarded = 0
    if not already_claimed:
        score_row.score += checkpoint.points
        score_row.last_updated_at = now_utc()
        if checkpoint.reward_tickets and checkpoint.reward_tickets > 0:
            _, _, created = apply_wallet_tx(
                db,
                user_id=user.id,
                amount_tickets=checkpoint.reward_tickets,
                kind="HUNT_CHECKPOINT_REWARD",
                ref_type="HUNT_CHECKPOINT",
                ref_id=str(checkpoint.id),
                idempotency_key=f"hunt-checkpoint-reward:{checkpoint.id}:{user.id}",
            )
            if created:
                reward_tickets_awarded = checkpoint.reward_tickets

    response = {
        "ok": True,
        "alreadyClaimed": already_claimed,
        "pointsAwarded": points_awarded,
        "totalScore": int(score_row.score),
        "rewardTicketsAwarded": reward_tickets_awarded,
    }
    db.add(EventHuntIdempotency(event_id=event_id, action=f"claim:{hunt_id}:{user.id}", idempotency_key=key, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="user",
        action="hunt.claim",
        entity_type="event_hunt_checkpoint",
        entity_id=str(checkpoint.id),
        event_id=event_id,
        bar_id=None,
        idempotency_key=key,
        payload={"hunt_id": hunt_id, "already_claimed": already_claimed, "points": points_awarded},
    )
    db.commit()
    return response


@router.get("/events/{event_id}/hunts/{hunt_id}/leaderboard")
def hunt_leaderboard(
    event_id: int,
    hunt_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _hunt_module_guard(db, event_id, write=False)
    _hunt_for_event(db, event_id, hunt_id)

    rows = db.query(EventHuntScore).filter(EventHuntScore.hunt_id == hunt_id).order_by(EventHuntScore.score.desc(), EventHuntScore.last_updated_at.asc()).all()
    me_row = next((r for r in rows if r.user_id == user.id), None)
    top3, dense = [], []
    for idx, row in enumerate(rows, start=1):
        private = _is_private(db, row.user_id)
        label = row.user_id if (row.user_id == user.id or not private) else _anonymous_label(row.user_id)
        item = {"rank": idx, "userId": row.user_id, "name": label, "score": int(row.score), "private": private and row.user_id != user.id}
        dense.append(item)
        if idx <= 3:
            top3.append(item)

    me_payload = {
        "rank": next((idx for idx, r in enumerate(rows, start=1) if r.user_id == user.id), None),
        "userId": user.id,
        "name": user.display_name or user.id,
        "score": int(me_row.score if me_row else 0),
    }
    return {"top3": top3, "list": dense, "me": me_payload}


@router.post("/events/{event_id}/hunts/{hunt_id}/steal")
def hunt_steal(
    event_id: int,
    hunt_id: int,
    payload: HuntStealIn,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    key = _require_idempotency(idempotency_key)
    _hunt_module_guard(db, event_id, write=True, critical=True)
    _hunt_for_event(db, event_id, hunt_id)

    existing = db.query(EventHuntIdempotency).filter(
        EventHuntIdempotency.event_id == event_id,
        EventHuntIdempotency.action == f"steal:{hunt_id}:{user.id}",
        EventHuntIdempotency.idempotency_key == key,
    ).first()
    if existing:
        return existing.response_json

    now = now_utc()
    cooldown_at = now - timedelta(minutes=10)
    recent = db.query(EventHuntSteal).filter(
        EventHuntSteal.hunt_id == hunt_id,
        EventHuntSteal.attacker_user_id == user.id,
        EventHuntSteal.created_at >= cooldown_at,
    ).order_by(EventHuntSteal.created_at.desc()).first()

    if recent:
        response = {"ok": False, "result": "COOLDOWN", "amount": 0}
    elif payload.victimUserId == user.id:
        response = {"ok": False, "result": "BLOCKED", "amount": 0}
    elif _is_private(db, payload.victimUserId):
        response = {"ok": False, "result": "VICTIM_PRIVATE", "amount": 0}
    else:
        attacker = _score_row(db, hunt_id, user.id)
        victim = _score_row(db, hunt_id, payload.victimUserId)
        steal_amount = max(1, min(50, int(victim.score * 0.1))) if victim.score > 0 else 0
        if steal_amount <= 0:
            response = {"ok": False, "result": "BLOCKED", "amount": 0, "attackerScore": attacker.score, "victimScoreMasked": victim.score}
        else:
            victim.score = max(0, victim.score - steal_amount)
            attacker.score += steal_amount
            victim.last_updated_at = now
            attacker.last_updated_at = now
            response = {
                "ok": True,
                "result": "OK",
                "amount": steal_amount,
                "attackerScore": attacker.score,
                "victimScoreMasked": "hidden" if _is_private(db, payload.victimUserId) else victim.score,
            }

    db.add(EventHuntSteal(
        hunt_id=hunt_id,
        attacker_user_id=user.id,
        victim_user_id=payload.victimUserId,
        amount=int(response.get("amount") or 0),
        result=str(response.get("result") or "BLOCKED"),
        audit={"idempotency_key": key},
        created_at=now,
    ))
    db.add(EventHuntIdempotency(event_id=event_id, action=f"steal:{hunt_id}:{user.id}", idempotency_key=key, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_user_id=user.id,
        actor_role="user",
        action="hunt.steal",
        entity_type="event_hunt",
        entity_id=str(hunt_id),
        event_id=event_id,
        bar_id=None,
        idempotency_key=key,
        payload={"victim": payload.victimUserId, "result": response.get("result"), "amount": response.get("amount", 0)},
    )
    db.commit()
    return response


# Legacy Hunt V0 routes kept for backward compatibility.
@router.post("/partner/portal/hunt", response_model=HuntOut)
def create_hunt(
    payload: HuntCreateIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_manager(identity)
    event = get_event_for_bar(db, payload.event_id, identity["bar_id"])
    hunt = Hunt(
        bar_id=identity["bar_id"],
        event_id=event.id,
        name=payload.name,
        reward_tickets=payload.reward_tickets,
        is_active=True,
    )
    db.add(hunt)
    db.commit()
    db.refresh(hunt)
    return hunt


@router.patch("/partner/portal/hunt/{hunt_id}", response_model=HuntOut)
def patch_hunt(
    hunt_id: int,
    payload: HuntPatchIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_manager(identity)
    hunt = get_hunt_for_bar(db, hunt_id, identity["bar_id"])
    if payload.name is not None:
        hunt.name = payload.name
    if payload.is_active is not None:
        hunt.is_active = payload.is_active
    if payload.reward_tickets is not None:
        hunt.reward_tickets = payload.reward_tickets
    db.add(hunt)
    db.commit()
    db.refresh(hunt)
    return hunt


@router.post("/partner/portal/hunt/{hunt_id}/points", response_model=HuntPointOut)
def create_hunt_point(
    hunt_id: int,
    payload: HuntPointCreateIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_manager(identity)
    hunt = get_hunt_for_bar(db, hunt_id, identity["bar_id"])
    code = generate_secret_code(db)
    point = HuntPoint(
        hunt_id=hunt.id,
        name=payload.name,
        hint=payload.hint,
        sort_order=payload.sort_order,
        is_active=True,
        secret_code=code,
    )
    db.add(point)
    db.commit()
    db.refresh(point)
    return HuntPointOut(
        id=point.id,
        hunt_id=point.hunt_id,
        name=point.name,
        hint=point.hint,
        sort_order=point.sort_order,
        is_active=point.is_active,
        secret_code=point.secret_code,
        qr_payload=qr_payload(hunt.event_id, point.secret_code),
        route_front=route_front(hunt.event_id, point.secret_code),
    )


@router.patch("/partner/portal/hunt/points/{point_id}", response_model=HuntPointOut)
def patch_hunt_point(
    point_id: int,
    payload: HuntPointPatchIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_manager(identity)
    point = db.get(HuntPoint, point_id)
    if not point:
        raise HTTPException(404, "Point not found")
    hunt = get_hunt_for_bar(db, point.hunt_id, identity["bar_id"])
    if payload.name is not None:
        point.name = payload.name
    if payload.hint is not None:
        point.hint = payload.hint
    if payload.sort_order is not None:
        point.sort_order = payload.sort_order
    if payload.is_active is not None:
        point.is_active = payload.is_active
    db.add(point)
    db.commit()
    db.refresh(point)
    return HuntPointOut(
        id=point.id,
        hunt_id=point.hunt_id,
        name=point.name,
        hint=point.hint,
        sort_order=point.sort_order,
        is_active=point.is_active,
        secret_code=point.secret_code,
        qr_payload=qr_payload(hunt.event_id, point.secret_code),
        route_front=route_front(hunt.event_id, point.secret_code),
    )


@router.delete("/partner/portal/hunt/points/{point_id}")
def delete_hunt_point(
    point_id: int,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_manager(identity)
    point = db.get(HuntPoint, point_id)
    if not point:
        raise HTTPException(404, "Point not found")
    get_hunt_for_bar(db, point.hunt_id, identity["bar_id"])
    db.delete(point)
    db.commit()
    return {"ok": True}


@router.get("/partner/portal/hunt/{hunt_id}/points", response_model=list[HuntPointOut])
def list_hunt_points(
    hunt_id: int,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_manager(identity)
    get_hunt_for_bar(db, hunt_id, identity["bar_id"])
    points = (
        db.query(HuntPoint)
        .filter(HuntPoint.hunt_id == hunt_id)
        .order_by(HuntPoint.sort_order.asc(), HuntPoint.id.asc())
        .all()
    )
    hunt = db.get(Hunt, hunt_id)
    return [
        HuntPointOut(
            id=p.id,
            hunt_id=p.hunt_id,
            name=p.name,
            hint=p.hint,
            sort_order=p.sort_order,
            is_active=p.is_active,
            secret_code=p.secret_code,
            qr_payload=qr_payload(hunt.event_id, p.secret_code),
            route_front=route_front(hunt.event_id, p.secret_code),
        )
        for p in points
    ]


@router.get("/partner/portal/hunt/{hunt_id}/stats", response_model=HuntStatsOut)
def get_hunt_stats(
    hunt_id: int,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_manager(identity)
    get_hunt_for_bar(db, hunt_id, identity["bar_id"])
    return hunt_stats(db, hunt_id)


@router.get("/hunt/event/{event_id}", response_model=HuntEventOut)
def public_hunt_event(
    event_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hunt = (
        db.query(Hunt)
        .filter(Hunt.event_id == event_id, Hunt.is_active.is_(True))
        .order_by(Hunt.id.desc())
        .first()
    )
    if not hunt:
        raise HTTPException(404, "Active hunt not found")
    progress = build_progress(db, hunt, user.id)
    points = [
        HuntPointPublicOut(
            id=p.id,
            name=p.name,
            hint=p.hint,
            sort_order=p.sort_order,
            is_active=p.is_active,
            scanned=p.id in progress["scanned_ids"],
        )
        for p in progress["points"]
    ]
    return HuntEventOut(
        hunt=HuntOut(
            id=hunt.id,
            bar_id=hunt.bar_id,
            event_id=hunt.event_id,
            name=hunt.name,
            is_active=hunt.is_active,
            reward_tickets=hunt.reward_tickets,
            created_at=hunt.created_at,
        ),
        points=points,
        completion=progress["completion"],
        completed=progress["completed"],
        reward_granted=progress["reward_granted"],
    )


@router.post("/hunt/scan", response_model=HuntScanOut)
def public_hunt_scan(
    payload: HuntScanIn,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return scan_point(
        db,
        event_id=payload.event_id,
        code=payload.code,
        user_id=user.id,
        device_id=payload.device_id,
    )


@router.get("/hunt/me/event/{event_id}", response_model=HuntEventOut)
def public_hunt_me(
    event_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return public_hunt_event(event_id=event_id, user=user, db=db)
