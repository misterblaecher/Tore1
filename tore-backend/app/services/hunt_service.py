from __future__ import annotations

import secrets
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db import now_utc
from models import Event, Hunt, HuntPoint, HuntScan, WalletTx
from app.services.wallet_service import apply_wallet_tx


def require_manager(identity: dict) -> None:
    if identity.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Forbidden")


def get_hunt_for_bar(s: Session, hunt_id: int, bar_id: int) -> Hunt:
    hunt = s.get(Hunt, hunt_id)
    if not hunt:
        raise HTTPException(status_code=404, detail="Hunt not found")
    if hunt.bar_id != bar_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return hunt


def get_event_for_bar(s: Session, event_id: int, bar_id: int) -> Event:
    event = s.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.bar_id != bar_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return event


def generate_secret_code(s: Session) -> str:
    for _ in range(20):
        code = f"HP-{secrets.token_hex(3).upper()}"
        exists = s.query(HuntPoint.id).filter(HuntPoint.secret_code == code).first()
        if not exists:
            return code
    raise HTTPException(status_code=500, detail="Unable to generate unique secret code")


def qr_payload(event_id: int, code: str) -> str:
    return f"tore://hunt?event_id={event_id}&code={code}"


def route_front(event_id: int, code: str) -> str:
    return f"/hunt/scan?event_id={event_id}&code={code}"


def build_progress(s: Session, hunt: Hunt, user_id: str) -> dict:
    points = (
        s.query(HuntPoint)
        .filter(HuntPoint.hunt_id == hunt.id)
        .order_by(HuntPoint.sort_order.asc(), HuntPoint.id.asc())
        .all()
    )
    active_point_ids = [p.id for p in points if p.is_active]
    scanned_ids = {
        row[0]
        for row in s.query(HuntScan.point_id)
        .filter(HuntScan.hunt_id == hunt.id, HuntScan.user_id == user_id)
        .all()
    }
    completed = bool(active_point_ids) and all(pid in scanned_ids for pid in active_point_ids)
    completion = (len([pid for pid in active_point_ids if pid in scanned_ids]) / len(active_point_ids)) if active_point_ids else 0.0
    reward_granted = (
        s.query(WalletTx.id)
        .filter(
            WalletTx.user_id == user_id,
            WalletTx.kind == "HUNT_REWARD",
            WalletTx.ref_type == "HUNT",
            WalletTx.ref_id == str(hunt.id),
        )
        .first()
        is not None
    )
    return {
        "points": points,
        "scanned_ids": scanned_ids,
        "completed": completed,
        "completion": completion,
        "reward_granted": reward_granted,
    }


def scan_point(
    s: Session,
    *,
    event_id: int,
    code: str,
    user_id: str,
    device_id: Optional[str] = None,
) -> dict:
    hunt = (
        s.query(Hunt)
        .filter(Hunt.event_id == event_id, Hunt.is_active.is_(True))
        .order_by(Hunt.id.desc())
        .first()
    )
    if not hunt:
        raise HTTPException(status_code=404, detail="Active hunt not found")

    point = (
        s.query(HuntPoint)
        .filter(HuntPoint.hunt_id == hunt.id, HuntPoint.secret_code == code, HuntPoint.is_active.is_(True))
        .first()
    )
    if not point:
        raise HTTPException(status_code=404, detail="Point not found")

    already_scanned = False
    scan = HuntScan(
        hunt_id=hunt.id,
        point_id=point.id,
        user_id=user_id,
        device_id=device_id,
        created_at=now_utc(),
    )
    s.add(scan)
    try:
        s.flush()
    except IntegrityError:
        s.rollback()
        already_scanned = True

    hunt = s.get(Hunt, hunt.id)
    progress = build_progress(s, hunt, user_id)

    reward_granted = progress["reward_granted"]
    if progress["completed"] and hunt.reward_tickets > 0 and not reward_granted:
        idempotency_key = f"hunt-reward:{hunt.id}"
        _, _, created = apply_wallet_tx(
            s,
            user_id=user_id,
            amount_tickets=hunt.reward_tickets,
            kind="HUNT_REWARD",
            ref_type="HUNT",
            ref_id=str(hunt.id),
            idempotency_key=idempotency_key,
        )
        if created:
            reward_granted = True

    s.commit()

    return {
        "hunt_id": hunt.id,
        "point_id": point.id,
        "already_scanned": already_scanned,
        "completion": progress["completion"],
        "completed": progress["completed"],
        "reward_granted": reward_granted,
        "reward_tickets": hunt.reward_tickets if reward_granted else 0,
    }


def hunt_stats(s: Session, hunt_id: int) -> dict:
    participants = s.query(func.count(func.distinct(HuntScan.user_id))).filter(HuntScan.hunt_id == hunt_id).scalar() or 0
    scans_total = s.query(func.count(HuntScan.id)).filter(HuntScan.hunt_id == hunt_id).scalar() or 0

    active_points = s.query(HuntPoint.id).filter(HuntPoint.hunt_id == hunt_id, HuntPoint.is_active.is_(True)).count()
    completion_count = 0
    if active_points > 0:
        rows = (
            s.query(HuntScan.user_id, func.count(func.distinct(HuntScan.point_id)).label("cnt"))
            .join(HuntPoint, HuntPoint.id == HuntScan.point_id)
            .filter(HuntScan.hunt_id == hunt_id, HuntPoint.is_active.is_(True))
            .group_by(HuntScan.user_id)
            .all()
        )
        completion_count = sum(1 for row in rows if row.cnt >= active_points)

    top_points_rows = (
        s.query(HuntPoint.id, HuntPoint.name, func.count(HuntScan.id).label("scans"))
        .outerjoin(HuntScan, HuntScan.point_id == HuntPoint.id)
        .filter(HuntPoint.hunt_id == hunt_id)
        .group_by(HuntPoint.id, HuntPoint.name)
        .order_by(func.count(HuntScan.id).desc(), HuntPoint.id.asc())
        .limit(5)
        .all()
    )
    top_points = [
        {"point_id": row.id, "name": row.name, "scans": int(row.scans or 0)}
        for row in top_points_rows
    ]
    return {
        "participants": int(participants),
        "scans_total": int(scans_total),
        "completion_count": int(completion_count),
        "top_points": top_points,
    }
