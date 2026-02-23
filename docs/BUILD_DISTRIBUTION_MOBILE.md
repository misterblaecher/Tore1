# Mobile build & distribution

## Required env/defines
- `TORE_ENV`: `dev`, `stage`, or `prod`.
- API base URL should follow environment:
  - DEV: `https://dev-api.tore.app`
  - STAGE: `https://stage-api.tore.app`
  - PROD: `https://api.tore.app`
- Recommended dart define usage:
  - `--dart-define=TORE_ENV=dev`
  - `--dart-define=TORE_ENV=stage`
  - `--dart-define=TORE_ENV=prod`

## Build commands
From `tore/app`:

```bash
flutter clean && flutter pub get
flutter build apk --flavor dev --dart-define=TORE_ENV=dev
flutter build apk --flavor stage --dart-define=TORE_ENV=stage
flutter build apk --flavor prod --dart-define=TORE_ENV=prod
```

```bash
flutter build ipa --flavor prod --dart-define=TORE_ENV=prod
```

## Version bump checklist
1. Update version/build in `tore/app/pubspec.yaml` (`version: x.y.z+build`).
2. Rebuild flavor artifacts.
3. Update remote config:
   - `min_supported_version`
   - `min_supported_build`
4. Re-run:
   - `./scripts/rc_verify_mobile.sh`
   - `./scripts/rc_grep_pii.sh`

## Distribution quick steps
### TestFlight (iOS)
1. Build IPA with `prod` flavor.
2. Upload in Xcode Organizer / Transporter.
3. Add release notes and assign testers in App Store Connect.

### Internal APK (Android)
1. Build APK/AAB for target flavor.
2. Upload to internal track (Play Console) or internal MDM.
3. Share install instructions with environment badge expectation.

## OS-level deep link plumbing (platform checklist)
- Android: add `intent-filter` entries for `tore://` + verified `https://*.tore.app/*` in `AndroidManifest.xml`.
- iOS: add URL Types for `tore` and Associated Domains for `applinks:dev.tore.app`, `applinks:stage.tore.app`, `applinks:tore.app`.
- Validate links with platform tooling before RC sign-off.
