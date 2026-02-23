import 'package:flutter_test/flutter_test.dart';
import 'package:tore/rebuild/routing/route_guards.dart';

void main() {
  test('legacy route guard blocks shell/app_shell/features surfaces', () {
    final guards = RouteGuards();

    expect(guards.isLegacyRoute('/shell'), isTrue);
    expect(guards.isLegacyRoute('/app_shell'), isTrue);
    expect(guards.isLegacyRoute('/features/menu'), isTrue);
    expect(guards.isLegacyRoute('/legacy/entry'), isTrue);
    expect(guards.isLegacyRoute('/user/home'), isFalse);
  });
}
