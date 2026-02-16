from __future__ import annotations

from typing import Iterator

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.schemas.qr import QrResolveIn, QrResolveOut
from app.services.p3_common import effective_module_state
from app.services.qr_service import resolve_qr_payload
from app.services.qr_validation_service import validate_signed_qr
from app.services.rate_limit_service import enforce_rate_limit
from models import AppUser, Battle, Bet, Order
from main import _role_rank, get_current_user, resolve_event_role

router = APIRouter()


QR_RUNTIME_POLICY = {
    "entry": ("entry_enabled", True),
    "staff_entry": ("entry_enabled", True),
    "entry_staff": ("entry_enabled", True),
    "bar_staff": ("orders_enabled", False),
    "checkins": ("checkins_enabled", True),
    "hunt": ("hunt_enabled", True),
    "wifi": ("wifi_enabled", False),
    "safety": ("safety_enabled", True),
    "menu": ("orders_enabled", False),
    "market": ("market_enabled", False),
    "battle": ("battles_enabled", False),
    "polymarket_bet": ("polymarket_enabled", False),
    "wallet_user": ("wallet_enabled", True),
}



def _resolve_runtime_gate(db: Session, qr_type: str, event_id: int | None) -> tuple[bool, str | None]:
    policy = QR_RUNTIME_POLICY.get(qr_type)
    if not policy or event_id is None:
        return True, None
    module_field, write_intent = policy
    state, reason = effective_module_state(db, event_id, module_field)
    if state == "OFF":
        return False, reason
    if state == "READ_ONLY" and write_intent:
        return False, reason
    return True, None


def get_db() -> Iterator[Session]:
    from main import get_db as _get_db

    yield from _get_db()


