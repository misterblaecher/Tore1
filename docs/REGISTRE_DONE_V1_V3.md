# REGISTRE DONE V1→V3 — TORÈ

Date de mise à jour: 2026-02-23

## 1) État des features/modules (USER / ORGA / BAR / COMITÉ)

| Domaine | Module / Feature | État | Notes d’alignement spec |
|---|---|---:|---|
| USER | Navigation lock (Home/Ticker/Scan/Polymarket/Profil) | ✅ | `AppShell` expose 4 tabs + scan central dominant (FAB). |
| USER | Scanner QR universel + fallback code manuel + écran QR inconnu | ✅ | `QrScannerGateScreen`, `code_entry_sheet`, `qr_unknown_screen` présents. |
| USER | Bars → Events → Join → Event Hub | ✅ | Flux implémenté (`BarsScreen`, `BarEventsScreen`, `JoinEventScreen`, `EventHubScreen`). |
| USER | Event state banner / réseau ONLINE-DEGRADED-OFFLINE | ✅ | Propagation alignée RUNNING/PAUSED/DEGRADED/FROZEN/ENDED sur écrans sensibles + messages de blocage write. |
| USER | Menu + panier + order QR + wallet + ticker | ✅ | Surfaces existantes côté app + backend (`orders`, `wallet`, `ticker`). |
| ORGA Event | Event Control Hub + transitions state machine avec audit | ✅ | Hub portal + endpoints `event-control`/audit + tests dédiés. |
| ORGA Event | Staff Entry rush-proof (scan/manual/export) | ✅ | Endpoints entry + exports CSV + écran portal staff entry/admin. |
| BAR Mode | Dashboard, orders live, menu admin, analytics | ✅ | Pages portal + endpoints bar/order/menu/analytics. |
| Sécurité | Idempotency keys write + logs reason sur actions sensibles | ✅ | Endpoints sensibles couverts par guards/tests (wallet/polymarket/ops) avec audit trail. |
| Sécurité | QR signé + anti-replay V1 | ✅ | Endpoints QR signés + tests (`test_qr_resolve_signed`). |
| Exports | Attendance CSV + report fin de soirée (CSV/PDF) | ✅ | Endpoints exports report/attendance/costs/pdf en place. |
| Musique | Module musique (tracks/queue/admin/user view) | ✅ | Endpoints/tests musique présents (`music_vote`, `music_rounds`). |
| Comité | Forum + rôles comité + baptême lifecycle + exports CSV | ✅ | Endpoints committee/forum/bapteme + tests dédiés. |
| Pack déploiement | docker compose + seed + runbook soirée/chapi | ✅ | Bootstrap local + smoke RC condensé + référence pipeline release links/assetlinks. |

## 2) Inventaire écrans & routes

### 2.1 Flutter (app)

- Entrée / boot: `_BootEntry` avec fallback réseau/session.
- Navigation lock: `AppShell` (Home / Events[Ticker] / Scan central / Polymarket / Profil).
- Routes déclarées:
  - `"/bars"` → `BarsScreen`
  - `"/bars/:barId/events"` (via `onGenerateRoute`) → `BarEventsScreen`
  - deep links `tore://open` et `https://app.tore.be/open`:
    - `type=event` → `EventPublicScreen`
    - `type=join` → `JoinEventScreen`
    - `type=orga` → `OrgaDetailScreen`
    - `type=staff_invite` → `StaffInviteJoinScreen`
    - `type=staff_backup` → `StaffBackupJoinScreen`
    - `type=orga_invite` → `OrgaInviteJoinScreen`

### 2.2 Portal (React)

- Public/auth: `/login`, `/open`, `/event/:eventId`, `/share/event/:eventId/print`, `/dev/status`
- Admin global: `/admin/audit`, `/admin/users`, `/admin/flags`, `/admin/role-requests`
- Ops event/orga: `/event-control/:eventId`, `/orga/create-event`, `/orga/events/:eventId/*`
- Entry/bar mode:
  - `/entry-staff`, `/entry-admin`
  - `/bar/events/:eventId/dashboard|menu|orders|analytics`
- Modules complémentaires: polymarket, hunts, battles, wifi, map, safety, zones, market

## 3) Endpoints backend par module (extrait opérationnel)

| Module | Endpoints clés (extrait) |
|---|---|
| Auth/Profile | `/auth/*`, `/me/export.json`, `/me/delete` |
| Bars/Events | `/bars`, `/bars/{bar_id}/events`, `/events`, `/events/{event_id}`, `/events/{event_id}/public`, `/events/{event_id}/join`, `/events/join_by_code` |
| Event state/control | `/events/{event_id}/state`, `/events/{event_id}/context`, `/event-control/*`, `/admin/audit` |
| Entry staff | `/events/{event_id}/entry/checkin`, `/entry/manual_increment`, `/entry/count`, `/entry/stats`, `/entry/export.csv`, `/entry/logs` |
| Orders/Menu/Bar | `/events/{event_id}/menu`, `/orders/*`, `/partner/portal/menu*`, `/bar/*`, `/partner/portal/events/{event_id}/drinks*` |
| Wallet/Ledger | `/tickets/balance`, `/events/{event_id}/wallet/history`, `/tickets/credit`, `/wallet/*` |
| QR/Links | `/qr/resolve`, `/codes/preview`, `/codes/consume`, `/shortlinks*`, `/events/{event_id}/qr-pack`, `/events/{event_id}/share_pack` |
| Exports fin de soirée | `/events/{event_id}/report`, `/events/{event_id}/exports/attendance.csv`, `/events/{event_id}/exports/report.pdf`, `/events/{event_id}/costs/export.csv` |
| Musique | routes `music_*` via router + votes (`music_vote_router`) |
| Comité/Forum/Baptême | `/committees/*`, `/committees/{id}/forum/*`, `/committees/{id}/bapteme/*`, `/committees/{id}/finances/*` |

