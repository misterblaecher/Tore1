import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/providers.dart';
import '../../../shared/models/bar.dart';
import '../../../shared/models/event_summary.dart';
import '../data/bars_repository.dart';

final barsRepositoryProvider = Provider<BarsRepository>((ref) {
  final client = ref.watch(apiClientProvider);
  return BarsRepository(client.dio);
});

final barsFutureProvider = FutureProvider<List<Bar>>((ref) async {
  final repo = ref.watch(barsRepositoryProvider);
  return repo.fetchBars();
});

final barEventsProvider =
    FutureProvider.family<List<EventSummary>, int>((ref, barId) async {
  final repo = ref.watch(barsRepositoryProvider);
  return repo.getBarEvents(barId);
});