@router.post("/qr/resolve", response_model=QrResolveOut)
def qr_resolve(
    payload: QrResolveIn,
    request: Request,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    actor_key = user.id or (request.client.host if request.client else "anon")
    enforce_rate_limit("qr_resolve", actor_key)
    base = resolve_qr_payload(payload.raw)
    if not base.get("valid"):
        return {
            "valid": False,
            "type": base.get("type") or "unknown",
            "event_id": None,
            "bar_id": None,
            "item_id": None,
            "category_id": None,
            "zone_id": None,
            "bet_id": None,
            "order_id": None,
            "battle_id": None,
            "scope": None,
            "route_front": None,
            "token": None,
            "reason": base.get("reason") or "invalid_qr",
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
            "zone_id": None,
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


    if qr_type == "wallet_user":
        required_role = "entry"
        granted_role = resolve_event_role(db, user.id, event_id) if event_id is not None else "guest"
        allowed, blocked_reason = _resolve_runtime_gate(db, qr_type, event_id)
        if not allowed:
            return {
                "valid": False,
                "type": qr_type,
                "event_id": event_id,
                "bar_id": None,
                "item_id": None,
                "category_id": None,
                "zone_id": None,
                "bet_id": None,
                "order_id": None,
                "battle_id": None,
                "scope": None,
                "route_front": None,
                "token": None,
                "user_id": base.get("user_id"),
                "reason": blocked_reason,
                "required_role": required_role,
                "granted_role": granted_role,
                "data": base.get("data"),
            }
        if _role_rank(granted_role) < _role_rank(required_role):
            return {
                "valid": False,
                "type": qr_type,
                "event_id": event_id,
                "bar_id": None,
                "item_id": None,
                "category_id": None,
                "zone_id": None,
                "bet_id": None,
                "order_id": None,
                "battle_id": None,
                "scope": None,
                "route_front": None,
                "token": None,
                "user_id": base.get("user_id"),
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
            "zone_id": None,
            "bet_id": None,
            "order_id": None,
            "battle_id": None,
            "scope": None,
            "route_front": base.get("route_front") or "topup_target",
            "token": None,
            "user_id": base.get("user_id"),
            "reason": None,
            "required_role": required_role,
            "granted_role": granted_role,
            "data": base.get("data"),
        }

    if qr_type == "menu":
        return {
            "valid": True,
            "type": "menu",
            "event_id": base.get("event_id"),
            "bar_id": base.get("bar_id"),
            "item_id": base.get("item_id"),
            "category_id": base.get("category_id"),
            "zone_id": base.get("zone_id"),
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
                "reason": "invalid_qr",
                "required_role": None,
                "granted_role": "guest",
                "data": base.get("data"),
            }
        allowed, blocked_reason = _resolve_runtime_gate(db, qr_type, battle.event_id)
        if not allowed:
            return {
                "valid": False,
                "type": qr_type,
                "event_id": battle.event_id,
                "bar_id": battle.bar_id,
                "item_id": None,
                "category_id": None,
                "bet_id": None,
                "order_id": None,
                "battle_id": battle.id,
                "scope": None,
                "route_front": None,
                "token": None,
                "reason": blocked_reason,
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
            "zone_id": None,
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
                "reason": "invalid_qr",
                "required_role": None,
                "granted_role": "guest",
                "data": base.get("data"),
            }
        allowed, blocked_reason = _resolve_runtime_gate(db, qr_type, bet.event_id)
        if not allowed:
            return {
                "valid": False,
                "type": qr_type,
                "event_id": bet.event_id,
                "bar_id": None,
                "item_id": None,
                "category_id": None,
                "bet_id": bet.id,
                "order_id": None,
                "battle_id": None,
                "scope": bet.scope,
                "route_front": None,
                "token": None,
                "reason": blocked_reason,
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
                "reason": "invalid_qr",
                "required_role": None,
                "granted_role": "guest",
                "data": base.get("data"),
            }
        allowed, blocked_reason = _resolve_runtime_gate(db, qr_type, order.event_id)
        if not allowed:
            return {
                "valid": False,
                "type": qr_type,
                "event_id": order.event_id,
                "bar_id": order.bar_id,
                "item_id": None,
                "category_id": None,
                "bet_id": None,
                "order_id": order.id,
                "battle_id": None,
                "scope": None,
                "route_front": None,
                "token": None,
                "reason": blocked_reason,
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
            "zone_id": None,
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

    signed_valid, signed_reason, signed_token_id, signed_expires_at = validate_signed_qr(payload.raw, qr_type=qr_type, event_id=event_id, db=db)
    if not signed_valid:
        return {
            "valid": False,
            "type": qr_type,
            "event_id": event_id,
            "bar_id": None,
            "item_id": None,
            "category_id": None,
            "zone_id": None,
            "bet_id": None,
            "order_id": None,
            "battle_id": None,
            "scope": None,
            "route_front": None,
            "token": signed_token_id,
            "reason": signed_reason,
            "required_role": None,
            "granted_role": "guest",
            "data": {**(base.get("data") or {}), "expires_at": signed_expires_at.isoformat() if signed_expires_at else None},
        }

    role_map = {
        "join": "guest",
        "join_event": "guest",
        "menu": "guest",
        "event": "guest",
        "entry": "entry",
        "staff": "entry",
        "payment": "guest",
        "paiement": "guest",
        "hunt": "guest",
        "gift": "guest",
        "wifi": "guest",
        "safety": "guest",
        "checkins": "guest",
        "admin_config": "admin",
        "staff_entry": "entry",
        "entry_staff": "entry",
        "bar_staff": "entry",
        "staff_invite": "guest",
    }
    required_role = role_map.get(qr_type, "guest")
    granted_role = resolve_event_role(db, user.id, event_id)

    allowed, blocked_reason = _resolve_runtime_gate(db, qr_type, event_id)
    if not allowed:
        return {
            "valid": False,
            "type": qr_type,
            "event_id": event_id,
            "bar_id": None,
            "item_id": None,
            "category_id": None,
            "zone_id": None,
            "bet_id": None,
            "order_id": None,
            "battle_id": None,
            "scope": None,
            "route_front": None,
            "token": None,
            "reason": blocked_reason,
            "required_role": required_role,
            "granted_role": granted_role,
            "data": base.get("data"),
        }

    if _role_rank(granted_role) < _role_rank(required_role):
        return {
            "valid": False,
            "type": qr_type,
            "event_id": event_id,
            "bar_id": base.get("bar_id"),
            "item_id": base.get("item_id"),
            "category_id": base.get("category_id"),
            "zone_id": base.get("zone_id"),
            "bet_id": None,
            "order_id": None,
            "battle_id": None,
            "scope": None,
            "route_front": None,
            "token": signed_token_id or token,
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
        "category_id": base.get("category_id"),
        "zone_id": base.get("zone_id"),
        "bet_id": None,
        "order_id": None,
        "battle_id": None,
        "scope": None,
        "route_front": None,
        "token": signed_token_id or token,
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
