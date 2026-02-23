# TORÈ Mobile Release Notes Template

## Summary
- Release tag:
- Version/build:
- Date/time:
- Owner:

## What changed
### USER
-

### ORGA
-

### BAR
-

## Risk areas
-

## Rollback steps
- Set remote config freeze (`disable_writes_global=true`).
- Revert/promote previous build.
- Pause risky server modules if needed.

## Verification steps
- Run `./scripts/rc_verify_mobile.sh`.
- Run `./scripts/rc_grep_pii.sh`.
- Validate checklist: `docs/RELEASE_CHECKLIST_MOBILE_RC.md`.
