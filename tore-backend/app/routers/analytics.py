from __future__ import annotations

import csv
import io
from datetime import timedelta
from typing import Iterator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from db import now_utc
from models import Bet, BetPosition, Event, MenuItem, MenuTrackEvent, Order, WalletTx
from partner_auth import require_role

router = APIRouter(prefix="/partner/portal/analytics", tags=["partner-analytics"])


def _analytics_base_filters(
    db: Session,
    bar_id: int,
    event_id: Optional[int],
    days: int,
) -> tuple[Optional[int], object]:
    if days < 1 or days > 90:
        raise HTTPException(422, "days must be between 1 and 90")

    if event_id is not None:
        owned_event = db.query(Event.id).filter(Event.id == event_id, Event.bar_id == bar_id).first()
        if not owned_event:
            raise HTTPException(403, "Forbidden")

    since = now_utc() - timedelta(days=days)
    return event_id, since


def get_db() -> Iterator[Session]:
    from main import get_db as _get_db

    yield from _get_db()


@router.get("/summary")
def partner_portal_analytics_summary(
    event_id: Optional[int] = Query(default=None),
    days: int = Query(default=7),
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    bar_id = identity["bar_id"]
    scoped_event_id, since = _analytics_base_filters(db, bar_id=bar_id, event_id=event_id, days=days)

    order_filters = [Order.bar_id == bar_id, Order.created_at >= since]
    if scoped_event_id is not None:
        order_filters.append(Order.event_id == scoped_event_id)

    order_agg = (
        db.query(
            func.count(Order.id),
            func.coalesce(func.sum(Order.total_cents), 0),
            func.coalesce(func.sum(case((Order.payment_status == "PAID", 1), else_=0)), 0),
            func.coalesce(func.sum(case((Order.payment_status != "PAID", 1), else_=0)), 0),
            func.coalesce(func.sum(case((Order.payment_status == "PAID", Order.total_tickets), else_=0)), 0),
        )
        .filter(*order_filters)
        .one()
    )

    menu_filters = [MenuTrackEvent.bar_id == bar_id, MenuTrackEvent.created_at >= since]
    if scoped_event_id is not None:
        menu_filters.append(MenuTrackEvent.event_id == scoped_event_id)

    menu_rows = (
        db.query(
            MenuTrackEvent.item_id,
            MenuItem.name,
            func.coalesce(func.sum(case((MenuTrackEvent.action == "view", 1), else_=0)), 0).label("views"),
            func.coalesce(
                func.sum(case((MenuTrackEvent.action.in_(["add", "add_to_cart"]), 1), else_=0)),
                0,
            ).label("adds"),
        )
        .outerjoin(MenuItem, MenuItem.id == MenuTrackEvent.item_id)
        .filter(*menu_filters)
        .group_by(MenuTrackEvent.item_id, MenuItem.name)
        .order_by(func.coalesce(func.sum(case((MenuTrackEvent.action.in_(["add", "add_to_cart"]), 1), else_=0)), 0).desc())
        .limit(10)
        .all()
    )

    menu_totals = (
        db.query(
            func.coalesce(func.sum(case((MenuTrackEvent.action == "view", 1), else_=0)), 0),
            func.coalesce(func.sum(case((MenuTrackEvent.action.in_(["add", "add_to_cart"]), 1), else_=0)), 0),
        )
        .filter(*menu_filters)
        .one()
    )

    bet_filters = [Event.bar_id == bar_id, Bet.created_at >= since]
    if scoped_event_id is not None:
        bet_filters.append(Bet.event_id == scoped_event_id)

    polymarket_counts = (
        db.query(
            func.coalesce(func.sum(case((Bet.status == "LIVE", 1), else_=0)), 0),
            func.coalesce(func.sum(case((Bet.status == "PENDING", 1), else_=0)), 0),
            func.coalesce(func.sum(case((Bet.status == "FINALIZED", 1), else_=0)), 0),
        )
        .join(Event, Event.id == Bet.event_id)
        .filter(*bet_filters)
        .one()
    )

    stake_query = (
        db.query(func.coalesce(func.sum(BetPosition.stake_tickets), 0))
        .join(Bet, Bet.id == BetPosition.bet_id)
        .join(Event, Event.id == Bet.event_id)
        .filter(*bet_filters)
    )
    payout_filters = [WalletTx.kind == "BET_PAYOUT", WalletTx.created_at >= since]

    # Portable payout aggregation: BET_PAYOUT rows are scoped by bet id in ref_id (<bet_id>:<user_id>).
    payout_total = 0
    payout_rows = (
        db.query(WalletTx.amount_tickets, WalletTx.ref_id)
        .filter(*payout_filters)
        .all()
    )
    if payout_rows:
        allowed_bet_ids = {
            bet_id
            for (bet_id,) in db.query(Bet.id).join(Event, Event.id == Bet.event_id).filter(*bet_filters).all()
        }
        for amount, ref_id in payout_rows:
            if not ref_id:
                continue
            bet_token = str(ref_id).split(":", 1)[0]
            if not bet_token.isdigit():
                continue
            if int(bet_token) in allowed_bet_ids:
                payout_total += int(amount or 0)

    return {
        "orders": {
            "count": int(order_agg[0] or 0),
            "total_cents": int(order_agg[1] or 0),
            "paid_count": int(order_agg[2] or 0),
            "unpaid_count": int(order_agg[3] or 0),
            "paid_tickets_total": int(order_agg[4] or 0),
        },
        "menu": {
            "top_items": [
                {
                    "item_id": row[0],
                    "name": row[1] or "Unknown",
                    "views": int(row[2] or 0),
                    "adds": int(row[3] or 0),
                }
                for row in menu_rows
            ],
            "totals": {
                "views": int(menu_totals[0] or 0),
                "adds": int(menu_totals[1] or 0),
            },
        },
        "polymarket": {
            "bets_live": int(polymarket_counts[0] or 0),
            "bets_pending": int(polymarket_counts[1] or 0),
            "bets_finalized": int(polymarket_counts[2] or 0),
            "total_staked_tickets": int(stake_query.scalar() or 0),
            "total_payout_tickets": int(payout_total),
        },
    }


@router.get("/orders.csv")
def partner_portal_analytics_orders_csv(
    event_id: Optional[int] = Query(default=None),
    days: int = Query(default=7),
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    bar_id = identity["bar_id"]
    scoped_event_id, since = _analytics_base_filters(db, bar_id=bar_id, event_id=event_id, days=days)

    query = db.query(
        Order.id,
        Order.created_at,
        Order.event_id,
        Order.status,
        Order.payment_status,
        Order.total_cents,
        Order.total_tickets,
    ).filter(Order.bar_id == bar_id, Order.created_at >= since)
    if scoped_event_id is not None:
        query = query.filter(Order.event_id == scoped_event_id)

    rows = query.order_by(Order.created_at.desc()).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["order_id", "created_at", "event_id", "status", "payment_status", "total_cents", "total_tickets"])
    for row in rows:
        writer.writerow([row[0], row[1].isoformat() if row[1] else "", row[2], row[3], row[4], row[5], row[6]])
    buffer.seek(0)

    filename = f"orders-{bar_id}-{days}d.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/menu-tracking.csv")
def partner_portal_analytics_menu_tracking_csv(
    event_id: Optional[int] = Query(default=None),
    days: int = Query(default=7),
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    bar_id = identity["bar_id"]
    scoped_event_id, since = _analytics_base_filters(db, bar_id=bar_id, event_id=event_id, days=days)
    filters = [MenuTrackEvent.bar_id == bar_id, MenuTrackEvent.created_at >= since]
    if scoped_event_id is not None:
        filters.append(MenuTrackEvent.event_id == scoped_event_id)

    rows = (
        db.query(MenuTrackEvent.created_at, MenuTrackEvent.event_id, MenuTrackEvent.item_id, MenuTrackEvent.action, MenuTrackEvent.device_id)
        .filter(*filters)
        .order_by(MenuTrackEvent.created_at.desc(), MenuTrackEvent.id.desc())
        .limit(5000)
        .all()
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["created_at", "event_id", "item_id", "action", "device_id"])
    for row in rows:
        writer.writerow([row[0].isoformat() if row[0] else "", row[1], row[2], row[3], row[4] or ""])
    buffer.seek(0)
    filename = f"menu-tracking-{bar_id}-{days}d.csv"
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
