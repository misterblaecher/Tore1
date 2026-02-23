import '../models/qr_resolve.dart';
import 'app_routes.dart';

class QrRouter {
  String targetFor(QrResolve? resolved) {
    if (resolved == null) return AppRoutes.blocked;
    final routeFront = resolved.routeFront?.trim();
    if (routeFront != null && routeFront.isNotEmpty) {
      return routeFront.startsWith('/') ? routeFront : AppRoutes.blocked;
    }

    switch (resolved.type) {
      case 'join_event':
        return AppRoutes.join;
      case 'menu':
      case 'menu_user':
        return AppRoutes.menu;
      case 'event_hub':
        return AppRoutes.eventHub;
      case 'orders_live':
        return AppRoutes.barOrders;
      case 'order':
      case 'order_client':
        return AppRoutes.orders;
      case 'wallet':
        return AppRoutes.wallet;
      case 'profile':
      case 'user_profile':
        return AppRoutes.profile;
      case 'polymarket':
      case 'pm':
        return AppRoutes.polymarketGlobal;
      case 'orga':
      case 'orga_entry':
      case 'staff_entry':
      case 'entry_staff':
        return AppRoutes.orgaEntry;
      case 'bar_zones':
      case 'bar_profile':
      case 'bar_staff':
      case 'staff_bar':
        return AppRoutes.barZones;
      default:
        return AppRoutes.blocked;
    }
  }
}
