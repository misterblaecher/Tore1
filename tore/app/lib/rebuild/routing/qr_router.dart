import '../models/qr_resolve.dart';

class QrRouter {
  String targetFor(QrResolve resolved) {
    switch (resolved.type) {
      case 'join_event':
        return 'user_join';
      case 'menu':
        return 'user_menu';
      case 'event_hub':
      default:
        return 'user_event_hub';
    }
  }
}
