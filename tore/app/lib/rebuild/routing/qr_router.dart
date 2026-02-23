import '../models/qr_resolve.dart';
import 'app_routes.dart';

class QrRouter {
  String targetFor(QrResolve resolved) {
    switch (resolved.type) {
      case 'join_event':
        return AppRoutes.join;
      case 'menu':
        return AppRoutes.menu;
      case 'event_hub':
        return AppRoutes.eventHub;
      case 'orders_live':
        return AppRoutes.barOrders;
      default:
        return AppRoutes.eventHub;
    }
  }
}
