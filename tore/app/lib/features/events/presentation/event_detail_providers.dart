import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/providers.dart';
import '../../../shared/cache/cache_providers.dart';
import '../data/event_detail_repository.dart';

final eventDetailRepositoryProvider = Provider<EventDetailRepository>((ref) {
  return EventDetailRepository(
    ref.watch(apiClientProvider).dio,
    ref.watch(cacheStoreProvider),
  );
});

final eventDetailProvider =
    FutureProvider.family<EventDetailResult, int>((ref, eventId) {
  return ref.watch(eventDetailRepositoryProvider).fetchEvent(eventId);
});