## 4) Couverture “event_state gating coverage”

| Zone | Couverture actuelle | Statut |
|---|---|---:|
| Orders live / bar actions | Tests dédiés présents (`orders_live*`, `bar_*`) + contrôle hub | ✅ |
| Entry checkin/manual increment | Endpoints staff avec contrôles + logs | ✅ |
| Wallet write (credit/topup/transferts) | Couverture idempotence + blocage runtime validée sur endpoints sensibles | ✅ |
| Bets/Polymarket actions | Reason/idempotence homogénéisés sur routes event critiques + tests associés | ✅ |
| Event close/pause/menu_only propagation UI | Propagation mobile harmonisée avec mapping RUNNING/PAUSED/ENDED et bannières runtime | ✅ |
| Exports en CLOSED | Endpoints report/exports disponibles | ✅ |

## 5) Couverture “module OFF invisibility coverage”

| Surface | Respect OFF invisible | Statut | Action |
|---|---|---:|---|
| Event Hub Flutter | Affichage conditionnel modules déjà structuré | ✅ | Maintenir tests UI/snapshot. |
| Home/Discovery Flutter | Quick-links conditionnés aux modules ON, placeholders OFF retirés | ✅ | Vérifié via rendu conditionnel Home/Event Hub. |
| Portal navigation | Guards runtime/module présents sur pages ops sensibles (blocage explicite) | ✅ | Maintenir couverture smoke RC. |
| QR routing | Résolution backend + écran unknown propre | ✅ | Ajouter diagnostics plus détaillés côté staff. |

## 6) Plan de PRs (ordre imposé)

1. PR#1 USER nav lock + scanner central + QR routing + bannière réseau.
2. PR#2 USER parcours soirée complet (Bars→Events→Join→Hub) + OFF invisible + state banner.
3. PR#3 USER menu/panier/orders/wallet/ticker (cache + confirmations + flux robustes).
4. PR#4 Portal ORGA Event Control Hub (state machine + audit).
5. PR#5 Portal Entry Staff rush-proof + export CSV + idempotence.
6. PR#6 Portal BAR MODE complet (dashboard/orders/menu admin/analytics).
7. PR#7 QR signés V1 (HMAC/expiry/anti-replay) + indicateur bouclier.
8. PR#8 Exports V1 (attendance/orders/ledger/report fin de soirée).
9. PR#9 Module Musique V1 (orga control + user read-only).
10. PR#10 Fondations COMITÉ + permissions + forum.
11. PR#11 Baptême lifecycle + assignations + exports.
12. PR#12 Pack déploiement soirée/chapi (compose + seed + template + runbooks).

## 7) DONE criteria global (max 10)

1. Build vert: backend `pytest -q`, portal `npm run build`, flutter `analyze`.
2. Navigation USER lock conforme et scanner central opérationnel.
3. Modules OFF totalement invisibles côté USER.
4. Event state machine prioritaire sur modules partout (API+UI).
5. Actions sensibles: confirmation forte + reason obligatoire + audit log.
6. Ledger append-only pour toutes écritures de valeur + idempotence writes.
7. QR sensibles signés avec expiry + anti-replay minimum.
8. Staff entry/bar mode exploitables en condition terrain instable.
9. Exports fin de soirée disponibles et vérifiés (CSV/PDF).
10. Runbooks déploiement soirée/chapi testés bout-en-bout en local.


## 8) Addendum convergence V3 ↔ Rebuild (ticket INVENTORY + DEDUP)

- Entrée unique constatée dans le code: `main.dart` lance `ToreRebuildApp`.
- Les surfaces `features/*` et `rebuild/*` coexistent avec duplication sur navigation USER, QR, bars/events/join/hub, wallet, ticker, polymarket, ORGA/BAR shells.
- Décision de convergence:
  - **Surface visible unique**: rebuild `AppRoutes` (single visible surface).
  - **Deep links publics**: rebuild `DeepLinkRouter` uniquement.
  - **Source de vérité contrats backend**: `docs/MOBILE_BACKEND_CONTRACTS.md`.
  - **V3** est interne uniquement (bibliothèque d'implémentation via adapters), pas une surface de routes publiques.
- Référence plan détaillé: `docs/APP_CONVERGENCE_MAP.md` (inventaire, routes audit, mismatch contrats, plan PR A/B/C).

### Developer rules (convergence)
- Ne jamais ajouter de nouveau screen user-visible sous `features/*` sans exposition via un adapter rebuild + `AppRoutes` rebuild.
- Ne jamais ajouter de route deep-link publique en dehors de `rebuild/routing/deep_link_router.dart`.
