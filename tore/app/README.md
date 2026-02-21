# mobile

A new Flutter project.

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Lab: Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Cookbook: Useful Flutter samples](https://docs.flutter.dev/cookbook)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.

## Android Gradle Wrapper bootstrap (Windows)

If `android/gradle/wrapper/gradle-wrapper.jar` is missing or corrupted locally, regenerate a fresh wrapper JAR from a temporary Flutter project and copy it:

```powershell
flutter create _tmp_wrapper
copy /Y _tmp_wrapper\android\gradle\wrapper\gradle-wrapper.jar android\gradle\wrapper\gradle-wrapper.jar
```

Then run:

```powershell
.\android\gradlew.bat -v
```

## Run dev (Render)

```bash
flutter run --flavor dev --dart-define=TORE_API_BASE_URL=https://tore-backend.onrender.com
```

## Run dev (local)

```bash
flutter run --flavor dev --dart-define=TORE_API_BASE_URL=http://10.0.2.2:8000
```

## Run on Windows (Render)

```bash
flutter run -d windows --dart-define=TORE_API_BASE_URL=https://tore-backend.onrender.com
```
