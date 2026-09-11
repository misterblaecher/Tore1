import '../../config/app_config.dart';

/// Builds public and app-scheme TORÈ links for the canonical runtime.
///
/// The public origin can be overridden at build time with
/// `TORE_PUBLIC_APP_URL`. Environment fallbacks intentionally keep the hosts
/// already accepted by [AppDeepLinkRouter] during the convergence window.
class AppLinkBuilder {
  const AppLinkBuilder({required this.publicBaseUrl});

  final String publicBaseUrl;

  factory AppLinkBuilder.fromConfig(AppConfig config) {
    const override =
        String.fromEnvironment('TORE_PUBLIC_APP_URL', defaultValue: '');
    final configured = override.trim();
    if (configured.isNotEmpty) {
      return AppLinkBuilder(publicBaseUrl: _normalizeBase(configured));
    }
    return AppLinkBuilder(
      publicBaseUrl: switch (config.environmentName) {
        'prod' || 'production' => 'https://tore.app',
        'stage' || 'staging' => 'https://stage.tore.app',
        _ => 'https://dev.tore.app',
      },
    );
  }

  String event(int eventId) => _https(['event', '$eventId']);

  String join(int eventId) => _https(['open'], query: {
        'type': 'join',
        'id': '$eventId',
      });

  String bar(int barId) => _https(['bar', '$barId']);

  String eventMenu(int eventId) => _https(['menu', 'event', '$eventId']);

  String barMenu(int barId) => _https(['menu', 'bar', '$barId']);

  String qr(String payload) => _https(['qr', payload]);

  String appEvent(int eventId) => _app(['event', '$eventId']);

  String appBar(int barId) => _app(['bar', '$barId']);

  String appEventMenu(int eventId) => _app(['menu', 'event', '$eventId']);

  String appBarMenu(int barId) => _app(['menu', 'bar', '$barId']);

  String appQr(String payload) => _app(['qr', payload]);

  String _https(List<String> pathSegments, {Map<String, String>? query}) {
    final base = Uri.parse(publicBaseUrl);
    return base
        .replace(pathSegments: pathSegments, queryParameters: query)
        .toString();
  }

  String _app(List<String> segments) {
    if (segments.isEmpty) return 'tore://';
    return Uri(
      scheme: 'tore',
      host: segments.first,
      pathSegments: segments.skip(1).toList(growable: false),
    ).toString();
  }

  static String _normalizeBase(String raw) {
    final uri = Uri.tryParse(raw.trim());
    if (uri == null ||
        uri.scheme != 'https' ||
        !uri.hasAuthority ||
        uri.host.isEmpty ||
        uri.userInfo.isNotEmpty ||
        uri.hasQuery ||
        uri.hasFragment) {
      throw const FormatException(
          'TORE_PUBLIC_APP_URL doit être une origine HTTPS publique.');
    }
    return uri.replace(path: '').toString().replaceFirst(RegExp(r'/+$'), '');
  }
}
