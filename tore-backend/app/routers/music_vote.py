from __future__ import annotations

import hashlib
import re
from datetime import timedelta
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from db import get_db, now_utc
from main import JWT_ALG, JWT_SECRET, get_current_user
from models import (
    AppToken,
    AppUser,
    Event,
    EventMusicActionIdempotency,
    EventMusicAdminIdempotency,
    EventMusicCandidate,
    EventMusicSetting,
    EventMusicVote,
    EventStaff,
)
from partner_auth import current_identity
from app.services.audit_service import write_audit_log
from app.services.p3_common import get_event_runtime_state

router = APIRouter(prefix="/events", tags=["music-vote"])

_PROVIDER_SET = {"spotify", "apple", "ytmusic", "soundcloud"}


class TrackCandidateIn(BaseModel):
    provider: str
    externalUrl: str = Field(min_length=4)
    title: str = Field(min_length=1, max_length=180)
    artist: str = Field(min_length=1, max_length=180)
    artworkUrl: Optional[str] = None
    durationSec: Optional[int] = None
    providerUri: Optional[str] = None
    searchHint: Optional[str] = None


class VoteIn(BaseModel):
    candidate: TrackCandidateIn


class MusicSettingsIn(BaseModel):
    enabled: Optional[bool] = None
    djOverrideEnabled: Optional[bool] = None
    allowMixedProviders: Optional[bool] = None
    providerDefault: Optional[str] = None
    reason: Optional[str] = None


class ForceIn(BaseModel):
    candidate: TrackCandidateIn
    reason: Optional[str] = None


class ClearIn(BaseModel):
    reason: Optional[str] = None


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _module_on(event: Event) -> bool:
    m = event.modules_on or {}
    return bool(m.get("music_vote") or m.get("music") or m.get("vote"))


def _normalize_url(url: str) -> str:
    return re.sub(r"\s+", "", (url or "").strip()).rstrip("/").lower()


def _candidate_key(candidate: TrackCandidateIn) -> str:
    provider = (candidate.provider or "").strip().lower()
    return f"{provider}:{_normalize_url(candidate.externalUrl)}"


def _runtime_write_guard(db: Session, event_id: int) -> None:
    state = (get_event_runtime_state(db, event_id) or "LIVE").upper()
    if state != "LIVE":
        raise HTTPException(status_code=403, detail={"reason": "runtime_blocked", "state": state})


def _get_or_create_settings(db: Session, event_id: int) -> EventMusicSetting:
    row = db.query(EventMusicSetting).filter(EventMusicSetting.event_id == event_id).first()
    if row:
        return row
    row = EventMusicSetting(event_id=event_id)
    db.add(row)
    db.flush()
    return row


def _winner_payload(settings: EventMusicSetting) -> Optional[dict]:
    if not settings.winner_candidate_key:
        return None
    return {
        "candidateKey": settings.winner_candidate_key,
        "candidate": settings.winner_candidate_json,
        "decidedAt": settings.winner_decided_at.isoformat() if settings.winner_decided_at else None,
    }


def _top_candidates(db: Session, event_id: int, limit: int = 8) -> list[dict]:
    rows = (
        db.query(
            EventMusicVote.candidate_key,
            EventMusicVote.provider,
            EventMusicVote.external_url,
            EventMusicVote.title,
            EventMusicVote.artist,
            EventMusicVote.artwork_url,
            func.count(EventMusicVote.id).label("votes"),
        )
        .filter(EventMusicVote.event_id == event_id)
        .group_by(
            EventMusicVote.candidate_key,
            EventMusicVote.provider,
            EventMusicVote.external_url,
            EventMusicVote.title,
            EventMusicVote.artist,
            EventMusicVote.artwork_url,
        )
        .order_by(func.count(EventMusicVote.id).desc(), EventMusicVote.candidate_key.asc())
        .limit(limit)
        .all()
    )
    out = []
    for row in rows:
        out.append({
            "candidateKey": row.candidate_key,
            "candidate": {
                "provider": row.provider,
                "externalUrl": row.external_url,
                "title": row.title,
                "artist": row.artist,
                "artworkUrl": row.artwork_url,
            },
            "votes": int(row.votes or 0),
        })
    return out


def _optional_partner_identity(authorization: Optional[str], db: Session) -> Optional[dict]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        return None
    if "bar_id" not in payload:
        return None
    try:
        return current_identity(authorization=authorization, db=db)
    except HTTPException:
        return None


def _optional_app_user(authorization: Optional[str], db: Session) -> Optional[AppUser]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    raw = authorization.split(" ", 1)[1].strip().strip('"').strip("'").strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()
    tok = db.query(AppToken).filter(AppToken.token_hash == _hash_token(raw), AppToken.revoked_at.is_(None)).first()
    if not tok:
        return None
    return db.get(AppUser, tok.user_id)


def _ensure_module_or_404(db: Session, event_id: int) -> Event:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail={"reason": "event_not_found"})
    if not _module_on(event):
        raise HTTPException(status_code=404, detail={"reason": "MODULE_OFF", "message": "Music vote module off"})
    return event


