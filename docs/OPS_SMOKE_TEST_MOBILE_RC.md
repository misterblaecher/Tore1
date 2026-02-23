# OPS smoke test (mobile RC)

1. Boot app and accept consent charter; verify Home Hub renders with snapshot/event context.
2. QR resolve success path: valid hub/menu/join payload routes to expected screen.
3. QR resolve error paths: invalid, expired, replay, module_off, event_paused, backend_down microcopy.
4. Load Bars + Menu online, then switch OFFLINE and confirm cached reads still render.
5. Attempt a write while OFFLINE (join/order/zone/entry): verify `offline_write_blocked` message.
6. Set event state paused/read_only; verify CTAs disabled and write guards enforce blocking reason.
7. Entry scan idempotency: submit same intent twice with same key and verify no duplicate side-effect.
8. Orders live refresh: verify updates only while ONLINE (no polling/refresh loop in DEGRADED/OFFLINE).
9. Zones toggle write: confirm guard + idempotency header + optional reason payload when required.
10. Accessibility quick pass: high contrast + reduce motion toggles still keep flows usable.
