import 'package:flutter/foundation.dart';

/// App-wide configuration.
///
/// Configure the API base URL via:
///
///   flutter run --dart-define=API_BASE_URL=https://your-api.example.com
///
/// If not provided, we fall back to a sensible default.
class AppConfig {
  static const String _defaultApiBaseUrl = 'https://tore-backend.onrender.com';

  /// Base URL used by the HTTP client.
  static String get apiBaseUrl =>
      const String.fromEnvironment('API_BASE_URL', defaultValue: _defaultApiBaseUrl);

  /// Enable verbose HTTP logs (only in debug by default).
  ///
  /// You can disable even in debug with:
  ///   --dart-define=HTTP_LOGS=false
  static bool get enableHttpLogs =>
      kDebugMode && const bool.fromEnvironment('HTTP_LOGS', defaultValue: true);

  /// Enable extra auth/token logs (debug only).
  static bool get enableAuthLogs =>
      kDebugMode && const bool.fromEnvironment('AUTH_LOGS', defaultValue: false);
}