@router.get("/{event_id}/music")
def music_get(event_id: int, db: Session = Depends(get_db)):
    _ensure_module_or_404(db, event_id)
    settings = _get_or_create_settings(db, event_id)
    payload = {
        "enabled": bool(settings.enabled),
        "djOverrideEnabled": bool(settings.dj_override_enabled),
        "allowMixedProviders": bool(settings.allow_mixed),
        "providerDefault": settings.provider_default,
        "winner": _winner_payload(settings),
        "topCandidates": _top_candidates(db, event_id),
        "lastUpdatedAt": settings.updated_at,
    }
    db.commit()
    return payload


@router.post("/{event_id}/music/vote")
def music_vote(
    event_id: int,
    body: VoteIn,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"reason": "idempotency_required"})
    _ensure_module_or_404(db, event_id)
    settings = _get_or_create_settings(db, event_id)
    if not settings.enabled:
        raise HTTPException(status_code=403, detail={"reason": "music_disabled"})
    _runtime_write_guard(db, event_id)

    existing = (
        db.query(EventMusicActionIdempotency)
        .filter(
            EventMusicActionIdempotency.event_id == event_id,
            EventMusicActionIdempotency.action_type == "vote",
            EventMusicActionIdempotency.idempotency_key == idempotency_key,
            EventMusicActionIdempotency.actor_user_id == user.id,
        )
        .first()
    )
    if existing:
        return existing.response_json

    recent = (
        db.query(EventMusicVote)
        .filter(EventMusicVote.event_id == event_id, EventMusicVote.user_id == user.id)
        .order_by(EventMusicVote.created_at.desc())
        .first()
    )
    if recent and recent.created_at and recent.created_at >= now_utc() - timedelta(seconds=10):
        raise HTTPException(status_code=429, detail={"reason": "vote_cooldown", "cooldownSec": 10})

    provider = body.candidate.provider.strip().lower()
    if provider not in _PROVIDER_SET:
        raise HTTPException(status_code=400, detail={"reason": "provider_invalid"})
    key = _candidate_key(body.candidate)
    vote = EventMusicVote(
        event_id=event_id,
        user_id=user.id,
        candidate_key=key,
        provider=provider,
        external_url=body.candidate.externalUrl,
        title=body.candidate.title,
        artist=body.candidate.artist,
        artwork_url=body.candidate.artworkUrl,
    )
    db.add(vote)
    db.add(
        EventMusicCandidate(
            event_id=event_id,
            candidate_key=key,
            provider=provider,
            external_url=body.candidate.externalUrl,
            title=body.candidate.title,
            artist=body.candidate.artist,
            artwork_url=body.candidate.artworkUrl,
        )
    )
    settings.last_updated_at = now_utc()
    settings.updated_at = now_utc()
    db.add(settings)
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_role="app_user",
        action="music_vote.vote",
        entity_type="event_music",
        entity_id=str(event_id),
        event_id=event_id,
        bar_id=None,
        payload={"candidate_key": key, "provider": provider},
    )
    response = {"ok": True, "topCandidates": _top_candidates(db, event_id), "winner": _winner_payload(settings)}
    db.add(
        EventMusicActionIdempotency(
            event_id=event_id,
            action_type="vote",
            idempotency_key=idempotency_key,
            actor_user_id=user.id,
            response_json=response,
        )
    )
    db.commit()
    return response


@router.post("/{event_id}/music/admin/settings")
def music_settings(
    event_id: int,
    body: MusicSettingsIn,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    identity=Depends(current_identity),
    db: Session = Depends(get_db),
):
    if identity.get("role") not in {"manager", "owner"}:
        raise HTTPException(status_code=403, detail={"reason": "forbidden"})
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"reason": "idempotency_required"})
    event = _ensure_module_or_404(db, event_id)
    if event.bar_id != identity.get("bar_id"):
        raise HTTPException(status_code=403, detail={"reason": "wrong_bar"})
    _runtime_write_guard(db, event_id)

    existing = (
        db.query(EventMusicAdminIdempotency)
        .filter(
            EventMusicAdminIdempotency.event_id == event_id,
            EventMusicAdminIdempotency.action_type == "settings",
            EventMusicAdminIdempotency.idempotency_key == idempotency_key,
            EventMusicAdminIdempotency.actor_partner_id == identity["user_id"],
        )
        .first()
    )
    if existing:
        return existing.response_json

    settings = _get_or_create_settings(db, event_id)
    before = {
        "enabled": settings.enabled,
        "djOverrideEnabled": settings.dj_override_enabled,
        "allowMixedProviders": settings.allow_mixed,
        "providerDefault": settings.provider_default,
    }
    if body.enabled is not None:
        settings.enabled = body.enabled
    if body.djOverrideEnabled is not None:
        settings.dj_override_enabled = body.djOverrideEnabled
    if body.allowMixedProviders is not None:
        settings.allow_mixed = body.allowMixedProviders
    if body.providerDefault is not None:
        provider = body.providerDefault.strip().lower()
        if provider not in _PROVIDER_SET:
            raise HTTPException(status_code=400, detail={"reason": "provider_invalid"})
        settings.provider_default = provider
    settings.updated_at = now_utc()
    settings.last_updated_at = now_utc()
    settings.updated_by = str(identity["user_id"])
    db.add(settings)
    response = {"ok": True, "settings": {
        "enabled": settings.enabled,
        "djOverrideEnabled": settings.dj_override_enabled,
        "allowMixedProviders": settings.allow_mixed,
        "providerDefault": settings.provider_default,
    }}
    db.add(EventMusicAdminIdempotency(event_id=event_id, action_type="settings", idempotency_key=idempotency_key, actor_partner_id=identity["user_id"], response_json=response))
    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity.get("role"),
        action="music_vote.settings",
        entity_type="event_music",
        entity_id=str(event_id),
        event_id=event_id,
        bar_id=identity.get("bar_id"),
        payload={"before": before, "after": response["settings"], "reason": body.reason},
    )
    db.commit()
    return response


