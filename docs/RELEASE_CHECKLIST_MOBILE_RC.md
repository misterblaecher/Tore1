# Mobile RC Release Checklist

1. Run formatting, static analysis, and Dart tests.
2. Execute smoke test procedure from `docs/OPS_SMOKE_TEST_MOBILE_RC.md`.
3. Open Diagnostics screen and verify sections render with no crash.
4. Use Diagnostics copy-to-clipboard and verify output is scrubbed (no secrets/PII).
5. Confirm ORGA exports screen opens and invalid/unavailable links are blocked safely.
6. Verify offline cache read works after at least one online sync.
7. Verify writes are blocked while offline and user sees action guidance.
8. Verify event paused/read-only state disables sensitive writes.
9. Verify QR resolve fallback always lands on actionable blocked state on errors.
10. Verify idempotency replay keeps same key and avoids double action.
11. Run `./scripts/rc_verify_mobile.sh`.
12. Run `./scripts/rc_grep_pii.sh`.
