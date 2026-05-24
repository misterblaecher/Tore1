import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/providers.dart';
import '../../../shared/cache/cache_providers.dart';
import '../data/event_cost_service.dart';
import '../data/event_report_service.dart';

final eventReportServiceProvider = Provider<EventReportService>((ref) {
  final client = ref.watch(apiClientProvider);
  final cache = ref.watch(cacheStoreProvider);
  return EventReportService(client.dio, cache);
});

final eventCostServiceProvider = Provider<EventCostService>((ref) {
  final client = ref.watch(apiClientProvider);
  return EventCostService(client.dio);
});

final eventReportProvider =
    FutureProvider.family<EventReportFetchResult, int>((ref, eventId) async {
  final service = ref.watch(eventReportServiceProvider);
  return service.fetchReport(eventId);
});
