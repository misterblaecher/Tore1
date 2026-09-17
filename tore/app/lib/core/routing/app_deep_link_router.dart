enum AppDeepLinkKind {
  event,
  join,
  bar,
  eventMenu,
  barMenu,
  qr,
}

class AppDeepLink {
  const AppDeepLink({
    required this.kind,
    this.id,
    this.payload,
  });

  final AppDeepLinkKind kind;
  final int? id;
  final String? payload;
}

/// Pure parser for public TORÈ links.
///
/// UI/navigation stays in the active app shell (`ToreMvpApp`). This parser only
/// accepts the explicit compatibility hosts/scheme and never executes a route
/// string returned by the backend.
class AppDeepLinkRouter {
  const AppDeepLinkRouter();

  static const _httpsHosts = <String>{
    'tore.app',
    'dev.tore.app',
    'stage.tore.app',
    'app.tore.be',
  };

  AppDeepLink? parse(String rawUrl) {
    final trimmed = rawUrl.trim();
    if (trimmed.isEmpty) return null;

    final uri = Uri.tryParse(trimmed);
    if (uri == null || !_isSupported(uri)) return null;

    final legacy = _parseLegacyOpen(uri);
    if (legacy != null) return legacy;

    final segments = _segmentsFor(uri);
    if (segments.isEmpty) return null;

    switch (segments.first.toLowerCase()) {
      case 'event':
        final id = _positiveInt(segments.length >= 2 ? segments[1] : null);
        return id == null
            ? null
            : AppDeepLink(kind: AppDeepLinkKind.event, id: id);
      case 'bar':
        final id = _positiveInt(segments.length >= 2 ? segments[1] : null);
        return id == null
            ? null
            : AppDeepLink(kind: AppDeepLinkKind.bar, id: id);
      case 'menu':
        if (segments.length < 3) return null;
        final scope = segments[1].toLowerCase();
        final id = _positiveInt(segments[2]);
        if (id == null) return null;
        if (scope == 'event') {
          return AppDeepLink(kind: AppDeepLinkKind.eventMenu, id: id);
        }
        if (scope == 'bar') {
          return AppDeepLink(kind: AppDeepLinkKind.barMenu, id: id);
        }
        return null;
      case 'qr':
        if (segments.length < 2) return null;
        final payload = Uri.decodeComponent(segments.sublist(1).join('/')).trim();
        return payload.isEmpty
            ? null
            : AppDeepLink(kind: AppDeepLinkKind.qr, payload: payload);
      default:
        return null;
    }
  }

  bool _isSupported(Uri uri) {
    if (uri.scheme == 'tore') return true;
    return uri.scheme == 'https' && _httpsHosts.contains(uri.host.toLowerCase());
  }

  AppDeepLink? _parseLegacyOpen(Uri uri) {
    final isCompatibleHttpsOpen = uri.scheme == 'https' &&
        _httpsHosts.contains(uri.host.toLowerCase()) &&
        uri.path == '/open';
    final isLegacyScheme = uri.scheme == 'tore' && uri.host == 'open';
    if (!isCompatibleHttpsOpen && !isLegacyScheme) return null;

    final type = uri.queryParameters['type']?.trim().toLowerCase();
    final id = _positiveInt(
        uri.queryParameters['id'] ?? uri.queryParameters['eventId']);

    switch (type) {
      case 'event':
        return id == null
            ? null
            : AppDeepLink(kind: AppDeepLinkKind.event, id: id);
      case 'join':
        return id == null
            ? null
            : AppDeepLink(kind: AppDeepLinkKind.join, id: id);
      case 'menu':
        return id == null
            ? null
            : AppDeepLink(kind: AppDeepLinkKind.eventMenu, id: id);
      case 'qr':
        final payload = (uri.queryParameters['payload'] ??
                uri.queryParameters['code'] ??
                uri.queryParameters['id'] ??
                '')
            .trim();
        return payload.isEmpty
            ? null
            : AppDeepLink(kind: AppDeepLinkKind.qr, payload: payload);
      default:
        return null;
    }
  }

  List<String> _segmentsFor(Uri uri) {
    if (uri.scheme == 'tore') {
      final host = uri.host.trim();
      if (host.isNotEmpty) {
        return <String>[
          host,
          ...uri.pathSegments.where((segment) => segment.isNotEmpty),
        ];
      }
    }
    return uri.pathSegments.where((segment) => segment.isNotEmpty).toList();
  }

  int? _positiveInt(String? raw) {
    final value = int.tryParse((raw ?? '').trim());
    return value != null && value > 0 ? value : null;
  }
}
