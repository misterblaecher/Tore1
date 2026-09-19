#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import timedelta
from urllib.parse import urlparse

from sqlalchemy import select

from db import get_session, now_utc
from models import Bar, Event, EventRuntimeState

SEED_SOURCE = "seed_local_discovery.py"


def _assert_local_dev_database() -> None:
    env_name = (os.getenv("TORE_ENV") or os.getenv("APP_ENV") or os.getenv("ENV") or "DEV").strip().upper()
    if env_name in {"PROD", "PRODUCTION"}:
        raise RuntimeError("Refus: ce seed est réservé au développement local.")

    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if not database_url or database_url.startswith("sqlite"):
        return

    parsed = urlparse(database_url)
    allowed_hosts = {"postgres", "localhost", "127.0.0.1", "host.docker.internal"}
    if parsed.hostname not in allowed_hosts:
        raise RuntimeError(
            f"Refus: DATABASE_URL ne ressemble pas à une base locale (host={parsed.hostname!r})."
        )


def _upsert_bar(session, spec: dict) -> Bar:
    bar = session.execute(
        select(Bar).where(Bar.partner_code == spec["partner_code"])
    ).scalar_one_or_none()
    if bar is None:
        bar = Bar(partner_code=spec["partner_code"])
        session.add(bar)

    for field, value in spec.items():
        setattr(bar, field, value)
    session.flush()
    return bar


def _upsert_event(session, bar: Bar, spec: dict, *, now) -> Event:
    event = session.execute(
        select(Event).where(Event.event_code == spec["event_code"])
    ).scalar_one_or_none()
    if event is None:
        event = Event(event_code=spec["event_code"])
        session.add(event)

    event.bar_id = bar.id
    event.name = spec["name"]
    event.starts_at = now + spec["starts_delta"]
    event.ends_at = now + spec["ends_delta"]
    event.entry_price_cents = spec["entry_price_cents"]
    event.ticket_mode = True
    event.ticket_value_cents = 200
    event.allow_self_ticket_adjust = True
    event.charter_enabled = spec.get("charter_enabled", False)
    event.charter_version = "demo-v1" if event.charter_enabled else None
    event.charter_text = (
        "Respecte les autres participants, le lieu et les consignes de sécurité."
        if event.charter_enabled
        else None
    )
    event.venue = spec["venue"]
    event.timezone = "Europe/Brussels"
    event.event_state = spec["runtime_state"]
    event.modules_on = {
        "menu": True,
        "entry": True,
        "map": True,
        "safety": True,
        "wifi": False,
        "music": True,
    }
    event.rules_flags = {"demo_seed": True}
    event.created_by = SEED_SOURCE
    event.last_state_updated_at = now
    event.last_updated_at = now
    event.host_type = "bar"
    event.host_id = str(bar.id)
    event.host_display_name = bar.name
    event.visibility = "PUBLIC"
    event.publication_status = "PUBLISHED"
    event.public_description = spec["public_description"]
    event.short_description = spec["short_description"]
    event.event_type = spec["event_type"]
    event.capacity = spec["capacity"]
    event.access_type = spec["access_type"]
    event.currency = "EUR"
    event.address = bar.address
    event.city = bar.city
    event.lat = bar.lat
    event.lng = bar.lng
    session.flush()

    runtime = session.execute(
        select(EventRuntimeState).where(EventRuntimeState.event_id == event.id)
    ).scalar_one_or_none()
    if runtime is None:
        runtime = EventRuntimeState(event_id=event.id)
        session.add(runtime)
    runtime.state = spec["runtime_state"]
    runtime.reason = "local_demo_seed"
    runtime.updated_at = now

    return event


