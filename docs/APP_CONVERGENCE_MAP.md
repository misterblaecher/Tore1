# APP Convergence Map — V3 (`features/*`) vs Rebuild (`rebuild/*`)

Date: 2026-02-23
Scope: inventory + dedup pass only (no feature implementation)

## 1) Inventory table (capabilities/screens/flows)

| Capability / Screen / Flow | Current location(s) | Status | Notes (gating, backend, risks) |
|---|---|---|---|
| App bootstrap + entrypoint | V3: legacy boot flow documented in old registers; current runtime entry now points to rebuild. Rebuild: `tore/app/lib/main.dart`, `tore/app/lib/rebuild/tore_rebuild_app.dart` | KEEP REBUILD | **Single entrypoint already active**: `runApp(const ToreRebuildApp())`. Risk: legacy docs still mention `_BootEntry`/`AppShell` as primary path. |
| Bottom navigation USER (Home/Events/Scan/Polymarket/Profile) | V3: `tore/app/lib/app_shell.dart`, `tore/app/lib/features/navigation/presentation/*`, `tore/app/lib/features/qr/presentation/qr_scanner_gate_screen.dart`. Rebuild: in-app nav in `ToreRebuildApp` + routes in `rebuild/routing/app_routes.dart` | MERGE | Duplicate navigation surfaces. Keep rebuild navigation surface visible; hide legacy `AppShell` route access to prevent user split. |
| QR scan + routing | V3: `tore/app/lib/features/qr/qr_router.dart`, `tore/app/lib/core/qr/*`, `features/qr/presentation/*`. Rebuild: `rebuild/routing/qr_router.dart`, `rebuild/ui/screens/user/user_screens.dart` (scanner), `rebuild/services/api_client.dart` (`/qr/resolve`) | MERGE | V3 router is richer for QR types; rebuild is canonical runtime entry. Minimal-risk path: keep rebuild shell, migrate missing QR decision branches from V3 before deleting legacy router. |
| Deep links (`tore://`, web open links) | V3: `features/qr/presentation/code_entry_detector.dart` supports `tore://open` + `https://app.tore.be/open`. Rebuild: `rebuild/routing/deep_link_router.dart` supports `tore://` and `https://{tore.app,dev.tore.app,stage.tore.app}` | MERGE | Current duplicated and inconsistent host matrix. Keep rebuild deep-link parser as canonical surface, add temporary compatibility for `app.tore.be/open` during migration window. |
| Bars → Events → Join → Event Hub | V3: `features/bars/*`, `features/qr/presentation/join_event_screen.dart`, `features/events/presentation/event_hub_screen.dart`. Rebuild: `AppRoutes.bars/events/join/eventHub` + `rebuild/ui/screens/user/user_screens.dart` | MERGE | Both surfaces exist. Rebuild currently mounted in `main.dart`; V3 flow should be treated as migration source, not second user path. |
| Menu + cart/order lifecycle | V3: `features/menu_market/presentation/*`, `features/orders/presentation/*`. Rebuild: `AppRoutes.menu` and module definition `user_orders_lifecycle` (no dedicated rebuild orders screen yet) | KEEP V3 | Critical UX depth remains mostly V3 today. Keep V3 implementation as source and migrate only minimum needed UI into rebuild in PR-B. |
| Wallet + ledger | V3: `features/wallet/*`, `api.dart` wallet calls. Rebuild: `AppRoutes.wallet`, `rebuild/services/api_client.dart` (`/wallet/me`) | MERGE | Duplicate service access with slightly different params (`event_id` query in rebuild). Backend contracts must be source-of-truth; normalize response field aliases once. |
| Ticker | V3: `features/ticker/*` + navigation ticker screen. Rebuild: `AppRoutes.ticker`, `fetchTicker('/events/{id}/ticker')` | MERGE | Equivalent capability duplicated. Keep rebuild route visible; retain V3 provider logic as migration source until parity checks pass. |
| Polymarket global/event | V3: `features/polymarket/*`, `features/market/*`, `api.dart`. Rebuild: `AppRoutes.polymarketGlobal` + `AppRoutes.polymarketEvent`, `rebuild/services/api_client.dart` | MERGE | High-risk write actions. Keep rebuild guard model (reason/idempotency pattern), migrate mature V3 UI elements only where missing. |
| ORGA event control + urgency | V3: distributed across `features/entry/*`, `features/reports/*`, admin screens. Rebuild: `rebuild/ui/screens/orga/orga_screens.dart`, `orga_exports_screen.dart` | KEEP REBUILD | Rebuild has explicit guarded ORGA routes and state-aware write buttons. Keep rebuild visible; retire parallel legacy ORGA entrypoints. |
| BAR dashboard/orders/menu/zones/analytics | V3: bar + orders + menu admin features under `features/*`. Rebuild: `rebuild/ui/screens/bar/bar_screens.dart`, `AppRoutes.bar*` | MERGE | Rebuild has complete route shell but several stubs. Keep rebuild routing surface; migrate missing non-stub BAR UX from V3 before deletion. |
| Committees/forum/baptême | V3: `features/committees/*`, heavy API usage in `api.dart`. Rebuild: no equivalent UI routes in `AppRoutes` | KEEP V3 | Not yet rebuilt. Explicitly keep in V3 code until migration PR; hide from rebuild navigation to avoid partial exposure. |
| Hunt/Battles/WiFi/Map-Calendar/Glossary/Safety | V3: dedicated feature folders under `features/*`. Rebuild: module catalog entries exist but many screens not implemented or not routed | KEEP V3 | Treat module catalog entries as roadmap placeholders; do not expose as active rebuild flows until migrated. |
| Diagnostics/dev tooling | V3: none centralized. Rebuild: `AppRoutes.devDiagnostics`, `rebuild/ui/screens/dev/diagnostics_screen.dart` | KEEP REBUILD | Keep rebuild-only, production-gated by remote config. |

