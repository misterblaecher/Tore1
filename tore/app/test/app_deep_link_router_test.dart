import 'package:flutter_test/flutter_test.dart';
import 'package:tore/core/routing/app_deep_link_router.dart';

void main() {
  const router = AppDeepLinkRouter();

  test('parses public event links', () {
    final link = router.parse('https://tore.app/event/42');
    expect(link, isNotNull);
    expect(link!.kind, AppDeepLinkKind.event);
    expect(link.id, 42);
  });

  test('parses custom-scheme bar links', () {
    final link = router.parse('tore://bar/7');
    expect(link, isNotNull);
    expect(link!.kind, AppDeepLinkKind.bar);
    expect(link.id, 7);
  });

  test('parses event and bar menu links', () {
    final eventMenu = router.parse('https://stage.tore.app/menu/event/12');
    expect(eventMenu, isNotNull);
    expect(eventMenu!.kind, AppDeepLinkKind.eventMenu);
    expect(eventMenu.id, 12);

    final barMenu = router.parse('https://dev.tore.app/menu/bar/8');
    expect(barMenu, isNotNull);
    expect(barMenu!.kind, AppDeepLinkKind.barMenu);
    expect(barMenu.id, 8);
  });

  test('keeps legacy app.tore.be event and join compatibility', () {
    final event =
        router.parse('https://app.tore.be/open?type=event&id=42');
    expect(event, isNotNull);
    expect(event!.kind, AppDeepLinkKind.event);
    expect(event.id, 42);

    final join = router.parse('tore://open?type=join&id=43');
    expect(join, isNotNull);
    expect(join!.kind, AppDeepLinkKind.join);
    expect(join.id, 43);
  });

  test('parses QR payload links without accepting arbitrary routes', () {
    final link = router.parse('tore://qr/abc%2Fdef');
    expect(link, isNotNull);
    expect(link!.kind, AppDeepLinkKind.qr);
    expect(link.payload, 'abc/def');
  });

  test('keeps legacy QR payload compatibility', () {
    final link = router.parse(
        'https://app.tore.be/open?type=qr&payload=signed%3Dpayload');
    expect(link, isNotNull);
    expect(link!.kind, AppDeepLinkKind.qr);
    expect(link.payload, 'signed=payload');
  });

  test('rejects unknown hosts, schemes and malformed ids', () {
    expect(router.parse('https://evil.example/event/42'), isNull);
    expect(router.parse('http://tore.app/event/42'), isNull);
    expect(router.parse('https://tore.app/event/nope'), isNull);
    expect(router.parse('https://tore.app/menu/unknown/1'), isNull);
  });
}
