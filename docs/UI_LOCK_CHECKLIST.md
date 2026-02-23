# UI LOCK Checklist (TORÈ V2 rebuild)

Use this checklist for final manual QA before release.

## USER
- [ ] Boot / Consent: loading skeleton visible, no blank state, offline banner shown when needed.
- [ ] Home Hub: module cards visible only when module is ON/FROZEN/READ_ONLY, OFF modules hidden.
- [ ] QR Scanner: camera frame + manual input + torch/help actions visible; success and error feedback clear.
- [ ] QR Scanner errors: verify `qr_unknown`, `expired`, `replay`, `module_off`, `event_paused`, `backend_down` copy.
- [ ] Event Hub: event status banner reflects LIVE/PAUSED/MENU_ONLY/CLOSED and CTA enable/disable is coherent.
- [ ] Menu: cache-first read, refresh entry point present, offline shows cached/read-only behavior, confirm CTA disabled offline.
- [ ] Wallet: large monospace balance + transaction timeline spacing consistent.
- [ ] Profile Settings: privacy, theme, and accessibility toggles present (high contrast / reduce motion).

## ORGA
- [ ] Event Control Hub: entry counter block readable, module toggles become read-only when writes not allowed.
- [ ] Entry Staff: scan result clearly displays OK / DENIED / ERROR + last 5 scans list.
- [ ] Urgency Actions: every sensitive action asks reason, payload preview visible (dev).

## BAR
- [ ] Orders Live: compact rows with status chips and readable hierarchy.
- [ ] Zones QR: empty state handled, enable/disable toggles present, export stub button present.

## Global checks
- [ ] Network banner appears on every main screen and writes are blocked with actionable copy in OFFLINE.
- [ ] Confirm dialogs enforce reason preset + required text for `other`.