## 2) Routes & entrypoints audit

### 2.1 Current app entrypoints
- **Actual runtime entrypoint**: `tore/app/lib/main.dart` runs `ToreRebuildApp`.
- **Legacy shell still present in repo**: `tore/app/lib/app_shell.dart` (not mounted by `main.dart`).

### 2.2 Rebuild route surface (`ToreRebuildApp` + `AppRoutes`)
- USER: `/user/boot`, `/user/consent`, `/user/home`, `/user/scanner`, `/user/bars`, `/user/events`, `/user/join`, `/user/event_hub`, `/user/menu`, `/user/wallet`, `/user/ticker`, `/user/polymarket_global`, `/user/polymarket_event`, `/user/profile`, `/user/help`.
- ORGA: `/orga/hub`, `/orga/entry`, `/orga/menu_admin`, `/orga/polymarket_admin`, `/orga/urgency`, `/orga/exports`, `/orga/runbook`.
- BAR: `/bar/dashboard`, `/bar/orders`, `/bar/menu_admin`, `/bar/zones`, `/bar/analytics`.
- DEV/GUARD: `/dev/diagnostics`, `/blocked`.

### 2.3 Legacy/AppShell routes and navigators
- `AppShell` uses nested `Navigator` tabs (Home/Events/Polymarket/Profile) and central scan button; this is a **parallel route surface** that can diverge from rebuild route guards.
- Legacy QR router pushes many feature screens directly (`EntryStaffScreen`, `MenuScreen`, `EventHubScreen`, invites, WiFi, Hunt, etc.), bypassing rebuild `AppRoutes`.

### 2.4 Deep-link support (current)
- Rebuild parser (`deep_link_router.dart`):
  - `tore://...` accepted.
  - `https://tore.app/*`, `https://dev.tore.app/*`, `https://stage.tore.app/*` accepted.
  - Supported prefixes: `/qr/*`, `/event/:id`, `/bar/:id`, `/menu/:scope/:id`.
