# Large Python files audit (safe split step)

## Selection criteria (current step)
- Include **all** Python files above **1500 LOC**.
- Include Python files between **800 and 1500 LOC** when they mix concerns (routing + business logic + DB access + utilities/constants).
- Exclude `.venv/venv`, `__pycache__`, `build/dist`, `node_modules`.

## Repo scan snapshot (descending LOC)

| Path | LOC | Role (observed) | Incoming imports (high-level) | Decision | Next step |
|---|---:|---|---|---|---|
| `app/legacy/monolith.py` | 11914 | Legacy runtime compatibility monolith | Broad runtime anchoring (main compat + legacy hooks) | **Ignored (kept)** | Keep as compatibility anchor during incremental extraction |
| `app/legacy/models_monolith.py` | 2377 | Historical ORM model surface | Via `models.py` wrapper and legacy imports | **Already split** | Keep as extracted source; continue thin wrapper strategy |
| `app/db/sqlite_compat.py` | 1052 | SQLite compatibility/migration helpers | Imported from monolith startup path | **Ignore** (cohesive module) | No split needed now |
| `app/legacy/orders_router_monolith.py` | 865 | Orders router (routes + serialization + DB queries + analytics exports) | Routed via `app.routers.orders` wrapper, runtime include in monolith | **Split done** | Later extract route helpers into dedicated service modules |
| `app/routers/orders.py` | 6 | Compat wrapper for orders router | Imported by monolith/app startup router include | **Already split** | Keep wrapper minimal |
| `app/legacy/portal_event_control_router_monolith.py` | 975 | Partner portal event control router (staff, modules, QR, profitability, exports) | Routed via `app.routers.portal_event_control` wrapper | **Split done** | Later isolate wizard/templates and reporting helpers |
| `app/routers/portal_event_control.py` | 6 | Compat wrapper for portal router | Imported by monolith/app startup router include | **Already split** | Keep wrapper minimal |
| `app/legacy/polymarket_service_monolith.py` | 912 | Polymarket business service (validation, wallet side-effects, disputes, timeline helpers) | Called through `app.services.polymarket_service` wrapper and routers | **Split done** | Later split validations/queries/settlement operations |
| `app/services/polymarket_service.py` | 6 | Compat wrapper for polymarket service | Imported by routers/tests through stable path | **Already split** | Keep wrapper minimal |
| `app/routers/music_vote.py` | 942 | Router with multiple concerns (auth gating + voting + state checks + DB writes) | Imported in legacy monolith routing graph | **To split next** | Candidate for extraction to `app/legacy/*_monolith.py` + wrapper |
| `app/routers/hunt.py` | 863 | Router with game flow + DB orchestration + response shaping | Imported in legacy monolith routing graph | **To split next** | Candidate for extraction after smoke checks |
| `app/routers/polymarket.py` | 847 | Router orchestrating polymarket service + auth/rate-limit + DTO mapping | Imported in legacy monolith routing graph | **To split next** | Candidate after music/hunt if additional ROI needed |

## Mandatory “split already exists?” verification

For each selected candidate, repository checks were performed against:
- Modern modules (`app/services/*`, `app/routers/*`, `app/core/*`, `app/utils/*`).
- Legacy equivalents (`app/legacy/*`).
- Duplicated implementations by key module/function names.

Results:
- `models.py` already had extraction target (`app/legacy/models_monolith.py`) and now uses standardized wrapper helper.
- `orders.py`, `portal_event_control.py`, and `polymarket_service.py` did not have dedicated legacy extraction files before this step; each was extracted unchanged to `app/legacy/*_monolith.py` and original import path converted to a compat wrapper.
- `app/db/sqlite_compat.py` is already cohesive and not duplicated; no split applied.

## Wrapper compatibility pattern (standardized)
- New helper: `app/compat/reexport.py::reexport_public(module, globals_dict, allowlist=None, denylist=None)`.
- Behavior:
  - Re-exports public names by module-level assignment (`globals()[name] = getattr(...)`) to preserve monkeypatchability.
  - Supports explicit allow/deny lists.
  - Builds stable `__all__`.
- Applied to `models.py` and newly introduced wrappers in routers/services.

## LOC impact for selected splits
- `app/routers/orders.py`: **865 → 6** (implementation moved to `app/legacy/orders_router_monolith.py`).
- `app/routers/portal_event_control.py`: **975 → 6** (implementation moved to `app/legacy/portal_event_control_router_monolith.py`).
- `app/services/polymarket_service.py`: **912 → 6** (implementation moved to `app/legacy/polymarket_service_monolith.py`).
