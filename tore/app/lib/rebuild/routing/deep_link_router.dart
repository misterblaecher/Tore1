import 'app_routes.dart';

class DeepLinkRoute {
  const DeepLinkRoute._({required this.route, this.qrPayload});

  const DeepLinkRoute.route(String route) : this._(route: route);

  const DeepLinkRoute.qr(String payload) : this._(route: AppRoutes.scanner, qrPayload: payload);

  final String route;
  final String? qrPayload;

  bool get isQr => qrPayload != null && qrPayload!.isNotEmpty;
}

class DeepLinkRouter {
  DeepLinkRoute? parse(String rawUrl) {
    final trimmed = rawUrl.trim();
    if (trimmed.isEmpty) return null;
    final uri = Uri.tryParse(trimmed);
    if (uri == null) return null;

    if (!_isSupported(uri)) return null;

    final segments = _segmentsFor(uri);
    if (segments.isEmpty) return null;

    switch (segments.first) {
      case 'qr':
        if (segments.length < 2) return null;
        return DeepLinkRoute.qr(Uri.decodeComponent(segments.sublist(1).join('/')));
      case 'event':
        return segments.length >= 2 ? const DeepLinkRoute.route(AppRoutes.eventHub) : null;
      case 'bar':
        return segments.length >= 2 ? const DeepLinkRoute.route(AppRoutes.barDashboard) : null;
      case 'menu':
        return segments.length >= 3 ? const DeepLinkRoute.route(AppRoutes.menu) : null;
      default:
        return null;
    }
  }

  bool _isSupported(Uri uri) {
    if (uri.scheme == 'tore') return true;
    if (uri.scheme != 'https') return false;
    return const {'tore.app', 'dev.tore.app', 'stage.tore.app'}.contains(uri.host);
  }

  List<String> _segmentsFor(Uri uri) {
    if (uri.scheme == 'tore') {
      final host = uri.host.trim();
      if (host.isNotEmpty) {
        return [host, ...uri.pathSegments.where((segment) => segment.isNotEmpty)];
      }
    }
    return uri.pathSegments.where((segment) => segment.isNotEmpty).toList();
  }
}
