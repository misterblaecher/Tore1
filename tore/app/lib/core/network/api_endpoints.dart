import '../../config/app_config.dart';

class ApiEndpoints {
  /// Base URL for the backend.
  ///
  /// It is configurable via --dart-define=TORE_API_BASE_URL=...
  /// and backward-compatible with --dart-define=API_BASE_URL=...
  static String get baseUrl => AppConfig.apiBaseUrlResolved;

  static const authGuest = '/auth/guest';
  static const authMe = '/auth/me';
  static const authGoogle = '/auth/google';
  static const authEmailRequestLink = '/auth/email/request_link';
  static const authEmailVerifyLink = '/auth/email/verify_link';
  static const authRefresh = '/auth/refresh';
  static const authUpgradeGuest = '/auth/upgrade_guest';

  // ✅ Market
  static String eventMenu(int eventId) => '/events/$eventId/menu';

  // ✅ Orders
  static const orders = '/orders';
}
