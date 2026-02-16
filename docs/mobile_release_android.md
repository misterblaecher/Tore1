# TORÈ mobile Android — build release et smoke tests

Ce guide couvre la configuration DEV/PROD, la signature Android release, les deep links et les commandes de build/install.

## 1) Prérequis

- Flutter SDK installé (`flutter --version`)
- JDK 17
- Android SDK + `adb`
- Un appareil Android branché (ou émulateur)

## 2) Configuration d'environnement (dart-define)

L'application lit les variables compile-time suivantes:

- `TORE_ENV` (`dev` ou `prod`)
- `TORE_API_BASE_URL` (URL backend)

Exemples:

```bash
flutter run --flavor dev \
  --dart-define=TORE_ENV=dev \
  --dart-define=TORE_API_BASE_URL=http://10.0.2.2:8000
```

```bash
flutter build apk --release --flavor prod \
  --dart-define=TORE_ENV=prod \
  --dart-define=TORE_API_BASE_URL=https://api.tore.example
```

## 3) Flavors Android

- `dev`
  - `applicationIdSuffix ".dev"`
  - nom d'app: **TORÈ Dev**
- `prod`
  - bundle/application id stable (`be.tore.app`)
  - nom d'app: **TORÈ**

## 4) Deep links Android

Intent filters configurés:

- `tore://qr?...` (scheme `tore`, host `qr`)
- `tore://<autre-host>/...` (host wildcard)
- App links HTTPS optionnels: `https://app.tore.be/...`

Tests manuels:

```bash
adb shell am start -a android.intent.action.VIEW -d 'tore://qr?token=demo'
```

```bash
adb shell am start -a android.intent.action.VIEW -d 'tore://menu?event_id=42'
```

```bash
adb shell am start -a android.intent.action.VIEW -d 'https://app.tore.be/qr?token=demo'
```

## 5) Signature release (sans commit de secrets)

1. Générer un keystore local:

```bash
keytool -genkey -v \
  -keystore upload-keystore.jks \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -alias upload
```

2. Copier le template:

```bash
cp android/key.properties.example android/key.properties
```

3. Remplir `android/key.properties` avec les vraies valeurs (fichier ignoré git).

Le build Gradle lit automatiquement `android/key.properties` si présent. Si absent, la signature debug est utilisée pour ne pas bloquer les builds locaux.

## 6) Build release

APK:

```bash
flutter build apk --release --flavor prod \
  --dart-define=TORE_ENV=prod \
  --dart-define=TORE_API_BASE_URL=https://api.tore.example
```

AAB:

```bash
flutter build appbundle --release --flavor prod \
  --dart-define=TORE_ENV=prod \
  --dart-define=TORE_API_BASE_URL=https://api.tore.example
```

## 7) Installation APK

```bash
adb install -r build/app/outputs/flutter-apk/app-prod-release.apk
```

## 8) Smoke test mobile

Vérifier:

1. Boot de l'app (pas de crash).
2. Join event.
3. Scanner QR.
4. Menu -> cart -> order QR.
5. Entry rush mode + capture offline (si réseau coupé).
6. Deep link `tore://qr?...` ouvre bien l'app.
