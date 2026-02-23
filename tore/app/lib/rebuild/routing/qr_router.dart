import '../models/qr_resolve.dart';
import 'app_routes.dart';

class QrRouter {
  String targetFor(QrResolve resolved) {
    if (resolved.routeFront != null && resolved.routeFront!.isNotEmpty) {
      return resolved.routeFront!;
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
      case 'wallet':
        return AppRoutes.wallet;
      case 'profile':
        return AppRoutes.profile;
      case 'orga_entry':
        return AppRoutes.orgaEntry;
      case 'bar_zones':
        return AppRoutes.barZones;
      default:
        return AppRoutes.blocked;
    }
  }
}
