# TORÈ App Links / Universal Links (P10.4)

## Android App Links

- Host: `https://app.tore.be/open`
- Manifest wiring: `tore/app/android/app/src/main/AndroidManifest.xml`
- Asset links file to host: `/.well-known/assetlinks.json`

### 1) Calculer le SHA256 du certificat release

Utiliser **le keystore release** (pas debug):

```bash
keytool -list -v -keystore <release-keystore.jks> -alias <alias> -storepass <storepass> -keypass <keypass>
```

Repérer la ligne `SHA256:` et copier l’empreinte complète (format `AA:BB:...`).

Alternative depuis un APK/AAB signé:

```bash
apksigner verify --print-certs app-release.apk
```

### 2) Publier `assetlinks.json` avec le bon SHA

Fichier source recommandé: `tore-portal/public/.well-known/assetlinks.json`.

Checklist:

1. Mettre à jour `sha256_cert_fingerprints` avec le SHA release.
2. Vérifier `package_name` Android exact.
3. Déployer tel quel sur `https://app.tore.be/.well-known/assetlinks.json`.
4. Vérifier publiquement:

```bash
curl -fsSL https://app.tore.be/.well-known/assetlinks.json
```

## Verify app links (checklist)

### Android (adb)

```bash
adb shell pm get-app-links <android.package.name>
adb shell am start -a android.intent.action.VIEW -d "https://app.tore.be/open?type=event&id=123"
```

Attendu: ouverture TORÈ (pas navigateur) si l’app est installée et vérifiée.

### Browser sanity

- Ouvrir `https://app.tore.be/open?type=join&code=ABC12345`.
- Vérifier que la redirection fallback est cohérente quand l’app n’est pas installée.
- Refaire le test après chaque rotation de cert/signature release.

## iOS Universal Links

Configurer Associated Domains sur la target iOS:

- `applinks:app.tore.be`

Ce repository couvre la doc/wiring iOS, sans build/release iOS dans cette PR.
