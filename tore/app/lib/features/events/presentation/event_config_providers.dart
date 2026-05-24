import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/providers.dart';
import '../../events/data/event_config_service.dart';
import '../../../shared/cache/cache_providers.dart';
import '../../../shared/models/event_config.dart';

final eventConfigServiceProvider = Provider<EventConfigService>((ref) {
  final client = ref.watch(apiClientProvider);
  final cache = ref.watch(cacheStoreProvider);
  return EventConfigService(client.dio, cache);
});

final eventConfigProvider =
    FutureProvider.family<EventConfig, int>((ref, eventId) async {
  final service = ref.watch(eventConfigServiceProvider);
  return service.fetchEventConfig(eventId);
});
