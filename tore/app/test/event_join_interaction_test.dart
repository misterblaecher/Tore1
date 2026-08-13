import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tore/core/auth/auth_session_provider.dart';
import 'package:tore/core/network/network_state_provider.dart';
import 'package:tore/features/events/data/event_detail_repository.dart';
import 'package:tore/features/events/domain/event_public_view.dart';
import 'package:tore/features/events/presentation/event_detail_providers.dart';
import 'package:tore/features/events/presentation/event_detail_screen.dart';
import 'package:tore/shared/cache/cache_store.dart';

class _TestSessionNotifier extends AuthSessionNotifier {
  _TestSessionNotifier(super.ref, AuthSessionState initial) {
    state = initial;
  }

  @override
  Future<void> bootstrap() async {}

  @override
  Future<void> continueAsGuest() async {}

  @override
  Future<void> loginWithEmail(
      {required String email, required String token}) async {}

  @override
  Future<void> loginWithGoogle() async {}

  @override
  Future<void> logout() async {}

  @override
  Future<void> markUnauthenticated() async {}

  @override
  Future<void> refreshSession() async {}
}

class _FakeEventDetailRepository extends EventDetailRepository {
  _FakeEventDetailRepository(this.completer) : super(Dio(), CacheStore());

  final Completer<Map<String, dynamic>> completer;
  int joinCalls = 0;

  @override
  Future<Map<String, dynamic>> joinEvent({
    required int eventId,
    required String idempotencyKey,
    String? acceptedCharterVersion,
  }) {
    joinCalls += 1;
    return completer.future;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

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

  Future<void> pumpDetail(
    WidgetTester tester, {
    required AuthSessionState session,
    required NetworkState network,
    required EventDetailRepository repository,
  }) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authSessionProvider.overrideWith(
            (ref) => _TestSessionNotifier(ref, session),
          ),
          networkStatusProvider.overrideWithValue(network),
          eventDetailRepositoryProvider.overrideWithValue(repository),
          eventDetailProvider(12).overrideWith((ref) async => detail),
        ],
        child: const MaterialApp(home: EventDetailScreen(eventId: 12)),
      ),
    );
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('Rejoindre la soirée'), 300);
  }

  testWidgets('join ignores a second tap while the real write is pending',
      (tester) async {
    final completer = Completer<Map<String, dynamic>>();
    final repository = _FakeEventDetailRepository(completer);
    await pumpDetail(
      tester,
      session: const AuthSessionState.guest(),
      network: NetworkState.online,
      repository: repository,
    );

    final button = find.text('Rejoindre la soirée');
    await tester.tap(button);
    await tester.tap(button, warnIfMissed: false);
    await tester.pump();

    expect(repository.joinCalls, 1);
    completer.complete({
      'event': {'id': 12, 'name': 'Bal des sciences'},
      'modulesOn': {'menu': true},
    });
    await tester.pumpAndSettle();
    expect(find.text('Ouvrir la soirée'), findsOneWidget);
  });

  testWidgets('guest session can execute the real join repository boundary',
      (tester) async {
    final completer = Completer<Map<String, dynamic>>();
    final repository = _FakeEventDetailRepository(completer);
    await pumpDetail(
      tester,
      session: const AuthSessionState.guest(),
      network: NetworkState.online,
      repository: repository,
    );

    await tester.tap(find.text('Rejoindre la soirée'));
    await tester.pump();
    expect(repository.joinCalls, 1);

    completer.complete({
      'event': {'id': 12, 'name': 'Bal des sciences'},
      'modulesOn': {'menu': true},
    });
    await tester.pumpAndSettle();
    expect(find.text('Ouvrir la soirée'), findsOneWidget);
  });

  testWidgets('join is blocked offline without calling the repository',
      (tester) async {
    final completer = Completer<Map<String, dynamic>>();
    final repository = _FakeEventDetailRepository(completer);
    await pumpDetail(
      tester,
      session: const AuthSessionState.guest(),
      network: NetworkState.offline,
      repository: repository,
    );

    await tester.tap(find.text('Rejoindre la soirée'));
    await tester.pump();

    expect(repository.joinCalls, 0);
    expect(find.textContaining('nécessite une connexion'), findsOneWidget);
  });

  testWidgets('join requires a session before any write', (tester) async {
    final completer = Completer<Map<String, dynamic>>();
    final repository = _FakeEventDetailRepository(completer);
    await pumpDetail(
      tester,
      session: const AuthSessionState.unauthenticated(),
      network: NetworkState.online,
      repository: repository,
    );

    await tester.tap(find.text('Rejoindre la soirée'));
    await tester.pumpAndSettle();

    expect(repository.joinCalls, 0);
    expect(find.text('Connecte-toi pour continuer'), findsOneWidget);
  });
}
