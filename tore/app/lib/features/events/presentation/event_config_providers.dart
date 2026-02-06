import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/providers.dart';
import '../../events/data/event_config_service.dart';
import '../../../shared/models/event_config.dart';

final eventConfigServiceProvider = Provider<EventConfigService>((ref) {
  final client = ref.watch(apiClientProvider);
  return EventConfigService(client.dio);
});

final eventConfigProvider = FutureProvider.family<EventConfig, int>((ref, eventId) async {
  final service = ref.watch(eventConfigServiceProvider);
  return service.fetchEventConfig(eventId);
});
