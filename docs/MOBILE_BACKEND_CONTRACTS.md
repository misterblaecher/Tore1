# Mobile backend contracts (rebuild binding)

## USER
- `GET /bars`
  - Query: `cursor`, `limit`
  - Response keys: `items[]` (bar rows), `next_cursor`.
- `GET /bars/{bar_id}/events`
  - Query: `filter`, `cursor`, `limit`
  - Response keys: `events[]|items[]`, `next_cursor`.
- `POST /events/{event_id}/join`
  - Body: `code` (optional)
  - Headers: `X-Idempotency-Key`
  - Response keys: `ok`, `event_id`, `joined`.
- `GET /events/{event_id}/context`
  - Response keys: `eventState|event_state`, `modulesOn`, `lastUpdatedAt`.
- `GET /menu/public/{bar_id}` and `GET /events/{event_id}/menu`
  - Response keys: `items[]|menu[]` with menu rows (`id,name,price`).
- `GET /wallet/me`, `GET /wallet/me/ledger`
  - Query for ledger: `cursor`, `limit`
  - Response keys: `balance`, `entries[]|items[]`, `next_cursor`.
- `GET /events/{event_id}/ticker`
  - Query: `cursor`, `limit`
  - Response keys: `items[]`, `next_cursor`.
- `GET /polymarket/global`
  - Response keys: `items[]|markets[]`.
- `GET /events/{event_id}/polymarket`
  - Response keys: `items[]|markets[]`.

## ORGA
- `GET /entry/stats`
  - Query: `event_id`
  - Response keys: `approved_count`, `denied_count`, `total_count`.
- `POST /entry/scan`
  - Body: scanner payload (`qr`, `event_id`, extra metadata)
  - Headers: `X-Idempotency-Key`
  - Response keys: `status`, `reason`, `scan_id`, `idempotent`.
- `GET /entry/logs`
  - Query: `event_id`, `cursor`, `limit`
  - Response keys: `items[]`, `next_cursor`.
- Urgency/admin actions are served under ORGA/portal endpoints and require reason payloads (`reason_code`, `reason_text`) and audit logging.

## BAR
- `GET /orders/live`
  - Query: `event_id`, `status`, `cursor`, `limit`
  - Response keys: `orders[]|items[]`, `next_cursor`, `runtime_state`.
- `PATCH /orders/{order_id}/status`
  - Body: `status`, optional `reason_text`
  - Headers: `X-Idempotency-Key`
  - Response keys: updated order (`id,status,...`).
- `GET /bars/{bar_id}/zones`
  - Query: `cursor`, `limit`
  - Response keys: `items[]`, `next_cursor`.
- `PATCH /zones/{zone_id}`
  - Body: `enabled`, optional reason/audit fields
  - Headers: `X-Idempotency-Key`
  - Response keys: updated zone (`id,name,enabled`).

## Source references
Routes inventoried from backend routers and monolith files:
- `tore-backend/app/legacy/monolith.py`
- `tore-backend/app/routers/wallet.py`
- `tore-backend/app/routers/entry.py`
- `tore-backend/app/routers/ticker.py`
- `tore-backend/app/routers/polymarket.py`
- `tore-backend/app/routers/zones.py`
- `tore-backend/app/legacy/orders_router_monolith.py`
