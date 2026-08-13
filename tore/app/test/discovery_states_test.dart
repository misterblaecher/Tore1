import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tore/features/discovery/domain/discovery_models.dart';
import 'package:tore/features/discovery/presentation/discovery_providers.dart';
import 'package:tore/features/discovery/presentation/discovery_screen.dart';

void main() {
  Widget appWith(Future<DiscoveryResult> Function(Ref) loader) => ProviderScope(
        overrides: [
          discoveryEventsProvider(const DiscoveryQuery()).overrideWith(loader),
        ],
        child: const MaterialApp(home: DiscoveryScreen()),
      );

  testWidgets('empty API response renders no event and no fixture',
      (tester) async {
    await tester.pumpWidget(appWith((ref) async => DiscoveryResult(
          events: const [],
          fromCache: false,
          lastSyncAt: DateTime.now(),
        )));
    await tester.pumpAndSettle();

    expect(find.text('Aucune soirée ne correspond à ces filtres.'),
        findsOneWidget);
    expect(find.byType(DiscoveryEventCard), findsNothing);
    expect(find.text('Afond Night'), findsNothing);
  });

  testWidgets('network error renders an explicit retry state', (tester) async {
    await tester.pumpWidget(appWith((ref) => Future<DiscoveryResult>.error(
          Exception('network down'),
        )));
    await tester.pumpAndSettle();

    expect(find.text('Impossible de charger les soirées.'), findsOneWidget);
    expect(find.text('Réessayer'), findsOneWidget);
  });
}
