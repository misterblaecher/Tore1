# TORÈ — API Conventions

## URL namespaces
- `/auth/*` authentication
- `/me/*` identity snapshot
- `/events/{event_id}/*` event scoped
- `/bars/{bar_id}/*` bar scoped
- `/orga/*` orga scoped
- `/partner/*` bar staff scoped
- `/admin/*` global admin

## Write safety
All write endpoints must support:
- `Idempotency-Key` header
- audit log on sensitive actions
- consistent error shape

## Error format (recommended)
- `code` (string)
- `message` (human)
- `details` (optional)
