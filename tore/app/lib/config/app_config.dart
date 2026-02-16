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
  static const String _environmentDefine = 'TORE_ENV';
  static const String _defaultEnvironment = 'dev';


  static String get apiBaseUrl => AppConfig.fromDartDefines().apiBaseUrl;

  factory AppConfig.fromDartDefines() {
    const definedApiBaseUrl = String.fromEnvironment(_apiBaseUrlDefine, defaultValue: '');
    const definedEnv = String.fromEnvironment(_environmentDefine, defaultValue: _defaultEnvironment);
    final normalizedEnv = (definedEnv.isEmpty ? _defaultEnvironment : definedEnv).toLowerCase();

    final fallbackBaseUrl = _defaultBaseUrlForCurrentPlatform;
    final apiBaseUrl = definedApiBaseUrl.isNotEmpty ? definedApiBaseUrl : fallbackBaseUrl;

    return AppConfig(
      apiBaseUrl: apiBaseUrl,
      environmentName: normalizedEnv,
    );
  }

  static String get _defaultBaseUrlForCurrentPlatform {
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      return 'http://10.0.2.2:8000';
    }
    return 'http://localhost:8000';
  }

  /// Enable verbose HTTP logs (only in debug by default).
  static bool get enableHttpLogs =>
      kDebugMode && const bool.fromEnvironment('HTTP_LOGS', defaultValue: true);

  /// Enable extra auth/token logs (debug only).
  static bool get enableAuthLogs =>
      kDebugMode && const bool.fromEnvironment('AUTH_LOGS', defaultValue: false);
}
