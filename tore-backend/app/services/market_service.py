from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db import now_utc
from models import (
    DrinkMarketConfig,
    DrinkMarketItem,
    DrinkPriceTick,
    DrinkPriceTickIdempotency,
    Event,
    Order,
)


def require_market_manager(identity: dict[str, Any]) -> None:
    if (identity.get("role") or "").lower() != "manager":
        raise HTTPException(status_code=403, detail="Forbidden")


def require_market_staff(identity: dict[str, Any]) -> None:
    role = (identity.get("role") or "").lower()
    if role not in {"manager", "staff", "bartender"}:
        raise HTTPException(status_code=403, detail="Forbidden")


def _scope_filter(event_id: Optional[int]):
    if event_id is None:
        return DrinkMarketConfig.event_id.is_(None)
    return DrinkMarketConfig.event_id == event_id


def _ensure_event_belongs_to_bar(s: Session, event_id: Optional[int], bar_id: int) -> None:
    if event_id is None:
        return
    event = s.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.bar_id != bar_id:
        raise HTTPException(status_code=403, detail="Forbidden")


def get_config_for_scope(s: Session, *, bar_id: int, event_id: Optional[int]) -> DrinkMarketConfig:
    config = (
        s.query(DrinkMarketConfig)
        .filter(DrinkMarketConfig.bar_id == bar_id)
        .filter(_scope_filter(event_id))
        .first()
    )
    if not config:
        raise HTTPException(status_code=404, detail="Market config not found")
    return config


