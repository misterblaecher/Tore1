from __future__ import annotations

import hashlib
import re
from datetime import timedelta
from typing import Optional
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.services.audit_service import write_audit_log
from app.services.p3_common import get_event_runtime_state
from db import get_db, now_utc
from app.core.settings import JWT_ALG, JWT_SECRET
from app.core.security.user_auth import get_current_user
from models import (
    AppToken,
    AppUser,
    Event,
    EventMusicActionIdempotency,
    EventMusicAdminIdempotency,
    EventMusicCandidate,
    EventMusicSetting,
    EventMusicSuggestion,
    EventMusicSuggestionVote,
    EventMusicRound,
    EventMusicVote,
    EventStaff,
)
from partner_auth import current_identity

router = APIRouter(prefix="/events", tags=["music-vote"])

_PROVIDER_SET = {"spotify", "apple", "youtube_music", "ytmusic", "soundcloud"}
_ALLOWED_ROUND_DURATIONS = {60, 120, 180, 300}
_PRE_EVENT_COOLDOWN_SECONDS = 20



class TrackCandidateIn(BaseModel):
    provider: str
    externalUrl: str = Field(min_length=4)
    title: str = Field(default="", max_length=180)
    artist: str = Field(default="", max_length=180)
    artworkUrl: Optional[str] = None
    durationSec: Optional[int] = None
    providerUri: Optional[str] = None
    searchHint: Optional[str] = None
    titleHint: Optional[str] = Field(default=None, max_length=180)


class VoteIn(BaseModel):
    candidate: TrackCandidateIn


class PreEventSuggestIn(BaseModel):
    provider: str
    externalUrl: str = Field(min_length=8, max_length=512)
    title: str = Field(default="", max_length=180)
    artist: str = Field(default="", max_length=180)


class PreEventVoteIn(BaseModel):
    suggestionId: int


class CandidateAddIn(BaseModel):
    provider: str
    externalUrl: str = Field(min_length=8, max_length=512)
    titleHint: Optional[str] = Field(default=None, max_length=180)


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


class RoundStartIn(BaseModel):
    durationSec: int


class NowPlayingIn(BaseModel):
    candidate: TrackCandidateIn
    reason: Optional[str] = None


class SkipIn(BaseModel):
    reason: str = Field(min_length=1, max_length=180)
    reopen: bool = False


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _module_on(event: Event) -> bool:
    m = event.modules_on or {}
    return bool(m.get("music_vote") or m.get("music") or m.get("vote"))


def _canonical_provider(value: str) -> str:
    provider = (value or "").strip().lower()
    if provider in {"youtube_music", "ytmusic"}:
        return "youtube_music"
    return provider


def _normalize_url(url: str) -> str:
    parsed = urlparse(re.sub(r"\s+", "", (url or "").strip()))
    host = (parsed.hostname or "").lower()
    path = re.sub(r"/{2,}", "/", (parsed.path or "/")).rstrip("/") or "/"
    return f"https://{host}{path}" + (f"?{parsed.query}" if parsed.query else "")


def _candidate_key(candidate: TrackCandidateIn) -> str:
    provider = _canonical_provider(candidate.provider)
    return f"{provider}:{_normalize_url(candidate.externalUrl)}"


def _reject_invalid_url(url: str) -> None:
    if len(url) > 512:
        raise HTTPException(status_code=400, detail={"reason": "link_invalid"})
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https":
        raise HTTPException(status_code=400, detail={"reason": "link_https_required"})
    host = (parsed.hostname or "").lower()
    if not host or host in {"localhost", "127.0.0.1", "::1"}:
        raise HTTPException(status_code=400, detail={"reason": "link_invalid_host"})
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host):
        raise HTTPException(status_code=400, detail={"reason": "link_invalid_host"})


