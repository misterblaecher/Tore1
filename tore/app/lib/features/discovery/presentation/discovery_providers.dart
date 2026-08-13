import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/providers.dart';
import '../../../shared/cache/cache_providers.dart';
import '../data/discovery_repository.dart';
import '../domain/discovery_models.dart';

final discoveryRepositoryProvider = Provider<DiscoveryRepository>((ref) {
  return DiscoveryRepository(
    ref.watch(apiClientProvider).dio,
    ref.watch(cacheStoreProvider),
  );
});

final discoveryQueryProvider = StateProvider<DiscoveryQuery>(
  (ref) => const DiscoveryQuery(),
);

final discoveryEventsProvider =
    FutureProvider.family<DiscoveryResult, DiscoveryQuery>((ref, query) {
  return ref.watch(discoveryRepositoryProvider).fetchEvents(query);
});
