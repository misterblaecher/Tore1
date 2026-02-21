# TORÈ App Links / Universal Links (PR56)

## Scope

- Production App Links URL: `https://app.tore.be/open`
- Digital Asset Links file: `https://app.tore.be/.well-known/assetlinks.json`
- Android App Links verification is **prod flavor only** (`be.tore.app`).
- Existing deep links `tore://open` and `tore://qr` remain unchanged in the app manifest.

## Android App Links configuration

### App manifest

Manifest file: `tore/app/android/app/src/main/AndroidManifest.xml`.

Configured intent filters:

- `https://app.tore.be/open...` with `android:autoVerify="@bool/app_links_auto_verify"`
- `tore://qr`
- `tore://*` (includes `tore://open`)

Flavor behavior:

- `prod`: `@bool/app_links_auto_verify = true`
- `dev`: `@bool/app_links_auto_verify = false`

This avoids requiring production asset links for `applicationId` dev flavor (`be.tore.app.dev`).

## Generate `assetlinks.json` from template

### Versioned files

- Template (committed): `tore-portal/public/.well-known/assetlinks.template.json`
- Generated output: `tore-portal/public/.well-known/assetlinks.json`

Template contains placeholder `__SHA256_CERT__`. The generator script computes SHA256 from local release keystore and writes final JSON.

### Script

- Script: `scripts/gen_assetlinks.py`
- Inputs:
  - `ANDROID_PACKAGE_NAME` (optional, defaults to `applicationId` from `tore/app/android/app/build.gradle.kts`)
  - `ANDROID_KEYSTORE_PATH` (required)
  - `ANDROID_KEY_ALIAS` (required)
  - `ANDROID_STOREPASS` (optional env)
  - `ANDROID_KEYPASS` (optional env)

#### macOS / Linux

```bash
export ANDROID_KEYSTORE_PATH="$HOME/keystores/tore-release.jks"
export ANDROID_KEY_ALIAS="tore-release"
export ANDROID_STOREPASS="***"
export ANDROID_KEYPASS="***"
python3 scripts/gen_assetlinks.py
```

#### Windows PowerShell

```powershell
$env:ANDROID_KEYSTORE_PATH = 'C:\keys\tore-release.jks'
$env:ANDROID_KEY_ALIAS = 'tore-release'
$env:ANDROID_STOREPASS = '***'
$env:ANDROID_KEYPASS = '***'
python scripts/gen_assetlinks.py
```

Expected output:

- SHA256 fingerprint (normalized, without `:`)
- generated file path (`tore-portal/public/.well-known/assetlinks.json`)

Failure conditions (exit code 1):

- `keytool` missing
- keystore missing
- SHA256 not found

## Deploy

Deploy the generated file exactly at:

- `https://app.tore.be/.well-known/assetlinks.json`

Quick check:

```bash
curl -fsSL https://app.tore.be/.well-known/assetlinks.json
```

## Verify App Links on Android (adb)

Scripts:

- Bash: `scripts/verify_app_links_android.sh`
- PowerShell: `scripts/verify_app_links_android.ps1`

### Linux / macOS

```bash
ANDROID_APP_ID=be.tore.app ./scripts/verify_app_links_android.sh
# optional
ANDROID_APP_ID=be.tore.app DEVICE_ID=emulator-5554 ./scripts/verify_app_links_android.sh
```

### Windows PowerShell

```powershell
./scripts/verify_app_links_android.ps1 -AndroidAppId be.tore.app
# optional
./scripts/verify_app_links_android.ps1 -AndroidAppId be.tore.app -DeviceId emulator-5554
```

What the scripts run:

1. `adb shell pm verify-app-links --re-verify <appId>` (Android 12+)
2. `adb shell pm get-app-links <appId>`
3. `adb shell am start -a android.intent.action.VIEW -d "https://app.tore.be/open?type=event&id=test"`

The scripts print PASS/FAIL and fallback guidance when `pm verify-app-links` is not supported by the device Android version.

## Browser sanity

- Open `https://app.tore.be/open?type=join&code=ABC12345`
- Validate fallback behavior if app is not installed.
- Re-run checks after any cert rotation.

## iOS Universal Links

Associated domains (iOS target):

- `applinks:app.tore.be`
