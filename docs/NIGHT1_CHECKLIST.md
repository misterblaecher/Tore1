# Night-1 Operator Checklist

Use this with:
- `docs/RELEASE_CHECKLIST_MOBILE_RC.md`
- `docs/OPS_SMOKE_TEST_MOBILE_RC.md`
- `docs/ROLLBACK_PLAN_MOBILE.md`

## Pre-night setup
- [ ] Confirm release candidate version/build and git SHA match handoff notes.
- [ ] Verify correct environment build installed on USER/ORGA/BAR devices.
- [ ] Print and place QR pack for venue zones and fallback entry flow.
- [ ] Validate remote config loaded with target env seed from `REMOTE_CONFIG_SEED.md`.
- [ ] Confirm `disable_writes_global=false` before doors open.
- [ ] Run operator smoke path from `OPS_SMOKE_TEST_MOBILE_RC.md` once per role.
- [ ] Confirm diagnostics screen is reachable for on-site triage.

## During-night checks
- [ ] Entry flow: scan and manual code fallback both accepted.
- [ ] Orders flow: create/confirm path works on live network.
- [ ] Bar flow: incoming orders and status updates propagate.
- [ ] Offline test: temporary network drop shows degraded/offline messaging.
- [ ] Recovery test: reconnect clears degraded state and sync resumes.
- [ ] Monitor diagnostics/telemetry for repeated write failures.
- [ ] Re-run key points from `RELEASE_CHECKLIST_MOBILE_RC.md` after major incident.

## Emergency actions
- [ ] If backend instability: set `disable_writes_global=true` with operator message.
- [ ] If severe user impact: pause event writes and announce read-only mode.
- [ ] If bad client version detected: raise min supported build/version to trigger update-required screen.
- [ ] Follow owner/escalation and rollback decision tree in `ROLLBACK_PLAN_MOBILE.md`.

## Post-night wrap
- [ ] Export QR/admin packs and nightly telemetry logs.
- [ ] Save links to incident notes, screenshots, and release report.
- [ ] Record final remote config state and any temporary toggles left enabled.
