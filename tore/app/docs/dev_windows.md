# Développement Windows (Flutter Android) — stabilité build

Ce guide évite les erreurs Windows suivantes :
- `PathAccessException: Access denied (errno=5)` pendant la copie d'assets Flutter.
- crash Kotlin daemon / erreurs incremental caches (`different roots`, ex: `A:\...` vs `C:\...`).

## Pré-requis obligatoires (même drive)

Pour éviter les problèmes de roots différents, tout doit être sur `C:` :

- Flutter SDK: `C:\Users\miste\Documents\flutter`
- PUB_CACHE: `C:\Users\miste\Documents\flutter_pub_cache`
- Projet: `C:\Users\miste\Documents\GitHub\Tore\tore\app`

> Ne pas utiliser de cache Flutter/Pub sur `A:\` (ou un autre drive).

Vérification rapide dans PowerShell:

```powershell
where flutter
flutter --version
echo $env:PUB_CACHE
```

## Script d'environnement

Depuis `tore/app`:

```powershell
.\tooling\windows_env.ps1
```

Le script:
- ajoute `C:\Users\miste\Documents\flutter\bin` au `PATH` (session courante),
- force `PUB_CACHE=C:\Users\miste\Documents\flutter_pub_cache`,
- affiche `where flutter`, `flutter --version` et `PUB_CACHE`.

## Nettoyage hard (avant build)

```powershell
.\tooling\clean_hard.ps1
```

Le script:
- stoppe les process `java/gradle/gradlew` si présents,
- supprime `build/`, `android/.gradle/`, `android/app/build/`.

## Kotlin / Gradle workaround appliqué

Dans `android/gradle.properties`:
- `kotlin.incremental=false`
- `kotlin.incremental.useClasspathSnapshot=false`
- `kotlin.compiler.execution.strategy=in-process`

Objectif: contourner les problèmes de caches incrémentaux et de daemon Kotlin sur Windows quand des roots différents ont été utilisés précédemment.

## API_BASE_URL (dart-define)

L'app supporte:
- `--dart-define=TORE_API_BASE_URL=...` (clé principale)
- `--dart-define=API_BASE_URL=...` (compatibilité)

Au boot, un log affiche l'URL de base effectivement utilisée.

## Commandes de validation (Windows)

```powershell
.\tooling\windows_env.ps1
.\tooling\clean_hard.ps1
flutter pub get
flutter run --flavor dev -t lib/main.dart --dart-define=API_BASE_URL=https://tore-backend.onrender.com
```

Résultat attendu:
- build Android OK,
- installation de `app-dev-debug.apk`,
- plus d'erreurs Kotlin incremental caches / daemon,
- plus d'erreurs `Access denied (errno=5)` liées aux locks/caches.

## Workaround Defender / antivirus (recommandé)

Si `errno=5` persiste:
- ajouter des exclusions Windows Security/Defender pour:
  - le dossier du projet (`...\Tore\tore\app`),
  - le dossier `PUB_CACHE` (`...\flutter_pub_cache`),
  - éventuellement le dossier Flutter SDK.

Puis relancer:
1. `clean_hard.ps1`
2. `flutter pub get`
3. `flutter run ...`
