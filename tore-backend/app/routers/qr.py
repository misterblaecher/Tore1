from __future__ import annotations

from typing import Iterator

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.schemas.qr import QrResolveIn, QrResolveOut
from app.services.qr_service import resolve_qr_payload
from models import AppUser, Battle, Bet, Order
from main import _role_rank, get_current_user, resolve_event_role

router = APIRouter()


def get_db() -> Iterator[Session]:
    from main import get_db as _get_db

    yield from _get_db()


@router.post("/qr/resolve", response_model=QrResolveOut)
def qr_resolve(
    payload: QrResolveIn,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base = resolve_qr_payload(payload.raw)
    if not base.get("valid"):
        return {
            "valid": False,
            "type": "unknown",
            "event_id": None,
            "bar_id": None,
            "item_id": None,
            "category_id": None,
            "bet_id": None,
            "order_id": None,
            "battle_id": None,
            "scope": None,
            "route_front": None,
            "token": None,
            "reason": base.get("reason"),
            "required_role": None,
            "granted_role": "guest",
            "data": base.get("data"),
        }

    event_id = base.get("event_id")
    qr_type = base.get("type")
    token = base.get("token")
    if qr_type == "wallet_topup":
        return {
            "valid": True,
            "type": qr_type,
            "event_id": None,
            "bar_id": None,
            "item_id": None,
            "category_id": None,
            "bet_id": None,
            "order_id": None,
            "battle_id": None,
            "scope": None,
            "route_front": None,
            "token": None,
            "user_id": base.get("user_id"),
            "amount_tickets": base.get("amount_tickets"),
            "idempotency_key": base.get("idempotency_key"),
            "reason": None,
            "required_role": None,
            "granted_role": "guest",
            "data": base.get("data"),
        }

    if qr_type == "menu":
        return {
            "valid": True,
            "type": "menu",
            "event_id": None,
            "bar_id": base.get("bar_id"),
            "item_id": base.get("item_id"),
            "category_id": base.get("category_id"),
            "bet_id": None,
            "order_id": None,
            "battle_id": None,
            "scope": None,
            "route_front": base.get("route_front"),
            "token": None,
            "reason": None,
            "required_role": None,
            "granted_role": "guest",
            "data": base.get("data"),
        }

    if qr_type == "battle":
        battle = db.get(Battle, base.get("battle_id"))
        if not battle:
            return {
                "valid": False,
                "type": "unknown",
                "event_id": None,
                "bar_id": None,
                "item_id": None,
                "category_id": None,
                "bet_id": None,
                "order_id": None,
                "battle_id": None,
                "scope": None,
                "route_front": None,
                "token": None,
                "reason": "invalid",
                "required_role": None,
                "granted_role": "guest",
                "data": base.get("data"),
            }
        return {
            "valid": True,
            "type": "battle",
            "event_id": battle.event_id,
            "bar_id": battle.bar_id,
            "item_id": None,
            "category_id": None,
            "bet_id": None,
            "order_id": None,
            "battle_id": battle.id,
            "scope": None,
            "route_front": base.get("route_front"),
            "token": None,
            "reason": None,
            "required_role": None,
            "granted_role": "guest",
            "data": base.get("data"),
        }

    if qr_type == "polymarket_bet":
        bet = db.get(Bet, base.get("bet_id"))
        if not bet:
            return {
                "valid": False,
                "type": "unknown",
                "event_id": None,
                "bar_id": None,
                "item_id": None,
                "category_id": None,
                "bet_id": None,
                "order_id": None,
                "scope": None,
                "route_front": None,
                "token": None,
                "reason": "invalid",
                "required_role": None,
                "granted_role": "guest",
                "data": base.get("data"),
            }
        return {
            "valid": True,
            "type": "polymarket_bet",
            "event_id": bet.event_id,
            "bar_id": None,
            "item_id": None,
            "category_id": None,
            "bet_id": bet.id,
            "order_id": None,
            "battle_id": None,
            "scope": bet.scope,
            "route_front": base.get("route_front"),
            "token": None,
            "reason": None,
            "required_role": None,
            "granted_role": "guest",
            "data": base.get("data"),
        }

    if qr_type == "order":
        order = db.get(Order, base.get("order_id"))
        if not order:
            return {
                "valid": False,
                "type": "unknown",
                "event_id": None,
                "bar_id": None,
                "item_id": None,
                "category_id": None,
                "bet_id": None,
                "order_id": None,
                "scope": None,
                "route_front": None,
                "token": None,
                "reason": "invalid",
                "required_role": None,
                "granted_role": "guest",
                "data": base.get("data"),
            }
        return {
            "valid": True,
            "type": "order",
            "event_id": order.event_id,
            "bar_id": order.bar_id,
            "item_id": None,
            "category_id": None,
            "bet_id": None,
            "order_id": order.id,
            "battle_id": None,
            "scope": None,
            "route_front": base.get("route_front"),
            "token": None,
            "reason": None,
            "required_role": None,
            "granted_role": "guest",
            "data": base.get("data"),
        }

    role_map = {
        "join": "guest",
        "menu": "guest",
        "entry": "entry",
        "admin_config": "admin",
        "staff_entry": "entry",
        "staff_invite": "guest",
    }
    required_role = role_map.get(qr_type, "guest")
    granted_role = resolve_event_role(db, user.id, event_id)

    if _role_rank(granted_role) < _role_rank(required_role):
        return {
            "valid": False,
            "type": "unknown",
            "event_id": None,
            "bar_id": None,
            "item_id": None,
            "category_id": None,
            "bet_id": None,
            "order_id": None,
            "battle_id": None,
            "scope": None,
            "route_front": None,
            "token": None,
            "reason": "forbidden",
            "required_role": required_role,
            "granted_role": granted_role,
            "data": base.get("data"),
        }

    return {
        "valid": True,
        "type": qr_type,
        "event_id": event_id,
        "bar_id": None,
        "item_id": None,
        "category_id": None,
        "bet_id": None,
        "order_id": None,
        "battle_id": None,
        "scope": None,
        "route_front": None,
        "token": token,
        "reason": None,
        "required_role": required_role,
        "granted_role": granted_role,
        "data": base.get("data"),
    }


@router.get("/qr/resolve", response_model=QrResolveOut)
def qr_resolve_get(
    raw: str = Query(..., min_length=1),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return qr_resolve(QrResolveIn(raw=raw), user=user, db=db)
