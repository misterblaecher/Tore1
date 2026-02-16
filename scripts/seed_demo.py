#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import secrets
import sys
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1] / "tore-backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.qr_pack_service import create_staff_qr_token, create_wifi_token_qr, generate_qr_pack
from db import get_session, now_utc
from models import (
    AppToken,
    AppUser,
    Bar,
    Committee,
    CommitteeMembership,
    CommitteeYear,
    Event,
    EventModuleConfig,
    EventQrToken,
    EventStaffAssignment,
    EventWifiSettings,
    MenuCategory,
    MenuItem,
    PartnerMembership,
    PartnerUser,
)
from partner_auth import _hash_pin, _make_token


def _sha256(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _mask(secret: str, keep: int = 6) -> str:
    if len(secret) <= keep:
        return "*" * len(secret)
    return f"{secret[:keep]}...{len(secret)}c"


def _get_or_create_partner_user(session, *, display_name: str, pin: str) -> PartnerUser:
    row = session.execute(select(PartnerUser).where(PartnerUser.display_name == display_name)).scalar_one_or_none()
    if row:
        return row
    row = PartnerUser(display_name=display_name, pin_hash=_hash_pin(pin), is_active=True)
    session.add(row)
    session.flush()
    return row


def _get_or_create_membership(session, *, user_id: int, bar_id: int, role: str, display_name: str) -> PartnerMembership:
    row = (
        session.execute(
            select(PartnerMembership).where(
                PartnerMembership.user_id == user_id,
                PartnerMembership.bar_id == bar_id,
            )
        )
        .scalar_one_or_none()
    )
    if row:
        return row
    row = PartnerMembership(user_id=user_id, bar_id=bar_id, role=role, display_name=display_name)
    session.add(row)
    session.flush()
    return row


def _get_or_create_staff_assignment(session, *, event_id: int, role: str, label: str, created_by_user_id: int) -> EventStaffAssignment:
    row = (
        session.execute(
            select(EventStaffAssignment).where(
                EventStaffAssignment.event_id == event_id,
                EventStaffAssignment.role == role,
                EventStaffAssignment.label == label,
                EventStaffAssignment.revoked_at.is_(None),
            )
        )
        .scalar_one_or_none()
    )
    if row:
        return row
    row = EventStaffAssignment(
        event_id=event_id,
        role=role,
        label=label,
        created_by_user_id=created_by_user_id,
    )
    session.add(row)
    session.flush()
    return row


def _latest_active_qr(session, *, event_id: int, qr_type: str, role: str | None = None, assignment_id: int | None = None) -> EventQrToken | None:
    q = session.query(EventQrToken).filter(
        EventQrToken.event_id == event_id,
        EventQrToken.qr_type == qr_type,
        EventQrToken.revoked_at.is_(None),
        EventQrToken.expires_at > now_utc(),
    )
    if role:
        q = q.filter(EventQrToken.role == role)
    if assignment_id is not None:
        q = q.filter(EventQrToken.assignment_id == assignment_id)
    return q.order_by(EventQrToken.issued_at.desc()).first()


def main() -> None:
    session = get_session()
    try:
        # Bar + event demo
        bar = session.execute(select(Bar).where(Bar.partner_code == "TORE_DEMO_BAR")).scalar_one_or_none()
        if not bar:
            bar = Bar(name="TORÈ Demo Chapi", city="Liège", partner_code="TORE_DEMO_BAR")
            session.add(bar)
            session.flush()

        event = (
            session.execute(select(Event).where(Event.bar_id == bar.id, Event.name == "TORÈ Demo Event LIVE"))
            .scalar_one_or_none()
        )
        modules_on = {
            "menu": True,
            "wallet": True,
            "ticker": True,
            "broadcast": True,
            "music": True,
            "battles": True,
            "hunt": True,
            "wifi": True,
            "safety": True,
            "map": True,
            "entry": True,
            "polymarket_event": True,
            "classement": True,
            "committee_os": True,
            "folklore_glossary": True,
        }

        if not event:
            event = Event(
                bar_id=bar.id,
                name="TORÈ Demo Event LIVE",
                starts_at=now_utc() - timedelta(minutes=20),
                ends_at=now_utc() + timedelta(hours=8),
                event_state="LIVE",
                timezone="Europe/Brussels",
                venue="Chapi Demo",
                modules_on=modules_on,
                rules_flags={"charter_enabled": True, "require_charter_accept": True},
                created_by="seed_demo.py",
                entry_price_cents=0,
                ticket_mode=True,
                ticket_value_cents=200,
            )
            session.add(event)
            session.flush()
        else:
            event.modules_on = {**(event.modules_on or {}), **modules_on}
            event.event_state = "LIVE"
            event.last_updated_at = now_utc()
            session.add(event)

        mod_cfg = session.execute(select(EventModuleConfig).where(EventModuleConfig.event_id == event.id)).scalar_one_or_none()
        if not mod_cfg:
            mod_cfg = EventModuleConfig(event_id=event.id)
        mod_cfg.orders_enabled = True
        mod_cfg.market_enabled = True
        mod_cfg.battles_enabled = True
        mod_cfg.hunt_enabled = True
        mod_cfg.polymarket_enabled = True
        mod_cfg.entry_enabled = True
        mod_cfg.checkins_enabled = True
        mod_cfg.wifi_enabled = True
        mod_cfg.safety_enabled = True
        session.add(mod_cfg)

        wifi = session.execute(select(EventWifiSettings).where(EventWifiSettings.event_id == event.id)).scalar_one_or_none()
        if not wifi:
            wifi = EventWifiSettings(event_id=event.id)
        wifi.enabled = True
        wifi.ssid = "TORE_DEMO_WIFI"
        wifi.password = "demo-change-me"
        wifi.instructions = "Demander à l'orga en cas de souci."
        session.add(wifi)

        # Menu demo
        category = (
            session.execute(
                select(MenuCategory).where(
                    MenuCategory.bar_id == bar.id,
                    MenuCategory.name == "Demo Signature",
                )
            )
            .scalar_one_or_none()
        )
        if not category:
            category = MenuCategory(bar_id=bar.id, name="Demo Signature", sort_order=1, is_active=True)
            session.add(category)
            session.flush()

        menu_specs = [
            ("Demo Mojito", "Menthe, sucre, citron", 550),
            ("Demo Spritz", "Aperol, prosecco, eau", 600),
            ("Demo Soft", "Limonade maison", 250),
        ]
        item_ids: list[int] = []
        for name, description, price_cents in menu_specs:
            item = (
                session.execute(
                    select(MenuItem).where(
                        MenuItem.bar_id == bar.id,
                        MenuItem.name == name,
                    )
                )
                .scalar_one_or_none()
            )
            if not item:
                item = MenuItem(
                    bar_id=bar.id,
                    category_id=category.id,
                    name=name,
                    description=description,
                    price_cents=price_cents,
                    is_active=True,
                    is_available=True,
                )
                session.add(item)
                session.flush()
            item_ids.append(item.id)

        # Committee + year + admin membership
        committee = session.execute(select(Committee).where(Committee.slug == "tore-demo-committee")).scalar_one_or_none()
        if not committee:
            committee = Committee(
                name="TORÈ Demo Committee",
                slug="tore-demo-committee",
                description_public="Comité de démo pour setup Chapi-ready",
            )
            session.add(committee)
            session.flush()

        committee_year = (
            session.execute(
                select(CommitteeYear).where(
                    CommitteeYear.committee_id == committee.id,
                    CommitteeYear.year_label == "2026",
                )
            )
            .scalar_one_or_none()
        )
        if not committee_year:
            committee_year = CommitteeYear(committee_id=committee.id, year_label="2026", is_active=True)
            session.add(committee_year)

        admin_app_user = session.execute(select(AppUser).where(AppUser.display_name == "demo-admin-global")).scalar_one_or_none()
        admin_token_raw = secrets.token_urlsafe(24)
        if not admin_app_user:
            admin_app_user = AppUser(id=secrets.token_hex(16), display_name="demo-admin-global")
            session.add(admin_app_user)
            session.flush()

        app_token = AppToken(user_id=admin_app_user.id, token_hash=_sha256(admin_token_raw))
        session.add(app_token)

        committee_membership = (
            session.execute(
                select(CommitteeMembership).where(
                    CommitteeMembership.committee_id == committee.id,
                    CommitteeMembership.user_id == admin_app_user.id,
                )
            )
            .scalar_one_or_none()
        )
        if not committee_membership:
            committee_membership = CommitteeMembership(
                committee_id=committee.id,
                user_id=admin_app_user.id,
                role="ADMIN",
                is_active=True,
            )
            session.add(committee_membership)

        # Staff demo + memberships
        manager_user = _get_or_create_partner_user(session, display_name="demo-manager", pin="1234")
        entry_user = _get_or_create_partner_user(session, display_name="demo-entry", pin="1234")
        bar_user = _get_or_create_partner_user(session, display_name="demo-bar", pin="1234")
        admin_global_partner = _get_or_create_partner_user(session, display_name="demo-admin-global-partner", pin="1234")

        _get_or_create_membership(session, user_id=manager_user.id, bar_id=bar.id, role="manager", display_name="demo-manager")
        _get_or_create_membership(session, user_id=entry_user.id, bar_id=bar.id, role="bartender", display_name="demo-entry")
        _get_or_create_membership(session, user_id=bar_user.id, bar_id=bar.id, role="bartender", display_name="demo-bar")
        _get_or_create_membership(session, user_id=admin_global_partner.id, bar_id=bar.id, role="manager", display_name="demo-admin-global-partner")

        assign_entry = _get_or_create_staff_assignment(
            session,
            event_id=event.id,
            role="ENTRY",
            label="Gate A",
            created_by_user_id=manager_user.id,
        )
        assign_bar = _get_or_create_staff_assignment(
            session,
            event_id=event.id,
            role="BAR",
            label="Main Bar",
            created_by_user_id=manager_user.id,
        )
        assign_manager = _get_or_create_staff_assignment(
            session,
            event_id=event.id,
            role="MANAGER",
            label="Control Room",
            created_by_user_id=manager_user.id,
        )

        # QR pack and role QR (idempotent)
        join_qr = _latest_active_qr(session, event_id=event.id, qr_type="JOIN_EVENT")
        if not join_qr:
            generate_qr_pack(session, event=event, actor_user_id=manager_user.id)
            join_qr = _latest_active_qr(session, event_id=event.id, qr_type="JOIN_EVENT")

        entry_qr = _latest_active_qr(
            session,
            event_id=event.id,
            qr_type="ENTRY_STAFF",
            role="ENTRY",
            assignment_id=assign_entry.id,
        )
        if not entry_qr:
            create_staff_qr_token(
                session,
                event=event,
                staff_role="ENTRY",
                created_by_user_id=manager_user.id,
                assignment_id=assign_entry.id,
                expires_at=event.ends_at + timedelta(hours=6),
            )
            entry_qr = _latest_active_qr(session, event_id=event.id, qr_type="ENTRY_STAFF", role="ENTRY", assignment_id=assign_entry.id)

        bar_qr = _latest_active_qr(
            session,
            event_id=event.id,
            qr_type="BAR_STAFF",
            role="BAR",
            assignment_id=assign_bar.id,
        )
        if not bar_qr:
            create_staff_qr_token(
                session,
                event=event,
                staff_role="BAR",
                created_by_user_id=manager_user.id,
                assignment_id=assign_bar.id,
                expires_at=event.ends_at + timedelta(hours=6),
            )
            bar_qr = _latest_active_qr(session, event_id=event.id, qr_type="BAR_STAFF", role="BAR", assignment_id=assign_bar.id)

        manager_qr = _latest_active_qr(
            session,
            event_id=event.id,
            qr_type="MANAGER",
            role="MANAGER",
            assignment_id=assign_manager.id,
        )
        if not manager_qr:
            create_staff_qr_token(
                session,
                event=event,
                staff_role="MANAGER",
                created_by_user_id=manager_user.id,
                assignment_id=assign_manager.id,
                expires_at=event.ends_at + timedelta(hours=6),
            )
            manager_qr = _latest_active_qr(session, event_id=event.id, qr_type="MANAGER", role="MANAGER", assignment_id=assign_manager.id)

        wifi_qr = _latest_active_qr(session, event_id=event.id, qr_type="WIFI_TOKEN")
        if not wifi_qr:
            created = create_wifi_token_qr(session, event=event, created_by_user_id=manager_user.id, ttl_seconds=21600)
            wifi_qr_payload = created["payload"]
        else:
            wifi_qr_payload = wifi_qr.payload

        session.commit()

        # tokens (masked)
        manager_partner_token = _make_token(manager_user.id, bar.id, "manager", manager_user.display_name)
        entry_partner_token = _make_token(entry_user.id, bar.id, "bartender", entry_user.display_name)
        bar_partner_token = _make_token(bar_user.id, bar.id, "bartender", bar_user.display_name)
        admin_global_token = _make_token(admin_global_partner.id, bar.id, "ADMIN_GLOBAL", admin_global_partner.display_name)

        payload = {
            "bar": {"id": bar.id, "partnerCode": bar.partner_code},
            "event": {"id": event.id, "name": event.name, "state": event.event_state},
            "committee": {"id": committee.id, "slug": committee.slug, "year": committee_year.year_label},
            "menuItemIds": item_ids,
            "staffAssignments": {
                "entry": assign_entry.id,
                "bar": assign_bar.id,
                "manager": assign_manager.id,
            },
            "qrDeepLinks": {
                "JOIN": join_qr.payload if join_qr else None,
                "ENTRY": entry_qr.payload if entry_qr else None,
                "BAR": bar_qr.payload if bar_qr else None,
                "MANAGER": manager_qr.payload if manager_qr else None,
                "WIFI": wifi_qr_payload,
                "HUNT": f"tore://hunt?event_id={event.id}",
                "BATTLES": f"tore://battle?event_id={event.id}",
            },
            "tokens": {
                "appUserTokenPreview": _mask(admin_token_raw),
                "managerPartnerTokenPreview": _mask(manager_partner_token),
                "entryPartnerTokenPreview": _mask(entry_partner_token),
                "barPartnerTokenPreview": _mask(bar_partner_token),
                "adminGlobalTokenPreview": _mask(admin_global_token),
            },
            "notes": {
                "devPins": {
                    "demo-manager": "1234",
                    "demo-entry": "1234",
                    "demo-bar": "1234",
                    "demo-admin-global-partner": "1234",
                },
                "tokenPolicy": "Tokens are masked in output. Re-generate with partner_auth._make_token for local dev only.",
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    finally:
        session.close()


if __name__ == "__main__":
    main()
