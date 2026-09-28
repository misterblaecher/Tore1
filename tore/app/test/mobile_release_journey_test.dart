import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tore/core/auth/auth_session_provider.dart';
import 'package:tore/core/network/network_state_provider.dart';
import 'package:tore/features/discovery/domain/discovery_models.dart';
import 'package:tore/features/discovery/presentation/discovery_providers.dart';
import 'package:tore/features/events/data/event_detail_repository.dart';
import 'package:tore/features/events/domain/event_public_view.dart';
import 'package:tore/features/events/presentation/event_detail_providers.dart';
import 'package:tore/features/events/presentation/event_hub_screen.dart';
import 'package:tore/features/health/presentation/health_providers.dart';
import 'package:tore/features/navigation/presentation/profile_screen.dart';
import 'package:tore/shared/cache/cache_store.dart';
import 'package:tore/tore_mvp_app.dart';

import 'support/test_network_fakes.dart';

class _GuestSession extends AuthSessionNotifier {
  _GuestSession(super.ref) : super(autoBootstrap: false) {
    state = const AuthSessionState.guest();
  }
}

class _JoinRepository extends EventDetailRepository {
  _JoinRepository() : super(Dio(), CacheStore());

  int joins = 0;

  @override
  Future<Map<String, dynamic>> joinEvent({
    required int eventId,
    required String idempotencyKey,
    String? acceptedCharterVersion,
  }) async {
    joins++;
    return {
      'event': {'id': eventId, 'name': 'Bal des sciences'},
      'modulesOn': {'menu': true},
    };
  }
}

void main() {
  testWidgets('Discovery -> Event Detail -> Join -> Hub -> Profile',
      (tester) async {
    final repository = _JoinRepository();
    final startsAt = DateTime(2030, 5, 10, 20);
    final event = DiscoveryEvent(
      id: 12,
      name: 'Bal des sciences',
      startsAt: startsAt,
      endsAt: startsAt.add(const Duration(hours: 5)),
      status: 'UPCOMING',
      eventState: 'LIVE',
      entryPriceCents: 500,
      modules: const ['menu'],
      barId: 2,
      barName: 'Reflektor',
      hostName: 'Cercle X',
    );
    final detail = EventDetailResult(
      event: EventPublicView.fromJson({
        'id': 12,
        'name': 'Bal des sciences',
        'startAt': '2030-05-10T20:00:00Z',
        'endAt': '2030-05-11T01:00:00Z',
        'eventState': 'LIVE',
        'modulesOn': ['menu'],
        'host': {'name': 'Cercle X'},
        'venue': {'barName': 'Reflektor'},
        'pricing': {'entryPriceCents': 500},
        'accessPolicy': {'visibility': 'PUBLIC'},
        'links': {},
        'flags': {'canJoin': true},
      }),
      fromCache: false,
      lastSyncAt: DateTime.now(),
    );

    await tester.pumpWidget(ProviderScope(
      overrides: [
        authSessionProvider.overrideWith((ref) => _GuestSession(ref)),
        networkStatusProvider.overrideWithValue(NetworkState.online),
        healthRepositoryProvider.overrideWithValue(FakeHealthRepository()),
        discoveryEventsProvider(const DiscoveryQuery()).overrideWith(
          (ref) async => DiscoveryResult(
            events: [event],
            fromCache: false,
            lastSyncAt: DateTime.now(),
          ),
        ),
        eventDetailProvider(12).overrideWith((ref) async => detail),
        eventDetailRepositoryProvider.overrideWithValue(repository),
      ],
      child: const MaterialApp(home: ToreMvpShell()),
    ));
    await tester.pump();
    await tester.ensureVisible(find.byKey(const ValueKey('event-card-12')));
    await tester.pump();
    await tester.tapAt(
        tester.getTopLeft(find.byKey(const ValueKey('event-card-12'))) +
            const Offset(30, 30));
    await tester.pumpAndSettle();
    expect(find.text('Détail de la soirée'), findsOneWidget);

    await tester.scrollUntilVisible(find.text('Rejoindre la soirée'), 300,
        scrollable: find.byType(Scrollable).last);
    await tester.tap(find.text('Rejoindre la soirée'));
    await tester.pump();
    expect(repository.joins, 1);
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('Ouvrir la soirée'), 300,
        scrollable: find.byType(Scrollable).last);
    await tester.tap(find.text('Ouvrir la soirée'));
    await tester.pumpAndSettle();
    expect(find.byType(EventHubScreen), findsOneWidget);

    final navigator =
        tester.state<NavigatorState>(find.byType(Navigator).first);
    navigator.pop();
    await tester.pump(const Duration(milliseconds: 300));
    navigator.pop();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.widgetWithText(NavigationDestination, 'Profil'));
    await tester.pump();
    expect(find.byType(ProfileScreen), findsOneWidget);
    expect(find.text('Mode invité'), findsOneWidget);
  });
}
