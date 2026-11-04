import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/providers.dart';
import '../../../shared/cache/cache_providers.dart';
import '../data/discovery_repository.dart';
import '../data/nearby_location_service.dart';
import '../domain/discovery_models.dart';

final discoveryRepositoryProvider = Provider<DiscoveryRepository>((ref) {
  return DiscoveryRepository(
    ref.watch(apiClientProvider).dio,
    ref.watch(cacheStoreProvider),
  );
});

final nearbyLocationServiceProvider = Provider<NearbyLocationService>(
  (ref) => NearbyLocationService(),
);

final discoveryQueryProvider = StateProvider<DiscoveryQuery>(
  (ref) => const DiscoveryQuery(),
);

final discoveryEventsProvider =
    FutureProvider.autoDispose.family<DiscoveryResult, DiscoveryQuery>((ref, query) {
  final refresh = Timer(const Duration(seconds: 30), ref.invalidateSelf);
  ref.onDispose(refresh.cancel);
  return ref.watch(discoveryRepositoryProvider).fetchEvents(query);
});
