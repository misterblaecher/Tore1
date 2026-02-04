import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/providers.dart';
import '../data/events_repository.dart';
import '../../../shared/models/event.dart';

final eventsRepositoryProvider = Provider<EventsRepository>((ref) {
  final client = ref.watch(apiClientProvider);
  return EventsRepository(client.dio);
});

final eventsFutureProvider = FutureProvider.family<List<Event>, int>((ref, barId) async {
  final repo = ref.watch(eventsRepositoryProvider);
  return repo.fetchEvents(barId);
});