def _normalize_candidate_link(provider_raw: str, external_url: str) -> tuple[str, str, Optional[str]]:
    provider = _canonical_provider(provider_raw)
    if provider not in _PROVIDER_SET:
        raise HTTPException(status_code=400, detail={"reason": "provider_invalid"})
    _reject_invalid_url(external_url)
    parsed = urlparse(external_url.strip())
    host = (parsed.hostname or "").lower()
    query = parse_qs(parsed.query)
    path = (parsed.path or "").strip("/")
    norm = _normalize_url(external_url)

    if provider == "soundcloud":
        if host != "soundcloud.com" or path.count("/") < 1:
            raise HTTPException(status_code=400, detail={"reason": "LINK_NOT_SUPPORTED"})
        parts = path.split("/")
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail={"reason": "LINK_NOT_SUPPORTED"})
        return provider, norm, f"{parts[0]}/{parts[1]}"

    if provider == "youtube_music":
        external_id = None
        if host == "music.youtube.com":
            if path in {"watch", "playlist"}:
                external_id = (query.get("v") or query.get("list") or [None])[0]
        elif host in {"youtu.be", "www.youtu.be"}:
            external_id = path.split("/")[0] if path else None
        elif host in {"youtube.com", "www.youtube.com"}:
            if path == "watch":
                external_id = (query.get("v") or [None])[0]
            elif path == "playlist":
                external_id = (query.get("list") or [None])[0]
        if not external_id:
            raise HTTPException(status_code=400, detail={"reason": "LINK_NOT_SUPPORTED"})
        return provider, norm, external_id

    return provider, norm, None


def _candidate_out(candidate: EventMusicCandidate) -> dict:
    return {
        "provider": candidate.provider,
        "urlOriginal": candidate.url_original or candidate.external_url,
        "urlNormalized": candidate.url_normalized or candidate.external_url,
        "externalId": candidate.external_id,
        "titleHint": candidate.title_hint,
        "externalUrl": candidate.external_url,
        "title": candidate.title,
        "artist": candidate.artist,
    }


def _list_candidates(db: Session, event_id: int, round_id: Optional[str]) -> list[dict]:
    rows = (
        db.query(EventMusicCandidate)
        .filter(EventMusicCandidate.event_id == event_id, EventMusicCandidate.round_id == round_id)
        .order_by(EventMusicCandidate.created_at.desc())
        .limit(50)
        .all()
    )
    return [_candidate_out(row) for row in rows]


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
        "lockedAt": settings.winner_decided_at.isoformat() if settings.winner_decided_at else None,
        "votesCount": int(settings.winner_votes_count or 0),
    }


