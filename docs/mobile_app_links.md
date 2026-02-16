# TORÈ App Links / Universal Links (P10.4)

## Android App Links

- Host: `https://app.tore.be/open`
- Manifest wiring: `tore/app/android/app/src/main/AndroidManifest.xml`
- Asset links file to host: `/.well-known/assetlinks.json`

### TODO before production verify

1. Replace fingerprint placeholder in `tore-portal/public/.well-known/assetlinks.json`.
2. Use the **release** signing cert SHA-256 fingerprint.
3. Deploy file on `https://app.tore.be/.well-known/assetlinks.json`.

## iOS Universal Links

Configure Associated Domains on iOS app target:

- `applinks:app.tore.be`

This repository ships documentation/wiring only for iOS in P10.4.
