from __future__ import annotations

from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException
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
from models import Hunt, HuntPoint
from partner_auth import current_identity as current_partner_identity

router = APIRouter()


def get_db() -> Iterator[Session]:
    from main import get_db as _get_db

    yield from _get_db()


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