def _round_payload(settings: EventMusicSetting) -> dict:
    return {
        "roundId": settings.round_id,
        "status": (settings.round_status or "IDLE").upper(),
        "startedAt": settings.round_started_at.isoformat() if settings.round_started_at else None,
        "endsAt": settings.round_ends_at.isoformat() if settings.round_ends_at else None,
        "durationSec": settings.round_duration_sec,
        "lockedAt": settings.round_locked_at.isoformat() if settings.round_locked_at else None,
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
    return [
        {
            "candidateKey": row.candidate_key,
            "candidate": {
                "provider": row.provider,
                "externalUrl": row.external_url,
                "title": row.title,
                "artist": row.artist,
                "artworkUrl": row.artwork_url,
            },
            "votes": int(row.votes or 0),
        }
        for row in rows
    ]


def _winning_row(db: Session, event_id: int):
    return (
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
        .first()
    )




def _current_round_row(db: Session, event_id: int) -> Optional[EventMusicRound]:
    return (
        db.query(EventMusicRound)
        .filter(EventMusicRound.event_id == event_id)
        .order_by(EventMusicRound.created_at.desc(), EventMusicRound.id.desc())
        .first()
    )


def _current_round_payload(db: Session, event_id: int) -> dict:
    row = _current_round_row(db, event_id)
    if not row:
        return {"round": None}
    winner = None
    if row.winner_candidate_id:
        candidate = db.get(EventMusicCandidate, row.winner_candidate_id)
        if candidate:
            winner = _candidate_out(candidate)
    return {
        "round": {
            "id": row.id,
            "eventId": row.event_id,
            "status": (row.status or "CLOSED").upper(),
            "durationSec": row.duration_sec,
            "startedAt": row.started_at.isoformat() if row.started_at else None,
            "endsAt": row.ends_at.isoformat() if row.ends_at else None,
            "closedAt": row.closed_at.isoformat() if row.closed_at else None,
            "winnerCandidateId": row.winner_candidate_id,
            "winnerCandidate": winner,
            "createdBy": row.created_by,
        }
    }


def _pre_event_top(db: Session, event_id: int, limit: int = 20) -> list[dict]:
    rows = (
        db.query(
            EventMusicSuggestion,
            func.count(EventMusicSuggestionVote.id).label("votes"),
        )
        .outerjoin(EventMusicSuggestionVote, EventMusicSuggestionVote.suggestion_id == EventMusicSuggestion.id)
        .filter(EventMusicSuggestion.event_id == event_id)
        .group_by(EventMusicSuggestion.id)
        .order_by(func.count(EventMusicSuggestionVote.id).desc(), EventMusicSuggestion.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": suggestion.id,
            "provider": suggestion.provider,
            "externalUrl": suggestion.external_url,
            "title": suggestion.title,
            "artist": suggestion.artist,
            "votes": int(votes or 0),
            "createdAt": suggestion.created_at.isoformat() if suggestion.created_at else None,
        }
        for suggestion, votes in rows
    ]

def _lock_round_with_winner(db: Session, event_id: int, settings: EventMusicSetting) -> None:
    now = now_utc()
    row = _winning_row(db, event_id)
    settings.round_status = "LOCKED"
    settings.round_locked_at = now
    settings.winner_decided_at = now
    if row is None:
        settings.winner_candidate_key = None
        settings.winner_candidate_json = None
        settings.winner_votes_count = 0
    else:
        settings.winner_candidate_key = row.candidate_key
        settings.winner_candidate_json = {
            "provider": row.provider,
            "externalUrl": row.external_url,
            "title": row.title,
            "artist": row.artist,
            "artworkUrl": row.artwork_url,
        }
        settings.winner_votes_count = int(row.votes or 0)
    settings.last_updated_at = now
    settings.updated_at = now
    db.add(settings)


def _lazy_finalize_if_needed(db: Session, event_id: int, settings: EventMusicSetting) -> bool:
    if (settings.round_status or "IDLE").upper() != "OPEN" or not settings.round_ends_at:
        return False
    if now_utc() < settings.round_ends_at:
        return False
    _lock_round_with_winner(db, event_id, settings)
    return True


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




@router.get("/{event_id}/music/pre_event")
def music_pre_event_get(event_id: int, db: Session = Depends(get_db)):
    _ensure_module_or_404(db, event_id)
    return {"items": _pre_event_top(db, event_id), "top": _pre_event_top(db, event_id, limit=8)}


@router.post("/{event_id}/music/pre_event/suggest")
def music_pre_event_suggest(
    event_id: int,
    body: PreEventSuggestIn,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"reason": "idempotency_required"})
    _ensure_module_or_404(db, event_id)
    _runtime_write_guard(db, event_id)
    existing = (
        db.query(EventMusicActionIdempotency)
        .filter(
            EventMusicActionIdempotency.event_id == event_id,
            EventMusicActionIdempotency.action_type == "pre_event_suggest",
            EventMusicActionIdempotency.idempotency_key == idempotency_key,
            EventMusicActionIdempotency.actor_user_id == user.id,
        )
        .first()
    )
    if existing:
        return existing.response_json
    last = (
        db.query(EventMusicSuggestion)
        .filter(EventMusicSuggestion.event_id == event_id, EventMusicSuggestion.user_id == user.id)
        .order_by(EventMusicSuggestion.created_at.desc())
        .first()
    )
    if last and (now_utc() - last.created_at).total_seconds() < _PRE_EVENT_COOLDOWN_SECONDS:
        raise HTTPException(status_code=429, detail={"reason": "suggestion_cooldown"})
    provider, normalized_url, _ = _normalize_candidate_link(body.provider, body.externalUrl)
    row = EventMusicSuggestion(
        event_id=event_id,
        user_id=user.id,
        provider=provider,
        external_url=normalized_url,
        title=body.title,
        artist=body.artist,
    )
    db.add(row)
    db.flush()
    payload = {"ok": True, "suggestionId": row.id, "top": _pre_event_top(db, event_id, limit=8)}
    db.add(EventMusicActionIdempotency(event_id=event_id, action_type="pre_event_suggest", actor_user_id=user.id, idempotency_key=idempotency_key, response_json=payload))
    db.commit()
    return payload


