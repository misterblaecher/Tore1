import 'package:flutter_test/flutter_test.dart';
import 'package:tore/rebuild/models/qr_resolve.dart';
import 'package:tore/rebuild/models/rebuild_types.dart';
import 'package:tore/rebuild/models/snapshot.dart';
import 'package:tore/rebuild/routing/app_routes.dart';
import 'package:tore/rebuild/routing/qr_router.dart';
import 'package:tore/rebuild/routing/route_guards.dart';
import 'package:tore/rebuild/ui/theme/tore_theme.dart';

void main() {
  test('route guard decisions by mode and route prefix', () {
    final guards = RouteGuards();
    final snapshot = UserSnapshot(
      roles: {'USER', 'ORGA'},
      capabilities: {'can_access_orga'},
      globalModules: {},
      syncedAt: DateTime.fromMillisecondsSinceEpoch(0),
    );

    expect(guards.modeAllowed(ToreMode.orga, snapshot), isTrue);
    expect(guards.modeAllowed(ToreMode.bar, snapshot), isFalse);
    expect(
        guards.routeAllowedForMode(AppRoutes.orgaHub, ToreMode.orga), isTrue);
    expect(
        guards.routeAllowedForMode(AppRoutes.orgaHub, ToreMode.user), isFalse);
  });

  test('qr resolve type maps to expected route', () {
    final router = QrRouter();
    expect(router.targetFor(const QrResolve(valid: true, type: 'join_event')),
        AppRoutes.join);
    expect(router.targetFor(const QrResolve(valid: true, type: 'menu')),
        AppRoutes.menu);
    expect(router.targetFor(const QrResolve(valid: true, type: 'event_hub')),
        AppRoutes.eventHub);
  });

  test('theme tokens are night-first and CTA yellow is stable', () {
    expect(ToreTokens.black.toARGB32(), 0xFF050506);
    expect(ToreTokens.ruby.toARGB32(), 0xFFBA1733);
    expect(ToreTokens.yellowCta.toARGB32(), 0xFFF4C430);
  });
}
