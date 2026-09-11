import 'package:flutter_test/flutter_test.dart';
import 'package:tore/rebuild/models/qr_resolve.dart';
import 'package:tore/rebuild/models/rebuild_types.dart';
import 'package:tore/rebuild/models/snapshot.dart';
import 'package:tore/rebuild/routing/app_routes.dart';
import 'package:tore/rebuild/routing/qr_router.dart';
import 'package:tore/rebuild/routing/route_guards.dart';
import 'package:tore/theme/tokens.dart';

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

  test('active theme tokens are night-first and authority gold is stable', () {
    expect(ToreSemantic.bg.toARGB32(), 0xFF070607);
    expect(ToreSemantic.accentPrimary.toARGB32(), 0xFFFF2A4D);
    expect(ToreSemantic.accentAuthority.toARGB32(), 0xFFF5C400);
  });
}