@router.post("/{event_id}/music/pre_event/vote")
def music_pre_event_vote(
    event_id: int,
    body: PreEventVoteIn,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"reason": "idempotency_required"})
    _ensure_module_or_404(db, event_id)
    _runtime_write_guard(db, event_id)
    existing = (
        db.query(EventMusicActionIdempotency)
        .filter(
            EventMusicActionIdempotency.event_id == event_id,
            EventMusicActionIdempotency.action_type == "pre_event_vote",
            EventMusicActionIdempotency.idempotency_key == idempotency_key,
            EventMusicActionIdempotency.actor_user_id == user.id,
        )
        .first()
    )
    if existing:
        return existing.response_json
    suggestion = db.get(EventMusicSuggestion, body.suggestionId)
    if not suggestion or suggestion.event_id != event_id:
        raise HTTPException(status_code=404, detail={"reason": "suggestion_not_found"})
    last = (
        db.query(EventMusicSuggestionVote)
        .filter(EventMusicSuggestionVote.event_id == event_id, EventMusicSuggestionVote.user_id == user.id)
        .order_by(EventMusicSuggestionVote.created_at.desc())
        .first()
    )
    if last and (now_utc() - last.created_at).total_seconds() < _PRE_EVENT_COOLDOWN_SECONDS:
        raise HTTPException(status_code=429, detail={"reason": "vote_cooldown"})
    existing_vote = db.query(EventMusicSuggestionVote).filter(
        EventMusicSuggestionVote.event_id == event_id,
        EventMusicSuggestionVote.user_id == user.id,
        EventMusicSuggestionVote.suggestion_id == body.suggestionId,
    ).first()
    if not existing_vote:
        db.add(EventMusicSuggestionVote(event_id=event_id, user_id=user.id, suggestion_id=body.suggestionId))
    payload = {"ok": True, "top": _pre_event_top(db, event_id, limit=8)}
    db.add(EventMusicActionIdempotency(event_id=event_id, action_type="pre_event_vote", actor_user_id=user.id, idempotency_key=idempotency_key, response_json=payload))
    db.commit()
    return payload

