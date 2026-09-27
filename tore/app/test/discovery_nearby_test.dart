import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tore/features/discovery/data/nearby_location_service.dart';
import 'package:tore/features/discovery/domain/discovery_models.dart';
import 'package:tore/features/discovery/presentation/discovery_providers.dart';
import 'package:tore/features/discovery/presentation/discovery_screen.dart';

class _LocationStub extends NearbyLocationService {
  _LocationStub(this.coordinates);

  final NearbyCoordinates? coordinates;

  @override
  Future<NearbyCoordinates?> locate() async => coordinates;
}

void main() {
  final requestedQueries = <DiscoveryQuery>[];
  Widget appWith(NearbyCoordinates? coordinates) => ProviderScope(
        overrides: [
          nearbyLocationServiceProvider
              .overrideWithValue(_LocationStub(coordinates)),
          discoveryEventsProvider.overrideWith((ref, query) async {
            requestedQueries.add(query);
            return DiscoveryResult(
              events: const [],
              fromCache: false,
              lastSyncAt: DateTime.now(),
            );
          }),
        ],
        child: const MaterialApp(home: DiscoveryScreen()),
      );

  testWidgets('denied location leaves Discovery visible and unfiltered',
      (tester) async {
    await tester.pumpWidget(appWith(null));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Autour de moi · 20 km'));
    await tester.pumpAndSettle();

    final chip = tester.widget<FilterChip>(find.byType(FilterChip));
    expect(chip.selected, isFalse);
    expect(requestedQueries.last.isNearby, isFalse);
    expect(find.text('Aucune soirée ne correspond à ces filtres.'),
        findsOneWidget);
    expect(find.textContaining('Localisation indisponible'), findsOneWidget);
  });

  testWidgets('available coordinates enable the nearby request',
      (tester) async {
    await tester.pumpWidget(appWith(const NearbyCoordinates(50.64, 5.57)));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Autour de moi · 20 km'));
    await tester.pumpAndSettle();

    final chip = tester.widget<FilterChip>(find.byType(FilterChip));
    expect(chip.selected, isTrue);
    expect(
        requestedQueries.last.toQueryParameters(), containsPair('lat', 50.64));
    expect(
        requestedQueries.last.toQueryParameters(), containsPair('lng', 5.57));
    expect(requestedQueries.last.toQueryParameters(),
        containsPair('radius', 20.0));
    expect(find.text('Aucune soirée ne correspond à ces filtres.'),
        findsOneWidget);
  });
}
