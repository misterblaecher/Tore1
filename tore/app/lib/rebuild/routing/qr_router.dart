import '../models/qr_resolve.dart';
import 'app_routes.dart';

class QrRouter {
  static const Set<String> _allowedTargets = {
    AppRoutes.boot,
    AppRoutes.consent,
    AppRoutes.home,
    AppRoutes.scanner,
    AppRoutes.bars,
    AppRoutes.events,
    AppRoutes.join,
    AppRoutes.eventHub,
    AppRoutes.menu,
    AppRoutes.orders,
    AppRoutes.wallet,
    AppRoutes.ticker,
    AppRoutes.polymarketGlobal,
    AppRoutes.polymarketEvent,
    AppRoutes.profile,
    AppRoutes.userHelp,
    AppRoutes.orgaHub,
    AppRoutes.orgaEntry,
    AppRoutes.orgaMenu,
    AppRoutes.orgaMarket,
    AppRoutes.orgaUrgency,
    AppRoutes.orgaExports,
    AppRoutes.orgaRunbook,
    AppRoutes.devDiagnostics,
    AppRoutes.barDashboard,
    AppRoutes.barOrders,
    AppRoutes.barMenu,
    AppRoutes.barZones,
    AppRoutes.barAnalytics,
    AppRoutes.blocked,
  };

  String targetFor(QrResolve? resolved) {
    if (resolved == null) return AppRoutes.blocked;
    final routeFront = resolved.routeFront?.trim();
    if (routeFront != null && routeFront.isNotEmpty) {
      if (!routeFront.startsWith('/')) return AppRoutes.blocked;
      return _allowedTargets.contains(routeFront)
          ? routeFront
          : AppRoutes.blocked;
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
