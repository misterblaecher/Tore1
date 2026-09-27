import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tore/features/discovery/domain/discovery_models.dart';
import 'package:tore/features/discovery/presentation/discovery_providers.dart';
import 'package:tore/features/discovery/presentation/discovery_screen.dart';
import 'package:tore/features/events/data/event_detail_repository.dart';
import 'package:tore/features/events/domain/event_public_view.dart';
import 'package:tore/features/events/presentation/event_detail_providers.dart';

void main() {
  testWidgets('Soirées opens the existing calendar screen', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          discoveryEventsProvider(const DiscoveryQuery()).overrideWith(
            (ref) async => DiscoveryResult(
              events: const [],
              fromCache: false,
              lastSyncAt: DateTime(2030, 5, 10),
            ),
          ),
        ],
        child: const MaterialApp(home: DiscoveryScreen()),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    await tester.tap(find.byKey(const ValueKey('calendar-entry')));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));

    expect(find.text('Calendrier guindaille'), findsOneWidget);
    expect(find.text('Aujourd’hui'), findsOneWidget);
    expect(find.text('Semaine'), findsOneWidget);
    expect(find.text('Mois'), findsOneWidget);
  });

  testWidgets('event card opens Event Detail before any join action',
      (tester) async {
    final now = DateTime(2030, 5, 10, 20);
    final event = DiscoveryEvent(
      id: 12,
      name: 'Bal des sciences',
      startsAt: now,
      endsAt: now.add(const Duration(hours: 5)),
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
        'venue': {'barId': 2, 'barName': 'Reflektor'},
        'pricing': {'entryPriceCents': 500},
        'accessPolicy': {'visibility': 'PUBLIC'},
        'links': {},
        'flags': {'canJoin': true},
      }),
      fromCache: false,
      lastSyncAt: DateTime.now(),
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          eventDetailProvider(12).overrideWith((ref) async => detail),
        ],
        child: MaterialApp(
          home: Scaffold(body: DiscoveryEventCard(event: event)),
        ),
      ),
    );

    await tester.tap(find.byKey(const ValueKey('event-card-12')));
    await tester.pumpAndSettle();

    expect(find.text('Détail de la soirée'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('Rejoindre la soirée'),
      300,
      scrollable: find.byType(Scrollable).last,
    );
    expect(find.text('Rejoindre la soirée'), findsOneWidget);
  });
}
