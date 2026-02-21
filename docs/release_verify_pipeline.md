# Verify release App Links pipeline (PR57)

Ce pipeline local vérifie de bout en bout les App Links Android en production :
1. Génération de `assetlinks.json` depuis le keystore release.
2. Build du portail web (`tore-portal`).
3. Validation stricte du fichier `assetlinks.json` généré.
4. Vérification ADB sur device connecté (si disponible).

Le pipeline est disponible sur Unix et Windows.

## Prérequis

- `python`
- `npm`
- `keytool` (JDK)
- `adb` (optionnel, seulement pour les vérifications device)

Variables nécessaires :
- `ANDROID_KEYSTORE_PATH`
- `ANDROID_KEY_ALIAS`
- `ANDROID_STOREPASS` (recommandé via env uniquement)
- `ANDROID_KEYPASS` (recommandé via env uniquement)

Variables optionnelles :
- `ANDROID_PACKAGE_NAME` (défaut `com.tore.app`)

## Exécution

### Unix (macOS/Linux)

```bash
ANDROID_KEYSTORE_PATH=/path/to/release.jks \
ANDROID_KEY_ALIAS=release \
ANDROID_STOREPASS=*** \
ANDROID_KEYPASS=*** \
bash scripts/verify_release_links.sh
```

Options utiles :
- `--skip-adb` : ignore les étapes ADB
- `--ci` : force `npm ci`
- `--package-name com.tore.app`
- `--public-url https://app.tore.be`
- `--keystore /path/to/release.jks`
- `--alias release`

### Windows (PowerShell)

```powershell
$env:ANDROID_KEYSTORE_PATH='C:\path\to\release.jks'
$env:ANDROID_KEY_ALIAS='release'
$env:ANDROID_STOREPASS='***'
$env:ANDROID_KEYPASS='***'
powershell -ExecutionPolicy Bypass -File scripts/verify_release_links.ps1
```

Options utiles :
- `-SkipAdb`
- `-Ci`
- `-PackageName com.tore.app`
- `-PublicUrl https://app.tore.be`
- `-Keystore C:\path\to\release.jks`
- `-Alias release`

## Vérification device Android

Pour brancher un device :

```bash
adb devices
```

- Si au moins un device `device` est visible, le pipeline exécute la vérification `pm` et un test d’ouverture d’URL (`am start`).
- Si `adb` est absent ou aucun device connecté, la partie ADB est **SKIP** avec message explicite.

## Interprétation des sorties

- `PASS`: étape validée.
- `WARN`: étape non bloquante (ex: ADB non disponible).
- `FAIL`: erreur bloquante.
- `RESULT: PASS` / `RESULT: FAIL`: résultat final du pipeline.

Le script retourne un code non nul sur échec des prérequis essentiels (génération `assetlinks`, build portal, validation JSON).

## Checklist avant déploiement

- [ ] Keystore release et alias corrects.
- [ ] `assetlinks.json` généré dans `tore-portal/public/.well-known/assetlinks.json`.
- [ ] Validation du JSON et du fingerprint SHA-256 colon-delimited.
- [ ] Build portail réussi (`npm run build`).
- [ ] (Recommandé) Vérification ADB + test d’ouverture URL sur device réel.
- [ ] Pipeline termine avec `RESULT: PASS`.
