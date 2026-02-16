# TORÈ — Architecture

## Monorepo
- Backend: `tore-backend/` (source of truth)
- App: `tore/app/` (Flutter, UX terrain, offline-first)
- Portal: `tore-portal/` (Ops/admin/orga/staff)

## Principle
Backend owns:
- business rules
- permissions
- invariants (event state, module gating, write rules)

Clients (App/Portal) own:
- UX, caching, offline read-only
- displaying only what backend allows (context-driven UI)

## Core shared concepts
### EventContext (canonical)
Returned by backend to drive UI:
- `event_state`: RUNNING | PAUSED | DEGRADED | FROZEN | ENDED
- `modules_enabled[]`
- `write_allowed` + reason
- identity snapshot: roles + capabilities

## Data flow
- App/Portal authenticate -> receive JWT
- Call `/me` for identity + capabilities
- For event screens: call `/events/{id}/context`
- Writes always include `Idempotency-Key`