def _admin_or_dj_guard(db: Session, event: Event, settings: EventMusicSetting, authorization: Optional[str]) -> tuple[str, Optional[int], Optional[str]]:
    partner = _optional_partner_identity(authorization, db)
    if partner and event.bar_id == partner.get("bar_id") and partner.get("role") in {"manager", "owner"}:
        return "partner", int(partner["user_id"]), partner.get("role")
    app_user = _optional_app_user(authorization, db)
    if app_user and settings.dj_override_enabled:
        staff = (
            db.query(EventStaff)
            .filter(EventStaff.event_id == event.id, EventStaff.user_id == app_user.id, EventStaff.is_active.is_(True))
            .first()
        )
        if staff and (staff.role or "").lower() == "dj":
            return "dj", None, "dj"
    raise HTTPException(status_code=403, detail={"reason": "forbidden"})


@router.post("/{event_id}/music/admin/force")
def music_force(
    event_id: int,
    body: ForceIn,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"reason": "idempotency_required"})
    event = _ensure_module_or_404(db, event_id)
    settings = _get_or_create_settings(db, event_id)
    _runtime_write_guard(db, event_id)
    mode, actor_partner_id, actor_role = _admin_or_dj_guard(db, event, settings, authorization)

    existing = db.query(EventMusicAdminIdempotency).filter(
        EventMusicAdminIdempotency.event_id == event_id,
        EventMusicAdminIdempotency.action_type == "force",
        EventMusicAdminIdempotency.idempotency_key == idempotency_key,
    ).first()
    if existing:
        return existing.response_json

    provider = body.candidate.provider.strip().lower()
    if provider not in _PROVIDER_SET:
        raise HTTPException(status_code=400, detail={"reason": "provider_invalid"})
    key = _candidate_key(body.candidate)
    candidate_json = body.candidate.model_dump()
    settings.winner_candidate_key = key
    settings.winner_candidate_json = candidate_json
    settings.winner_decided_at = now_utc()
    settings.last_updated_at = now_utc()
    settings.updated_at = now_utc()
    db.add(settings)
    response = {"ok": True, "winner": _winner_payload(settings)}
    db.add(EventMusicAdminIdempotency(event_id=event_id, action_type="force", idempotency_key=idempotency_key, actor_partner_id=actor_partner_id, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=actor_partner_id,
        actor_role=actor_role,
        action="music_vote.force",
        entity_type="event_music",
        entity_id=str(event_id),
        event_id=event_id,
        bar_id=event.bar_id,
        payload={"candidate_key": key, "candidate": candidate_json, "reason": body.reason, "actor_mode": mode},
    )
    db.commit()
    return response


@router.post("/{event_id}/music/admin/clear")
def music_clear(
    event_id: int,
    body: ClearIn,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"reason": "idempotency_required"})
    event = _ensure_module_or_404(db, event_id)
    settings = _get_or_create_settings(db, event_id)
    _runtime_write_guard(db, event_id)
    mode, actor_partner_id, actor_role = _admin_or_dj_guard(db, event, settings, authorization)

    existing = db.query(EventMusicAdminIdempotency).filter(
        EventMusicAdminIdempotency.event_id == event_id,
        EventMusicAdminIdempotency.action_type == "clear",
        EventMusicAdminIdempotency.idempotency_key == idempotency_key,
    ).first()
    if existing:
        return existing.response_json

    db.query(EventMusicVote).filter(EventMusicVote.event_id == event_id).delete(synchronize_session=False)
    settings.winner_candidate_key = None
    settings.winner_candidate_json = None
    settings.winner_decided_at = None
    settings.last_updated_at = now_utc()
    settings.updated_at = now_utc()
    db.add(settings)
    response = {"ok": True}
    db.add(EventMusicAdminIdempotency(event_id=event_id, action_type="clear", idempotency_key=idempotency_key, actor_partner_id=actor_partner_id, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=actor_partner_id,
        actor_role=actor_role,
        action="music_vote.clear",
        entity_type="event_music",
        entity_id=str(event_id),
        event_id=event_id,
        bar_id=event.bar_id,
        payload={"reason": body.reason, "actor_mode": mode},
    )
    db.commit()
    return response