- Legacy manual detector (`code_entry_detector.dart`):
  - `tore://open?...`
  - `https://app.tore.be/open?...`

### 2.5 Dead/duplicated routes and single routing proposal
- **Duplicated**: USER tabs, QR entrypoints, event/menu/polymarket screens exist in both trees.
- **Dead from runtime perspective**: legacy `AppShell` path is currently unreachable via `main.dart` unless called manually/tests.
- **Single routing strategy (target)**:
  1. Keep `main.dart -> ToreRebuildApp` as sole public entrypoint.
  2. Route all deep links through rebuild `DeepLinkRouter` + `QrRouter`.
  3. During migration, keep legacy screens callable only through internal adapters (no direct external/deep-link landing).

## 3) Backend contract alignment

Source-of-truth mandated: `docs/MOBILE_BACKEND_CONTRACTS.md`.

### 3.1 Aligned endpoints (already consistent in rebuild)
- `/bars`, `/bars/{bar_id}/events`, `/events/{event_id}/join`, `/events/{event_id}/context`, `/events/{event_id}/menu`, `/wallet/me`, `/events/{event_id}/ticker`, `/polymarket/global`, `/events/{event_id}/polymarket`, `/orders/live`, `/orders/{order_id}/status`.

### 3.2 Mismatches to resolve (high priority)
1. **Entry stats/scan paths**
   - Contract: `/entry/stats`, `/entry/scan`, `/entry/logs`.
   - Rebuild currently uses partner portal namespace: `/partner/portal/orga/events/{event_id}/entry/stats` and `/partner/portal/orga/events/{event_id}/entry/scan` (with fallback variant).
   - Action: unify app clients on contract endpoints or explicitly version portal endpoints in contracts.
2. **Zones paths**
   - Contract: `/bars/{bar_id}/zones`, `PATCH /zones/{zone_id}`.
   - Rebuild currently uses `/partner/portal/bar/{bar_id}/zones` and `/partner/portal/zones/{zone_id}`.
   - Action: same as above; prefer contract paths for mobile-facing clients.
3. **Legacy `api.dart` superscope risk**
   - V3 `api.dart` calls many endpoints outside the scoped mobile contracts (committees, music, admin, map/calendar, open links, etc.).
   - Action: maintain a contract allowlist for convergence so migration does not silently bind rebuild to legacy/portal-only endpoints.

### 3.3 Single-source decision
- **Single source for endpoint semantics: `docs/MOBILE_BACKEND_CONTRACTS.md`.**
- Any endpoint used by either V3 or rebuild but absent in contracts must be: (a) added to contracts with payload schema, or (b) considered out-of-scope and removed from mobile route surface.

## 4) Convergence plan (3 PRs max, minimal risk)

### PR A — Surface dedup (visibility control, no heavy migrations)
- Keep only rebuild route surface publicly reachable (`main.dart`, deep links, nav).
- Remove/hide duplicated external entrypoints into legacy `AppShell`/legacy QR route pushes.
- Add temporary compatibility mapping for `https://app.tore.be/open` into rebuild deep-link parser.
- Deliverable: one visible user path, no feature additions.

### PR B — Critical minimal migration
- Migrate only critical user/bar/orga pieces still missing in rebuild from V3 (menu/orders depth, selected BAR UX, richer QR outcomes).
- Align endpoint calls to `MOBILE_BACKEND_CONTRACTS.md` (or update contracts first when needed).
- Keep behavior parity tests focused on joins, orders writes, entry, wallet, polymarket writes.

### PR C — Cleanup + truth docs
- Delete unused legacy route glue and unreachable screens/services after parity completion.
- Remove duplicate providers/repositories no longer referenced.
- Update registries/docs and tests to reflect single routing surface and endpoint contracts.

## 5) Done criteria mapping
- ✅ Clear keep/migrate/remove decision per major module in inventory table.
- ✅ Single routing strategy proposed (`main.dart -> ToreRebuildApp` only).
- ✅ No new features defined/implemented; this ticket is inventory + plan only.
