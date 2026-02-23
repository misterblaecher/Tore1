# Mobile build & distribution

## Required Dart defines
Every build command below must set:
- `TORE_ENV=dev|stage|prod`
- `TORE_API_BASE_URL=<env API base>`
- `TORE_STARTUP_URL=<optional deep link/route for QA fast-entry>`

Recommended API bases:
- DEV: `https://dev-api.tore.app`
- STAGE: `https://stage-api.tore.app`
- PROD: `https://api.tore.app`

## Android builds
Run from `tore/app` after dependency sync:

```bash
flutter clean && flutter pub get
```

### APK (internal test / sideload)
```bash
flutter build apk --release \
  --flavor dev \
  --dart-define=TORE_ENV=dev \
  --dart-define=TORE_API_BASE_URL=https://dev-api.tore.app \
  --dart-define=TORE_STARTUP_URL=tore://home-hub

flutter build apk --release \
  --flavor stage \
  --dart-define=TORE_ENV=stage \
  --dart-define=TORE_API_BASE_URL=https://stage-api.tore.app \
  --dart-define=TORE_STARTUP_URL=tore://home-hub

flutter build apk --release \
  --flavor prod \
  --dart-define=TORE_ENV=prod \
  --dart-define=TORE_API_BASE_URL=https://api.tore.app
```

### Android App Bundle (Play Store)
```bash
flutter build appbundle --release \
  --flavor stage \
  --dart-define=TORE_ENV=stage \
  --dart-define=TORE_API_BASE_URL=https://stage-api.tore.app

flutter build appbundle --release \
  --flavor prod \
  --dart-define=TORE_ENV=prod \
  --dart-define=TORE_API_BASE_URL=https://api.tore.app
```

## iOS build
### IPA (TestFlight)
```bash
flutter build ipa --release \
  --flavor prod \
  --dart-define=TORE_ENV=prod \
  --dart-define=TORE_API_BASE_URL=https://api.tore.app
```

Optional QA fast-entry:
```bash
flutter build ipa --release \
  --flavor stage \
  --dart-define=TORE_ENV=stage \
  --dart-define=TORE_API_BASE_URL=https://stage-api.tore.app \
  --dart-define=TORE_STARTUP_URL=tore://orga/control
```

## Artifact naming convention
Rename/copy exported binaries using:

`tore_<env>_<version>+<build>_<gitsha>.<apk|aab|ipa>`

Examples:
- `tore_dev_1.8.0+220_a1b2c3d.apk`
- `tore_stage_1.8.0+220_a1b2c3d.aab`
- `tore_prod_1.8.0+220_a1b2c3d.ipa`

## Distribution quick steps
1. Build artifact with matching env flavor + defines.
2. Verify runtime diagnostics shows expected env/API base.
3. Upload:
   - APK/AAB: internal or Play track.
   - IPA: TestFlight via Organizer/Transporter.
4. Attach release notes and Night-1 checklist links in operator handoff.
