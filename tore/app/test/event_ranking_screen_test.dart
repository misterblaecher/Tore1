import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tore/api.dart';
import 'package:tore/features/events/presentation/event_ranking_screen.dart';

void main() {
  testWidgets('ranking renders top3 when list is empty without RangeError',
      (tester) async {
    const eventId = 1;
    const result = EventRankingFetchResult(
      fromCache: false,
      payload: {
        'top3': [
          {
            'rank': 1,
            'displayName': 'Test Player',
            'score': 42,
            'stats': {'orders': 1, 'spentTickets': 2},
          }
        ],
        'list': [],
        'rulesText': 'Test rules',
      },
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          eventRankingProvider(eventId).overrideWith((ref) async => result),
        ],
        child: const MaterialApp(
          home: EventRankingScreen(eventId: eventId),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(find.text('Test Player'), findsOneWidget);
    expect(find.text('Test rules'), findsOneWidget);
  });
}
