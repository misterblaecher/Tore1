import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/providers.dart';
import '../data/events_repository.dart';
import '../../../shared/cache/cache_providers.dart';
import '../../../shared/models/event.dart';
import '../../../shared/models/qr_pack.dart';

final eventsRepositoryProvider = Provider<EventsRepository>((ref) {
  final client = ref.watch(apiClientProvider);
  final cache = ref.watch(cacheStoreProvider);
  return EventsRepository(client.dio, cache);
});

final eventsFutureProvider = FutureProvider.family<List<Event>, int>((ref, barId) async {
  final repo = ref.watch(eventsRepositoryProvider);
  return repo.fetchEvents(barId);
});

final qrPackProvider = FutureProvider.family<QrPack, int>((ref, eventId) async {
  final repo = ref.watch(eventsRepositoryProvider);
  return repo.fetchQrPack(eventId);
});
