# Large Python files audit (safe split step)

## Selection criteria
- Priority 1: all Python files above 3000 LOC.
- Priority 2: files between 1500 and 3000 LOC when mixing multiple responsibilities.

## Top 3 largest files (scan)

| Path | LOC | Presumed role | Status |
|---|---:|---|---|
| `app/legacy/monolith.py` | 11915 | legacy monolith (router/service/auth/startup mixed) | already partially split; kept runtime source of truth for compat |
| `models.py` | 2378 | ORM models aggregation | split in this step via compat wrapper |
| `app/db/sqlite_compat.py` | 1053 | DB sqlite compatibility/migrations helpers | dedicated module already split/cohesive |

## Split-existence checks and decisions

### `app/legacy/monolith.py`
- Existing split modules detected in `app/core/*`, `app/routers/*`, `app/services/*`, `app/api/*`.
- File is still imported at runtime by many modules for compatibility symbols (`get_db`, auth helpers, startup hooks, etc.).
- Decision: **already split + keep as compatibility anchor** (no behavior change in this step).

### `models.py`
- No dedicated split module existed for the ORM declaration surface.
- Runtime usage is broad (`from models import ...` in routers/services/tests/alembic).
- Decision: **split safely** by moving full implementation to `app/legacy/models_monolith.py` and keeping `models.py` as monkeypatchable re-export wrapper.

### `app/db/sqlite_compat.py`
- Already a dedicated focused module imported from monolith startup.
- Decision: **ignored for now** (not oversized per threshold and already cohesive).

## Compatibility guarantees applied
- `models.py` preserves import compatibility by assigning public symbols from the new module (`X = _models_monolith.X` pattern via dynamic loop).
- This keeps existing import paths stable (`import models`, `from models import X`) while enabling incremental future decomposition.