def main() -> None:
    _assert_local_dev_database()
    now = now_utc()

    bar_specs = [
        {
            "partner_code": "DEMO_CARRE",
            "name": "TORÈ Demo · Le Carré",
            "city": "Liège",
            "lat": 50.6414,
            "lng": 5.5718,
            "public_description": "Bar étudiant de démonstration au cœur de Liège, pensé pour tester le parcours TORÈ.",
            "address": "Quartier du Carré · Liège (démo)",
            "practical_info": "Données locales de démonstration — pas un établissement réel TORÈ.",
            "public_modules": {"menu": True, "events": True},
            "partner_status": "ACTIVE",
            "public_visibility": "PUBLIC",
            "primary_color": "#F5C400",
            "secondary_color": "#111116",
        },
        {
            "partner_code": "DEMO_QUAI22",
            "name": "TORÈ Demo · Quai 22",
            "city": "Liège",
            "lat": 50.6462,
            "lng": 5.5794,
            "public_description": "Spot de démonstration en bord de Meuse pour les soirées live et DJ sets.",
            "address": "Quai de la Meuse · Liège (démo)",
            "practical_info": "Données locales de démonstration — pas un établissement réel TORÈ.",
            "public_modules": {"menu": True, "events": True},
            "partner_status": "ACTIVE",
            "public_visibility": "PUBLIC",
            "primary_color": "#F5C400",
            "secondary_color": "#111116",
        },
        {
            "partner_code": "DEMO_VERRIERE",
            "name": "TORÈ Demo · La Verrière",
            "city": "Liège",
            "lat": 50.6380,
            "lng": 5.5873,
            "public_description": "Lieu de démonstration plus calme pour afterworks, collectifs et événements associatifs.",
            "address": "Outremeuse · Liège (démo)",
            "practical_info": "Données locales de démonstration — pas un établissement réel TORÈ.",
            "public_modules": {"menu": True, "events": True},
            "partner_status": "ACTIVE",
            "public_visibility": "PUBLIC",
            "primary_color": "#F5C400",
            "secondary_color": "#111116",
        },
    ]

    event_specs = [
        {
            "bar_code": "DEMO_CARRE",
            "event_code": "DEMO-LIVE-01",
            "name": "TORÈ Demo · Open Decks du Carré",
            "starts_delta": timedelta(minutes=-45),
            "ends_delta": timedelta(hours=4),
            "runtime_state": "LIVE",
            "venue": "Salle principale · Le Carré (démo)",
            "public_description": "Une soirée déjà en cours pour tester immédiatement Découverte, détail, rejoindre et Event Hub.",
            "short_description": "DJ sets étudiants · événement LIVE de démonstration.",
            "event_type": "DJ_SET",
            "capacity": 350,
            "access_type": "FREE",
            "entry_price_cents": 0,
            "charter_enabled": False,
        },
        {
            "bar_code": "DEMO_CARRE",
            "event_code": "DEMO-NIGHT-02",
            "name": "TORÈ Demo · Bal des Facs",
            "starts_delta": timedelta(hours=12),
            "ends_delta": timedelta(hours=18),
            "runtime_state": "SCHEDULED",
            "venue": "Grande salle · Le Carré (démo)",
            "public_description": "Bal étudiant de démonstration avec jauge, entrée payante et charte à accepter.",
            "short_description": "Bal étudiant · ce soir · charte activée.",
            "event_type": "STUDENT_PARTY",
            "capacity": 700,
            "access_type": "TICKET",
            "entry_price_cents": 500,
            "charter_enabled": True,
        },
        {
            "bar_code": "DEMO_QUAI22",
            "event_code": "DEMO-TECH-03",
            "name": "TORÈ Demo · Nuit Techno sur Meuse",
            "starts_delta": timedelta(hours=30),
            "ends_delta": timedelta(hours=37),
            "runtime_state": "SCHEDULED",
            "venue": "Quai 22 · salle basse (démo)",
            "public_description": "Nuit techno de démonstration pour tester les événements à venir et les détails de lieu.",
            "short_description": "Techno · demain soir · capacité 500.",
            "event_type": "CLUB_NIGHT",
            "capacity": 500,
            "access_type": "TICKET",
            "entry_price_cents": 800,
            "charter_enabled": False,
        },
        {
            "bar_code": "DEMO_VERRIERE",
            "event_code": "DEMO-AFTER-04",
            "name": "TORÈ Demo · Afterwork Outremeuse",
            "starts_delta": timedelta(hours=54),
            "ends_delta": timedelta(hours=59),
            "runtime_state": "SCHEDULED",
            "venue": "La Verrière · patio (démo)",
            "public_description": "Afterwork associatif de démonstration pour varier les formats visibles dans Découverte.",
            "short_description": "Afterwork · entrée libre · ambiance associative.",
            "event_type": "AFTERWORK",
            "capacity": 180,
            "access_type": "FREE",
            "entry_price_cents": 0,
            "charter_enabled": False,
        },
    ]

    session = get_session()
    try:
        bars_by_code: dict[str, Bar] = {}
        for spec in bar_specs:
            bar = _upsert_bar(session, spec)
            bars_by_code[bar.partner_code] = bar

        events: list[Event] = []
        for spec in event_specs:
            events.append(
                _upsert_event(session, bars_by_code[spec["bar_code"]], spec, now=now)
            )

        session.commit()

        print(
            json.dumps(
                {
                    "ok": True,
                    "source": SEED_SOURCE,
                    "bars": [
                        {"id": bar.id, "name": bar.name, "city": bar.city}
                        for bar in bars_by_code.values()
                    ],
                    "events": [
                        {
                            "id": event.id,
                            "name": event.name,
                            "state": event.event_state,
                            "starts_at": event.starts_at.isoformat(),
                            "event_code": event.event_code,
                        }
                        for event in events
                    ],
                    "recommended_test_event": next(
                        (
                            {"id": event.id, "name": event.name}
                            for event in events
                            if event.event_code == "DEMO-LIVE-01"
                        ),
                        None,
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
