import 'package:flutter/foundation.dart';

/// App-wide compile-time configuration loaded from `--dart-define`.
class AppConfig {
  const AppConfig({
    required this.apiBaseUrl,
    required this.environmentName,
  });

  final String apiBaseUrl;
  final String environmentName;

  static const String _apiBaseUrlDefine = 'TORE_API_BASE_URL';
  static const String _apiBaseUrlCompatDefine = 'API_BASE_URL';
  static const String _flutterFlavorDefine = 'FLUTTER_APP_FLAVOR';
  static const String _environmentDefine = 'TORE_ENV';
  static const String _defaultEnvironment = 'dev';

  static String get apiBaseUrlResolved => AppConfig.fromDartDefines().apiBaseUrl;

  factory AppConfig.fromDartDefines() {
    const definedApiBaseUrl = String.fromEnvironment(_apiBaseUrlDefine, defaultValue: '');
    const definedApiBaseUrlCompat = String.fromEnvironment(_apiBaseUrlCompatDefine, defaultValue: '');
    const definedFlavor = String.fromEnvironment(_flutterFlavorDefine, defaultValue: _defaultEnvironment);
    const definedEnv = String.fromEnvironment(_environmentDefine, defaultValue: _defaultEnvironment);
    final normalizedFlavor = (definedFlavor.isEmpty ? _defaultEnvironment : definedFlavor).toLowerCase();
    final normalizedEnv = (definedEnv.isEmpty ? normalizedFlavor : definedEnv).toLowerCase();

    final fallbackBaseUrl = _defaultBaseUrlForFlavor(normalizedFlavor);
    final apiBaseUrl = _resolveApiBaseUrl(
      primary: definedApiBaseUrl,
      compat: definedApiBaseUrlCompat,
      fallback: fallbackBaseUrl,
    );

    return AppConfig(
      apiBaseUrl: apiBaseUrl,
      environmentName: normalizedEnv,
    );
  }

  static String _resolveApiBaseUrl({
    required String primary,
    required String compat,
    required String fallback,
  }) {
    final normalizedPrimary = primary.trim();
    if (normalizedPrimary.isNotEmpty) {
      return _normalizeBaseUrl(normalizedPrimary);
    }

    final normalizedCompat = compat.trim();
    if (normalizedCompat.isNotEmpty) {
      return _normalizeBaseUrl(normalizedCompat);
    }

    return _normalizeBaseUrl(fallback);
  }

  static String _defaultBaseUrlForFlavor(String flavor) {
    switch (flavor) {
      case 'dev':
        return 'https://tore-backend.onrender.com';
      case 'prod':
        // TODO: replace with dedicated production API base URL when available.
        return 'https://tore-backend.onrender.com';
      default:
        if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
          return 'http://10.0.2.2:8000';
        }
        return 'http://localhost:8000';
    }
  }

  static String _normalizeBaseUrl(String url) {
    return url.replaceFirst(RegExp(r'/+$'), '');
  }

  /// Enable verbose HTTP logs (only in debug by default).
  static bool get enableHttpLogs =>
      kDebugMode && const bool.fromEnvironment('HTTP_LOGS', defaultValue: true);

  /// Enable extra auth/token logs (debug only).
  static bool get enableAuthLogs =>
      kDebugMode && const bool.fromEnvironment('AUTH_LOGS', defaultValue: false);
}
