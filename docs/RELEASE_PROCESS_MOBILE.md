# TORÈ Mobile release process

## Core references
- [Release checklist](./RELEASE_CHECKLIST_MOBILE_RC.md)
- [Ops smoke test](./OPS_SMOKE_TEST_MOBILE_RC.md)
- [Rollback plan](./ROLLBACK_PLAN_MOBILE.md)
- [Night-1 operator checklist](./NIGHT1_CHECKLIST.md)
- [Remote config seed payloads](./REMOTE_CONFIG_SEED.md)
- [UI screenshot pack guide](./UI_SCREENSHOT_PACK.md)

## 1) Bump version
1. Update `tore/app/pubspec.yaml` (`version: x.y.z+build`).
2. Pass defines for build metadata when compiling (`APP_VERSION`, `APP_BUILD`, optional `GIT_SHA`, `BUILD_TIME`).

## 2) Install deps + checks
1. `flutter clean && flutter pub get`
2. `flutter analyze`
3. `flutter test`
4. `./scripts/rc_verify_mobile.sh`
5. `./scripts/rc_grep_pii.sh`

## 3) Tag and release notes
1. Create release notes from `docs/RELEASE_NOTES_TEMPLATE.md`.
2. Tag commit: `git tag vX.Y.Z-mobile`.
3. Push branch + tag.
4. Attach “what changed” summary and risk/rollback notes.

## 4) Screenshot pack
Capture current user/orga/bar critical screens and store in release artifact pack using `docs/UI_SCREENSHOT_PACK.md`.

## 5) Go/No-Go
- Confirm remote config defaults for PROD from `docs/REMOTE_CONFIG_SEED.md`.
- Confirm rollback owner + on-call contact via `docs/ROLLBACK_PLAN_MOBILE.md`.
- Confirm telemetry export path for post-mortem.
