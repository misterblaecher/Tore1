# RC Edge-Case Matrix (Mobile Rebuild)

## QR resolution
| Case | Trigger | Expected UI | Expected log event key |
|---|---|---|---|
| Unknown QR | Random payload / malformed code | Blocked state with `QR inconnu` copy | `qr.route` + `api.error` |
| Expired QR | QR contains expired claim / backend `expired_qr` | Blocked state with renewal CTA | `qr.route` |
| Replay QR | Same one-time QR scanned twice | Blocked state with replay copy | `qr.route` |
| Module OFF | Backend returns `module_off` | Blocked state, route denied | `qr.route` |
| Event paused | Backend reason `event_paused` | Blocked/frozen copy, writes disabled | `qr.route`, `write.blocked` |
| Backend down | `/qr/resolve` timeout/5xx | Blocked state fallback, never throw | `api.error`, `qr.route` |

## Network/cache
| Case | Trigger | Expected UI | Expected log event key |
|---|---|---|---|
| Degraded network | Simulate degraded mode | Banner + stale-safe content | `api.request` |
| Offline after warm cache | Toggle offline after online load | Cache content shown, no crash | `offline.read_cache` |
| First-launch offline | Offline with empty cache | Blocked copy instead of exception | `api.error` |
| Cache stale + backend fail | Cached stale + request fails | Keep stale content | `api.error` |

## State machine transitions
| Case | Trigger | Expected UI | Expected log event key |
|---|---|---|---|
| LIVE -> PAUSED mid-screen | Event context refresh to paused | Buttons freeze/read-only | `write.blocked` |
| PAUSED -> MENU_ONLY | Module set readOnly | Navigation remains stable | `api.request` |
| MENU_ONLY -> CLOSED | Event ended while on module | Read-only/blocked visuals | `write.blocked` |
| Mode switch during transition | USER to ORGA during route change | Guarded block view, no throw | `qr.route` |

## Idempotency
| Case | Trigger | Expected UI | Expected log event key |
|---|---|---|---|
| Replay same intent | Retry same write intent | Same idempotency key reused | `write.sent` |
| Different intent | Change action payload | New idempotency key | `write.sent` |
| Store cleared | Clear idempotency store then retry | New key generated once | `write.sent` |

## Guards/parsing
| Case | Trigger | Expected UI | Expected log event key |
|---|---|---|---|
| Wrong mode | Open ORGA route in USER mode | Blocked mode message | `qr.route` |
| Missing capability | Route without permission | Blocked state (guard) | `qr.route` |
| Missing fields | Partial API payload map | Safe defaults, no crash | `api.request` |
| Empty arrays | `items: []`, `next_cursor: ''` | Empty state, pager stops safely | `api.request` |
| Repeated cursor | API returns same cursor twice | Pager halts, no infinite loop | `api.request` |
