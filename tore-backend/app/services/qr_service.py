from __future__ import annotations

from typing import Any, Dict
from urllib.parse import parse_qs, urlparse


def resolve_qr_payload(raw: str) -> Dict[str, Any]:
    trimmed = (raw or "").strip()
    if not trimmed:
        return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}

    # Manual fallback (short code typed by staff/user when camera/QR fails)
    if not trimmed.startswith("tore://"):
        code = trimmed.replace(" ", "")
        if len(code) >= 4 and code.isalnum():
            return {
                "valid": False,
                "type": "manual_code",
                "event_id": None,
                "reason": "manual_required",
                "data": {"manual_code": code.upper()},
            }
        return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}

    parsed = urlparse(trimmed)
    if parsed.scheme.lower() != "tore":
        return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}

    qr_type = (parsed.netloc or parsed.path.lstrip("/")).lower()
    if qr_type == "wallet":
        action = parsed.path.lstrip("/").lower()
        if action != "topup":
            return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}
        params = parse_qs(parsed.query)
        user_id = (params.get("user_id") or [None])[0]
        amount_raw = (params.get("amount") or [None])[0]
        nonce = (params.get("nonce") or [None])[0]
        if not user_id or not amount_raw or not nonce:
            return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}
        try:
            amount_tickets = int(amount_raw)
        except (TypeError, ValueError):
            return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}
        if amount_tickets <= 0:
            return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}
        return {
            "valid": True,
            "type": "wallet_topup",
            "event_id": None,
            "user_id": user_id,
            "amount_tickets": amount_tickets,
            "idempotency_key": nonce,
            "reason": None,
            "data": {
                "deep_link": trimmed,
            },
        }

    params = parse_qs(parsed.query)

    if qr_type == "polymarket":
        raw_bet_id = (params.get("bet_id") or [None])[0]
        try:
            bet_id = int(raw_bet_id) if raw_bet_id is not None else None
        except (TypeError, ValueError):
            bet_id = None
        if bet_id is None:
            return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}
        return {
            "valid": True,
            "type": "polymarket_bet",
            "event_id": None,
            "bet_id": bet_id,
            "scope": None,
            "route_front": f"/polymarket/bets/{bet_id}",
            "reason": None,
            "data": {
                "deep_link": trimmed,
            },
        }

    if qr_type == "menu":
        raw_bar_id = (params.get("bar_id") or [None])[0]
        raw_item_id = (params.get("item_id") or [None])[0]
        raw_category_id = (params.get("category_id") or [None])[0]
        try:
            bar_id = int(raw_bar_id) if raw_bar_id is not None else None
            item_id = int(raw_item_id) if raw_item_id is not None else None
            category_id = int(raw_category_id) if raw_category_id is not None else None
        except (TypeError, ValueError):
            return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}
        if bar_id is None:
            return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}
        route_front = f"/menu/{bar_id}"
        if item_id is not None:
            route_front = f"/menu/{bar_id}/item/{item_id}"
        return {
            "valid": True,
            "type": "menu",
            "event_id": None,
            "bar_id": bar_id,
            "item_id": item_id,
            "category_id": category_id,
            "route_front": route_front,
            "reason": None,
            "data": {
                "deep_link": trimmed,
            },
        }

    if qr_type == "market":
        raw_bar_id = (params.get("bar_id") or [None])[0]
        raw_event_id = (params.get("event_id") or [None])[0]
        try:
            bar_id = int(raw_bar_id) if raw_bar_id is not None else None
            event_id = int(raw_event_id) if raw_event_id is not None else None
        except (TypeError, ValueError):
            return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}
        if bar_id is None:
            return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}
        route_front = f"/market/{bar_id}"
        if event_id is not None:
            route_front = f"/market/{bar_id}?event_id={event_id}"
        return {
            "valid": True,
            "type": "market",
            "event_id": event_id,
            "bar_id": bar_id,
            "route_front": route_front,
            "reason": None,
            "data": {
                "deep_link": trimmed,
            },
        }


    if qr_type == "battle":
        raw_battle_id = (params.get("battle_id") or [None])[0]
        try:
            battle_id = int(raw_battle_id) if raw_battle_id is not None else None
        except (TypeError, ValueError):
            battle_id = None
        if battle_id is None:
            return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}
        return {
            "valid": True,
            "type": "battle",
            "event_id": None,
            "battle_id": battle_id,
            "route_front": f"/battles/{battle_id}",
            "reason": None,
            "data": {
                "deep_link": trimmed,
            },
        }

    if qr_type == "order":
        raw_order_id = (params.get("order_id") or [None])[0]
        try:
            order_id = int(raw_order_id) if raw_order_id is not None else None
        except (TypeError, ValueError):
            order_id = None
        if order_id is None:
            return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}
        return {
            "valid": True,
            "type": "order",
            "event_id": None,
            "order_id": order_id,
            "route_front": f"/orders/{order_id}",
            "reason": None,
            "data": {
                "deep_link": trimmed,
            },
        }

    # Roadmap extensions: expose contract + routing, backend handlers can remain modular.
    route_map = {
        "event": "/events/{event_id}",
        "payment": "/wallet",
        "paiement": "/wallet",
        "hunt": "/hunt",
        "gift": "/wallet/gift",
        "wifi": "/wifi",
        "safety": "/safety",
        "checkins": "/checkins",
        "staff": None,
    }
    if qr_type in route_map:
        raw_event_id = (params.get("event_id") or [None])[0]
        event_id = None
        if raw_event_id is not None:
            try:
                event_id = int(raw_event_id)
            except (TypeError, ValueError):
                return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}
        route = route_map[qr_type]
        if route and "{event_id}" in route:
            if event_id is None:
                return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}
            route = route.format(event_id=event_id)
        return {
            "valid": True,
            "type": qr_type,
            "event_id": event_id,
            "route_front": route,
            "reason": None,
            "data": {
                "deep_link": trimmed,
            },
        }

    if qr_type not in {"join", "entry", "admin_config", "staff_entry", "staff_invite"}:
        return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}

    raw_event_id = (params.get("event_id") or [None])[0]
    try:
        event_id = int(raw_event_id) if raw_event_id is not None else None
    except (TypeError, ValueError):
        event_id = None

    if event_id is None:
        return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}

    token = None
    if qr_type == "staff_invite":
        token = (params.get("token") or [None])[0]
        if not token:
            return {"valid": False, "type": "unknown", "event_id": None, "reason": "invalid"}

    return {
        "valid": True,
        "type": qr_type,
        "event_id": event_id,
        "bar_id": None,
        "item_id": None,
        "category_id": None,
        "route_front": None,
        "token": token,
        "reason": None,
        "data": {
            "deep_link": trimmed,
        },
    }
