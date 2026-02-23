# Mobile rollback plan (TORÈ)

## 1) Immediate freeze (night safety)
1. Update remote config payload and set:
   - `disable_writes_global=true`
   - `disable_writes_message="Temporary freeze while incident is investigated"`
2. (Optional) Raise `min_supported_build`/`min_supported_version` to force update gate.
3. Confirm in Diagnostics that remote config source is `remote` or `cache` with the freeze fields.

## 2) Revert client build
1. Keep current release in store, but stop rollout / staged release progression.
2. Promote previous known-good build.
3. Post incident note to release channel with rollback timestamp and build id.

## 3) Server-side module pauses
Use backend toggles to reduce blast radius:
- Pause event state to read-only (`event_state=read_only`) where needed.
- Disable sensitive modules (entry writes / market resolution / urgency actions).
- Keep read paths and exports enabled for post-mortem.

## 4) Recovery
1. Clear `disable_writes_global` when backend/client are stable.
2. Lower/adjust minimum version requirements.
3. Re-run:
   - `./scripts/rc_verify_mobile.sh`
   - `./scripts/rc_grep_pii.sh`
4. Capture diagnostics + telemetry export and attach to incident ticket.
