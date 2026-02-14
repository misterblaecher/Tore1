from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Iterator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.schemas.market import (
    DrinkMarketConfigOut,
    DrinkMarketItemOut,
    MarketConfigUpsertIn,
    MarketItemCreateIn,
    MarketItemHistoryOut,
    MarketItemPatchIn,
    MarketPublicOut,
    MarketSetPriceIn,
    MarketSetPriceOut,
)
from app.services.market_service import (
    create_item,
    get_config_for_scope,
    get_item_in_bar_scope,
    list_public_ticker,
    list_scope_items,
    require_market_manager,
    require_market_staff,
    set_item_price,
    update_item,
    upsert_config,
)
from db import get_session
from models import DrinkMarketItem, DrinkPriceTick
from partner_auth import current_identity as current_partner_identity

router = APIRouter(tags=["market"])


def get_db() -> Iterator[Session]:
    from main import get_db as _get_db

    yield from _get_db()


@router.get("/market/public", response_model=MarketPublicOut)
def market_public(
    bar_id: int = Query(...),
    event_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    config = get_config_for_scope(db, bar_id=bar_id, event_id=event_id)
    items = list_scope_items(db, config_id=config.id)
    ticker = list_public_ticker(db, config_id=config.id, limit=30)
    return {"config": config, "items": items, "ticker": ticker}


@router.get("/market/public/stream")
async def market_public_stream(
    request: Request,
    bar_id: int = Query(...),
    event_id: Optional[int] = Query(default=None),
    once: bool = Query(default=False),
):
    session = get_session()
    try:
        config = get_config_for_scope(session, bar_id=bar_id, event_id=event_id)
        if not config.is_live:
            return Response(status_code=204)
        item_ids = [item.id for item in list_scope_items(session, config_id=config.id)]
    finally:
        session.close()

    if not item_ids:
        return Response(status_code=204)

    async def stream_events():
        last_ts = datetime.min
        try:
            while True:
                if await request.is_disconnected():
                    break

                loop_session = get_session()
                try:
                    ticks = (
                        loop_session.query(DrinkPriceTick)
                        .filter(DrinkPriceTick.item_id.in_(item_ids), DrinkPriceTick.ts > last_ts)
                        .order_by(DrinkPriceTick.ts.asc(), DrinkPriceTick.id.asc())
                        .limit(50)
                        .all()
                    )
                finally:
                    loop_session.close()

                for tick in ticks:
                    payload = {
                        "item_id": tick.item_id,
                        "price_cents": tick.price_cents,
                        "ts": tick.ts.isoformat(),
                        "source": tick.source,
                    }
                    if tick.ref_order_id is not None:
                        payload["ref_order_id"] = tick.ref_order_id
                    yield f"event: tick\ndata: {json.dumps(payload)}\n\n"
                    last_ts = tick.ts

                if not ticks:
                    yield ": keepalive\n\n"
                if once:
                    break
                await asyncio.sleep(1)
        except GeneratorExit:
            return

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/market/public/items/{item_id}", response_model=MarketItemHistoryOut)
def market_public_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(DrinkMarketItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Market item not found")
    history = (
        db.query(DrinkPriceTick)
        .filter(DrinkPriceTick.item_id == item.id)
        .order_by(DrinkPriceTick.ts.asc(), DrinkPriceTick.id.asc())
        .limit(200)
        .all()
    )
    return {"item": item, "history": history}


@router.post("/partner/portal/market/config", response_model=DrinkMarketConfigOut)
def partner_market_upsert_config(
    payload: MarketConfigUpsertIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_market_manager(identity)
    return upsert_config(
        db,
        bar_id=identity["bar_id"],
        event_id=payload.event_id,
        is_live=payload.is_live,
        ticket_value_cents=payload.ticket_value_cents,
        price_floor_cents=payload.price_floor_cents,
        price_cap_cents=payload.price_cap_cents,
        step_cents=payload.step_cents,
    )


@router.get("/partner/portal/market/config", response_model=DrinkMarketConfigOut)
def partner_market_get_config(
    event_id: Optional[int] = Query(default=None),
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_market_staff(identity)
    return get_config_for_scope(db, bar_id=identity["bar_id"], event_id=event_id)


@router.post("/partner/portal/market/items", response_model=DrinkMarketItemOut)
def partner_market_create_item(
    payload: MarketItemCreateIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_market_manager(identity)
    return create_item(
        db,
        bar_id=identity["bar_id"],
        event_id=payload.event_id,
        name=payload.name,
        base_price_cents=payload.base_price_cents,
        unit=payload.unit,
        sort_order=payload.sort_order,
        actor_user_id=identity.get("user_id"),
    )


@router.get("/partner/portal/market/items", response_model=list[DrinkMarketItemOut])
def partner_market_items(
    event_id: Optional[int] = Query(default=None),
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_market_staff(identity)
    config = get_config_for_scope(db, bar_id=identity["bar_id"], event_id=event_id)
    return list_scope_items(db, config_id=config.id)


@router.patch("/partner/portal/market/items/{item_id}", response_model=DrinkMarketItemOut)
def partner_market_patch_item(
    item_id: int,
    payload: MarketItemPatchIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_market_manager(identity)
    item = get_item_in_bar_scope(db, item_id=item_id, bar_id=identity["bar_id"])
    return update_item(
        db,
        item=item,
        name=payload.name,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
        base_price_cents=payload.base_price_cents,
    )


@router.post("/partner/portal/market/items/{item_id}/price", response_model=MarketSetPriceOut)
def partner_market_set_price(
    item_id: int,
    payload: MarketSetPriceIn,
    identity=Depends(current_partner_identity),
    db: Session = Depends(get_db),
):
    require_market_staff(identity)
    item = get_item_in_bar_scope(db, item_id=item_id, bar_id=identity["bar_id"])
    item, tick = set_item_price(
        db,
        item=item,
        price_cents=payload.price_cents,
        actor_user_id=identity.get("user_id"),
        idempotency_key=payload.idempotency_key,
    )
    return {"item": item, "tick": tick}
