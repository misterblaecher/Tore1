#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import timedelta

from sqlalchemy import select

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "tore-backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db import get_session, now_utc
from models import (
    AppToken,
    AppUser,
    Bar,
    EntryToken,
    Event,
    EventModuleConfig,
    MenuCategory,
    MenuItem,
    PartnerMembership,
    PartnerUser,
    Zone,
)
from partner_auth import _hash_pin, _make_token


def _sha256(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def main() -> None:
    s = get_session()
    try:
        bar = s.execute(select(Bar).where(Bar.partner_code == "TORE_RELEASE_BAR")).scalar_one_or_none()
        if not bar:
            bar = Bar(name="TORÈ Release Bar", city="Liège", partner_code="TORE_RELEASE_BAR")
            s.add(bar)
            s.flush()

        event = (
            s.execute(select(Event).where(Event.bar_id == bar.id, Event.name == "TORÈ Release Event"))
            .scalar_one_or_none()
        )
        if not event:
            event = Event(
                bar_id=bar.id,
                name="TORÈ Release Event",
                starts_at=now_utc(),
                ends_at=now_utc() + timedelta(hours=8),
                entry_price_cents=0,
                ticket_mode=True,
                ticket_value_cents=200,
            )
            s.add(event)
            s.flush()

        zone = (
            s.execute(select(Zone).where(Zone.bar_id == bar.id, Zone.slug == "main-floor"))
            .scalar_one_or_none()
        )
        if not zone:
            zone = Zone(bar_id=bar.id, event_id=event.id, name="Main Floor", slug="main-floor", enabled=True)
            s.add(zone)

        category = (
            s.execute(select(MenuCategory).where(MenuCategory.bar_id == bar.id, MenuCategory.name == "Signature"))
            .scalar_one_or_none()
        )
        if not category:
            category = MenuCategory(bar_id=bar.id, name="Signature", sort_order=1, is_active=True)
            s.add(category)
            s.flush()

        item = (
            s.execute(select(MenuItem).where(MenuItem.bar_id == bar.id, MenuItem.name == "Release Spritz"))
            .scalar_one_or_none()
        )
        if not item:
            item = MenuItem(
                bar_id=bar.id,
                category_id=category.id,
                name="Release Spritz",
                description="Seed item for smoke checks",
                price_cents=450,
                is_active=True,
                is_available=True,
            )
            s.add(item)

        app_user = s.execute(select(AppUser).where(AppUser.display_name == "release-user")).scalar_one_or_none()
        app_token_raw = secrets.token_urlsafe(24)
        if not app_user:
            app_user = AppUser(id=secrets.token_hex(16), display_name="release-user")
            s.add(app_user)
            s.flush()

        app_token = AppToken(user_id=app_user.id, token_hash=_sha256(app_token_raw))
        s.add(app_token)

        partner_user = s.execute(select(PartnerUser).where(PartnerUser.display_name == "release-staff")).scalar_one_or_none()
        if not partner_user:
            partner_user = PartnerUser(display_name="release-staff", pin_hash=_hash_pin("1234"), is_active=True)
            s.add(partner_user)
            s.flush()

        membership = (
            s.execute(
                select(PartnerMembership).where(
                    PartnerMembership.user_id == partner_user.id,
                    PartnerMembership.bar_id == bar.id,
                )
            ).scalar_one_or_none()
        )
        if not membership:
            membership = PartnerMembership(
                user_id=partner_user.id,
                bar_id=bar.id,
                role="manager",
                display_name="release-staff",
            )
            s.add(membership)

        cfg = s.execute(select(EventModuleConfig).where(EventModuleConfig.event_id == event.id)).scalar_one_or_none()
        if not cfg:
            cfg = EventModuleConfig(event_id=event.id, orders_enabled=True, entry_enabled=True)
            s.add(cfg)

        for _ in range(3):
            s.add(
                EntryToken(
                    event_id=event.id,
                    token_hash=_sha256(secrets.token_urlsafe(16)),
                    expires_at=now_utc() + timedelta(hours=12),
                    status="ACTIVE",
                )
            )

        s.commit()

        partner_token = _make_token(partner_user.id, bar.id, "manager", partner_user.display_name)
        payload = {
            "bar_id": bar.id,
            "event_id": event.id,
            "zone_id": zone.id,
            "item_id": item.id,
            "app_user_id": app_user.id,
            "app_user_token": app_token_raw,
            "partner_user_id": partner_user.id,
            "partner_token": partner_token,
            "partner_pin": "1234",
        }
        print(json.dumps(payload, ensure_ascii=False))
    finally:
        s.close()


if __name__ == "__main__":
    main()
