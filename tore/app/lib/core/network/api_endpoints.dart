import '../../config/app_config.dart';

class ApiEndpoints {
  /// Base URL for the backend.
  ///
  /// It is configurable via --dart-define=TORE_API_BASE_URL=...
  static String get baseUrl => AppConfig.apiBaseUrl;

  static const authGuest = '/auth/guest';
  static const authMe = '/auth/me';

  // ✅ Market
  static String eventMenu(int eventId) => '/events/$eventId/menu';

  // ✅ Orders
  static const orders = '/orders';
}