@router.get("/{event_id}/music")
def music_get(event_id: int, db: Session = Depends(get_db)):
    _ensure_module_or_404(db, event_id)
    settings = _get_or_create_settings(db, event_id)
    _lazy_finalize_if_needed(db, event_id, settings)
    payload = {
        "enabled": bool(settings.enabled),
        "djOverrideEnabled": bool(settings.dj_override_enabled),
        "allowMixedProviders": bool(settings.allow_mixed),
        "providerDefault": settings.provider_default,
        "round": _round_payload(settings),
        "nowPlaying": settings.now_playing_candidate_json,
        "winner": _winner_payload(settings),
        "topCandidates": _top_candidates(db, event_id),
        "candidates": _list_candidates(db, event_id, settings.round_id),
        "providers": ["spotify", "apple", "youtube_music", "soundcloud"],
        "lastUpdatedAt": settings.last_updated_at.isoformat() if settings.last_updated_at else None,
        "runtimeState": (get_event_runtime_state(db, event_id) or "LIVE").upper(),
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
    _lazy_finalize_if_needed(db, event_id, settings)
    if (settings.round_status or "IDLE").upper() != "OPEN":
        raise HTTPException(status_code=409, detail={"reason": "VOTE_CLOSED"})
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

    provider, normalized_url, external_id = _normalize_candidate_link(body.candidate.provider, body.candidate.externalUrl)
    key = _candidate_key(body.candidate)
    vote = EventMusicVote(
        event_id=event_id,
        user_id=user.id,
        candidate_key=key,
        provider=provider,
        external_url=normalized_url,
        title=body.candidate.title,
        artist=body.candidate.artist,
        artwork_url=body.candidate.artworkUrl,
    )
    db.add(vote)
    db.add(
        EventMusicCandidate(
            event_id=event_id,
            round_id=settings.round_id,
            candidate_key=key,
            provider=provider,
            url_original=body.candidate.externalUrl,
            url_normalized=normalized_url,
            external_id=external_id,
            title_hint=body.candidate.titleHint,
            external_url=normalized_url,
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


@router.post("/{event_id}/music/candidates")
def music_add_candidate(
    event_id: int,
    body: CandidateAddIn,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"reason": "idempotency_required"})
    _ensure_module_or_404(db, event_id)
    settings = _get_or_create_settings(db, event_id)
    _lazy_finalize_if_needed(db, event_id, settings)
    if (settings.round_status or "IDLE").upper() != "OPEN":
        raise HTTPException(status_code=409, detail={"reason": "VOTE_CLOSED"})
    if not settings.enabled:
        raise HTTPException(status_code=403, detail={"reason": "music_disabled"})
    _runtime_write_guard(db, event_id)

    provider, normalized_url, external_id = _normalize_candidate_link(body.provider, body.externalUrl)

    q = db.query(EventMusicCandidate).filter(
        EventMusicCandidate.event_id == event_id,
        EventMusicCandidate.round_id == settings.round_id,
        EventMusicCandidate.provider == provider,
    )
    if external_id:
        q = q.filter((EventMusicCandidate.external_id == external_id) | (EventMusicCandidate.url_normalized == normalized_url))
    else:
        q = q.filter(EventMusicCandidate.url_normalized == normalized_url)
    existing = q.first()
    if existing:
        return {"ok": True, "status": "already_exists", "candidate": _candidate_out(existing)}

    row = EventMusicCandidate(
        event_id=event_id,
        round_id=settings.round_id,
        candidate_key=f"{provider}:{external_id or normalized_url}",
        provider=provider,
        url_original=body.externalUrl,
        url_normalized=normalized_url,
        external_id=external_id,
        title_hint=body.titleHint,
        external_url=normalized_url,
        title=body.titleHint or "",
        artist="",
    )
    db.add(row)
    settings.last_updated_at = now_utc()
    settings.updated_at = now_utc()
    db.add(settings)
    write_audit_log(
        db,
        actor_partner_id=None,
        actor_role="app_user",
        action="music_vote.candidate_added",
        entity_type="event_music",
        entity_id=str(event_id),
        event_id=event_id,
        bar_id=None,
        payload={"provider": provider, "external_id": external_id, "url_normalized": normalized_url, "actor_user_id": user.id},
    )
    db.commit()
    db.refresh(row)
    return {"ok": True, "status": "added", "candidate": _candidate_out(row)}


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
        provider = _canonical_provider(body.providerDefault)
        if provider not in _PROVIDER_SET:
            raise HTTPException(status_code=400, detail={"reason": "provider_invalid"})
        settings.provider_default = provider
    settings.updated_at = now_utc()
    settings.last_updated_at = now_utc()
    settings.updated_by = str(identity["user_id"])
    db.add(settings)
    response = {
        "ok": True,
        "settings": {
            "enabled": settings.enabled,
            "djOverrideEnabled": settings.dj_override_enabled,
            "allowMixedProviders": settings.allow_mixed,
            "providerDefault": settings.provider_default,
        },
    }
    db.add(
        EventMusicAdminIdempotency(
            event_id=event_id,
            action_type="settings",
            idempotency_key=idempotency_key,
            actor_partner_id=identity["user_id"],
            response_json=response,
        )
    )
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


@router.post("/{event_id}/music/admin/round/start")
@router.post("/{event_id}/music/rounds/start")
def music_round_start(
    event_id: int,
    body: RoundStartIn,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"reason": "idempotency_required"})
    if body.durationSec not in _ALLOWED_ROUND_DURATIONS:
        raise HTTPException(status_code=400, detail={"reason": "invalid_duration"})
    event = _ensure_module_or_404(db, event_id)
    settings = _get_or_create_settings(db, event_id)
    _runtime_write_guard(db, event_id)
    mode, actor_partner_id, actor_role = _admin_or_dj_guard(db, event, settings, authorization)
    existing = db.query(EventMusicAdminIdempotency).filter(
        EventMusicAdminIdempotency.event_id == event_id,
        EventMusicAdminIdempotency.action_type == "round_start",
        EventMusicAdminIdempotency.idempotency_key == idempotency_key,
    ).first()
    if existing:
        return existing.response_json

    started_at = now_utc()
    settings.round_id = str(uuid4())
    settings.round_status = "OPEN"
    settings.round_started_at = started_at
    settings.round_duration_sec = body.durationSec
    settings.round_ends_at = started_at + timedelta(seconds=body.durationSec)
    round_row = EventMusicRound(
        event_id=event_id,
        status="OPEN",
        duration_sec=body.durationSec,
        started_at=started_at,
        ends_at=started_at + timedelta(seconds=body.durationSec),
        created_by=f"{actor_role}:{actor_partner_id or 'dj'}",
    )
    db.add(round_row)
    settings.round_locked_at = None
    settings.winner_candidate_key = None
    settings.winner_candidate_json = None
    settings.winner_decided_at = None
    settings.winner_votes_count = 0
    settings.last_updated_at = started_at
    settings.updated_at = started_at
    db.query(EventMusicVote).filter(EventMusicVote.event_id == event_id).delete(synchronize_session=False)
    db.add(settings)
    response = {"ok": True, "round": _round_payload(settings)}
    db.add(EventMusicAdminIdempotency(event_id=event_id, action_type="round_start", idempotency_key=idempotency_key, actor_partner_id=actor_partner_id, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=actor_partner_id,
        actor_role=actor_role,
        action="music_vote.round_start",
        entity_type="event_music",
        entity_id=str(event_id),
        event_id=event_id,
        bar_id=event.bar_id,
        payload={"durationSec": body.durationSec, "actor_mode": mode},
    )
    db.commit()
    return response


@router.post("/{event_id}/music/admin/round/end")
@router.post("/{event_id}/music/rounds/close")
def music_round_end(
    event_id: int,
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
        EventMusicAdminIdempotency.action_type == "round_end",
        EventMusicAdminIdempotency.idempotency_key == idempotency_key,
    ).first()
    if existing:
        return existing.response_json

    _lock_round_with_winner(db, event_id, settings)
    round_row = _current_round_row(db, event_id)
    if round_row and (round_row.status or "").upper() == "OPEN":
        round_row.status = "CLOSED"
        round_row.closed_at = now_utc()
        winner_key = settings.winner_candidate_key
        if winner_key:
            winner_candidate = db.query(EventMusicCandidate).filter(
                EventMusicCandidate.event_id == event_id,
                EventMusicCandidate.round_id == settings.round_id,
                EventMusicCandidate.candidate_key == winner_key,
            ).first()
            round_row.winner_candidate_id = winner_candidate.id if winner_candidate else None
        db.add(round_row)
    response = {"ok": True, "round": _round_payload(settings), "winner": _winner_payload(settings), "current": _current_round_payload(db, event_id).get("round")}
    db.add(EventMusicAdminIdempotency(event_id=event_id, action_type="round_end", idempotency_key=idempotency_key, actor_partner_id=actor_partner_id, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=actor_partner_id,
        actor_role=actor_role,
        action="music_vote.round_end",
        entity_type="event_music",
        entity_id=str(event_id),
        event_id=event_id,
        bar_id=event.bar_id,
        payload={"actor_mode": mode, "winner": settings.winner_candidate_key},
    )
    db.commit()
    return response


@router.get("/{event_id}/music/rounds/current")
def music_round_current(event_id: int, db: Session = Depends(get_db)):
    _ensure_module_or_404(db, event_id)
    return _current_round_payload(db, event_id)


@router.post("/{event_id}/music/admin/now-playing")
@router.post("/{event_id}/music/now_playing")
def music_now_playing(
    event_id: int,
    body: NowPlayingIn,
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
        EventMusicAdminIdempotency.action_type == "now_playing",
        EventMusicAdminIdempotency.idempotency_key == idempotency_key,
    ).first()
    if existing:
        return existing.response_json

    provider, normalized_url, external_id = _normalize_candidate_link(body.candidate.provider, body.candidate.externalUrl)
    candidate_json = body.candidate.model_dump()
    candidate_json.update({"provider": provider, "externalUrl": normalized_url, "externalId": external_id})
    settings.now_playing_candidate_json = candidate_json
    settings.last_updated_at = now_utc()
    settings.updated_at = now_utc()
    db.add(settings)
    response = {"ok": True, "nowPlaying": settings.now_playing_candidate_json}
    db.add(EventMusicAdminIdempotency(event_id=event_id, action_type="now_playing", idempotency_key=idempotency_key, actor_partner_id=actor_partner_id, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=actor_partner_id,
        actor_role=actor_role,
        action="music_vote.now_playing",
        entity_type="event_music",
        entity_id=str(event_id),
        event_id=event_id,
        bar_id=event.bar_id,
        payload={"candidate": settings.now_playing_candidate_json, "reason": body.reason, "actor_mode": mode},
    )
    db.commit()
    return response


@router.post("/{event_id}/music/admin/skip")
@router.post("/{event_id}/music/skip_winner")
def music_skip(
    event_id: int,
    body: SkipIn,
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
        EventMusicAdminIdempotency.action_type == "skip",
        EventMusicAdminIdempotency.idempotency_key == idempotency_key,
    ).first()
    if existing:
        return existing.response_json

    settings.winner_candidate_key = None
    settings.winner_candidate_json = None
    settings.winner_decided_at = None
    settings.winner_votes_count = 0
    settings.round_status = "OPEN" if body.reopen and settings.round_started_at else "IDLE"
    settings.round_locked_at = None
    settings.last_updated_at = now_utc()
    settings.updated_at = now_utc()
    db.add(settings)
    response = {"ok": True, "round": _round_payload(settings), "winner": None}
    db.add(EventMusicAdminIdempotency(event_id=event_id, action_type="skip", idempotency_key=idempotency_key, actor_partner_id=actor_partner_id, response_json=response))
    write_audit_log(
        db,
        actor_partner_id=actor_partner_id,
        actor_role=actor_role,
        action="music_vote.skip",
        entity_type="event_music",
        entity_id=str(event_id),
        event_id=event_id,
        bar_id=event.bar_id,
        payload={"reason": body.reason, "actor_mode": mode},
    )
    db.commit()
    return response


@router.post("/{event_id}/music/admin/force")
@router.post("/{event_id}/music/force")
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

    provider, normalized_url, external_id = _normalize_candidate_link(body.candidate.provider, body.candidate.externalUrl)
    key = _candidate_key(body.candidate)
    candidate_json = body.candidate.model_dump()
    candidate_json.update({"provider": provider, "externalUrl": normalized_url, "externalId": external_id})
    settings.winner_candidate_key = key
    settings.winner_candidate_json = candidate_json
    settings.winner_decided_at = now_utc()
    settings.winner_votes_count = 0
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
    settings.winner_votes_count = 0
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