def get_item_in_bar_scope(s: Session, *, item_id: int, bar_id: int) -> DrinkMarketItem:
    item = (
        s.query(DrinkMarketItem)
        .join(DrinkMarketConfig, DrinkMarketConfig.id == DrinkMarketItem.config_id)
        .filter(DrinkMarketItem.id == item_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Market item not found")
    config = s.get(DrinkMarketConfig, item.config_id)
    if not config or config.bar_id != bar_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return item


def normalize_price(price_cents: int, config: DrinkMarketConfig) -> int:
    clamped = max(config.price_floor_cents, min(config.price_cap_cents, price_cents))
    step = max(config.step_cents, 1)
    offset = clamped - config.price_floor_cents
    return config.price_floor_cents + int(round(offset / step)) * step


def upsert_config(
    s: Session,
    *,
    bar_id: int,
    event_id: Optional[int],
    is_live: Optional[bool],
    ticket_value_cents: Optional[int],
    price_floor_cents: Optional[int],
    price_cap_cents: Optional[int],
    step_cents: Optional[int],
) -> DrinkMarketConfig:
    _ensure_event_belongs_to_bar(s, event_id, bar_id)

    config = (
        s.query(DrinkMarketConfig)
        .filter(DrinkMarketConfig.bar_id == bar_id)
        .filter(_scope_filter(event_id))
        .first()
    )
    if not config:
        config = DrinkMarketConfig(
            bar_id=bar_id,
            event_id=event_id,
            is_live=is_live if is_live is not None else False,
            ticket_value_cents=ticket_value_cents,
            price_floor_cents=price_floor_cents if price_floor_cents is not None else 50,
            price_cap_cents=price_cap_cents if price_cap_cents is not None else 2000,
            step_cents=step_cents if step_cents is not None else 10,
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        s.add(config)
    else:
        if is_live is not None:
            config.is_live = is_live
        if ticket_value_cents is not None:
            config.ticket_value_cents = ticket_value_cents
        if price_floor_cents is not None:
            config.price_floor_cents = price_floor_cents
        if price_cap_cents is not None:
            config.price_cap_cents = price_cap_cents
        if step_cents is not None:
            config.step_cents = step_cents
        config.updated_at = now_utc()

    if config.price_floor_cents > config.price_cap_cents:
        raise HTTPException(status_code=400, detail="price_floor_cents must be <= price_cap_cents")

    s.commit()
    s.refresh(config)
    return config


def create_item(
    s: Session,
    *,
    bar_id: int,
    event_id: Optional[int],
    name: str,
    base_price_cents: int,
    unit: str,
    sort_order: int,
    actor_user_id: Optional[int],
) -> DrinkMarketItem:
    config = get_config_for_scope(s, bar_id=bar_id, event_id=event_id)
    price = normalize_price(base_price_cents, config)
    item = DrinkMarketItem(
        config_id=config.id,
        name=name.strip(),
        is_active=True,
        base_price_cents=base_price_cents,
        current_price_cents=price,
        unit=unit,
        sort_order=sort_order,
    )
    s.add(item)
    s.flush()
    tick = DrinkPriceTick(
        item_id=item.id,
        price_cents=item.current_price_cents,
        ts=now_utc(),
        source="manual",
        actor_user_id=actor_user_id,
    )
    s.add(tick)
    config.updated_at = now_utc()
    s.commit()
    s.refresh(item)
    return item


def update_item(s: Session, *, item: DrinkMarketItem, **patch: Any) -> DrinkMarketItem:
    for key, value in patch.items():
        if value is not None:
            setattr(item, key, value)
    config = s.get(DrinkMarketConfig, item.config_id)
    if config:
        config.updated_at = now_utc()
    s.commit()
    s.refresh(item)
    return item


def set_item_price(
    s: Session,
    *,
    item: DrinkMarketItem,
    price_cents: int,
    actor_user_id: Optional[int],
    idempotency_key: Optional[str],
) -> tuple[DrinkMarketItem, DrinkPriceTick]:
    config = s.get(DrinkMarketConfig, item.config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Market config not found")

    if idempotency_key:
        idem = (
            s.query(DrinkPriceTickIdempotency)
            .filter(
                DrinkPriceTickIdempotency.item_id == item.id,
                DrinkPriceTickIdempotency.idempotency_key == idempotency_key,
            )
            .first()
        )
        if idem:
            tick = s.get(DrinkPriceTick, idem.tick_id)
            if not tick:
                raise HTTPException(status_code=409, detail="Invalid idempotency state")
            return item, tick

    normalized_price = normalize_price(price_cents, config)
    item.current_price_cents = normalized_price
    tick = DrinkPriceTick(
        item_id=item.id,
        price_cents=normalized_price,
        ts=now_utc(),
        source="manual",
        actor_user_id=actor_user_id,
    )
    s.add(tick)
    s.flush()

    if idempotency_key:
        s.add(
            DrinkPriceTickIdempotency(
                item_id=item.id,
                idempotency_key=idempotency_key,
                tick_id=tick.id,
                created_at=now_utc(),
            )
        )
    config.updated_at = now_utc()
    try:
        s.commit()
    except IntegrityError:
        s.rollback()
        idem = (
            s.query(DrinkPriceTickIdempotency)
            .filter(
                DrinkPriceTickIdempotency.item_id == item.id,
                DrinkPriceTickIdempotency.idempotency_key == idempotency_key,
            )
            .first()
        )
        if not idem:
            raise
        existing_tick = s.get(DrinkPriceTick, idem.tick_id)
        if not existing_tick:
            raise HTTPException(status_code=409, detail="Invalid idempotency state")
        item = s.get(DrinkMarketItem, item.id)
        if not item:
            raise HTTPException(status_code=404, detail="Market item not found")
        return item, existing_tick

    s.refresh(item)
    s.refresh(tick)
    return item, tick




def apply_order_market_impact(s: Session, *, order: Order) -> int:
    config = (
        s.query(DrinkMarketConfig)
        .filter(DrinkMarketConfig.bar_id == order.bar_id)
        .filter(_scope_filter(order.event_id))
        .first()
    )
    if not config or not config.is_live:
        return 0

    impacted = 0
    for line in order.items:
        item = None
        if line.market_item_id is not None:
            direct_item = s.get(DrinkMarketItem, line.market_item_id)
            if (
                direct_item
                and direct_item.config_id == config.id
                and direct_item.is_active
                and direct_item.name == line.name_snapshot
            ):
                item = direct_item
            else:
                continue
        else:
            item = (
                s.query(DrinkMarketItem)
                .filter(
                    DrinkMarketItem.config_id == config.id,
                    DrinkMarketItem.is_active.is_(True),
                    DrinkMarketItem.name == line.name_snapshot,
                )
                .first()
            )
        if not item:
            continue
        next_price = normalize_price(item.current_price_cents + config.step_cents, config)
        item.current_price_cents = next_price
        s.add(
            DrinkPriceTick(
                item_id=item.id,
                price_cents=next_price,
                ts=now_utc(),
                source="order",
                actor_user_id=None,
                ref_order_id=order.id,
            )
        )
        impacted += 1

    if impacted > 0:
        config.updated_at = now_utc()
    return impacted

def list_scope_items(s: Session, *, config_id: int) -> list[DrinkMarketItem]:
    return (
        s.query(DrinkMarketItem)
        .filter(DrinkMarketItem.config_id == config_id)
        .order_by(DrinkMarketItem.sort_order.asc(), DrinkMarketItem.id.asc())
        .all()
    )


def list_public_ticker(s: Session, *, config_id: int, limit: int = 30) -> list[DrinkPriceTick]:
    return (
        s.query(DrinkPriceTick)
        .join(DrinkMarketItem, DrinkMarketItem.id == DrinkPriceTick.item_id)
        .filter(DrinkMarketItem.config_id == config_id)
        .order_by(DrinkPriceTick.ts.desc(), DrinkPriceTick.id.desc())
        .limit(limit)
        .all()
    )
