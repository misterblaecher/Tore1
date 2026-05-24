import 'package:flutter_test/flutter_test.dart';
import 'package:tore/rebuild/routing/app_routes.dart';
import 'package:tore/rebuild/routing/deep_link_router.dart';

void main() {
  final router = DeepLinkRouter();

  test('parses tore://qr payload', () {
    final result = router.parse('tore://qr/payload_1');
    expect(result, isNotNull);
    expect(result!.isQr, isTrue);
    expect(result.qrPayload, 'payload_1');
  });

  test('parses https fallback for event/menu/bar', () {
    expect(
        router.parse('https://tore.app/event/e42')!.route, AppRoutes.eventHub);
    expect(router.parse('https://stage.tore.app/bar/b1')!.route,
        AppRoutes.barDashboard);
    expect(router.parse('https://dev.tore.app/menu/event/e42')!.route,
        AppRoutes.menu);
  });

  test('parses legacy open links and maps to rebuild routes only', () {
    expect(
        router.parse('https://app.tore.be/open?type=event&id=event_42')!.route,
        AppRoutes.eventHub);
    expect(router.parse('tore://open?type=join&id=event_42')!.route,
        AppRoutes.join);
    final qr =
        router.parse('https://app.tore.be/open?type=qr&payload=legacy_payload');
    expect(qr, isNotNull);
    expect(qr!.isQr, isTrue);
    expect(qr.qrPayload, 'legacy_payload');
  });

  test('rejects unsupported hosts/schemes', () {
    expect(router.parse('http://tore.app/event/e42'), isNull);
    expect(router.parse('https://example.com/event/e42'), isNull);
  });
}
