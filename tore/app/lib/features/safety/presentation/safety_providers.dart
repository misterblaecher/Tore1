import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/network_state_provider.dart';
import '../../../state.dart';
import '../safety_cache.dart';
import '../safety_models.dart';

class SafetyCacheStatus {
  const SafetyCacheStatus({required this.isCached, this.lastSyncAt});

  final bool isCached;
  final DateTime? lastSyncAt;
}

class SafetyCached<T> {
  const SafetyCached({required this.data, required this.cacheStatus});

  final T data;
  final SafetyCacheStatus cacheStatus;
}

class SafetyHistoryData {
  const SafetyHistoryData({required this.items, this.buddyLastCheckin});

  final List<SafetyHistoryItem> items;
  final SafetyHistoryItem? buddyLastCheckin;

  factory SafetyHistoryData.fromJson(Map<String, dynamic> json) {
    final response = SafetyHistoryResponse.fromJson(json);
    return SafetyHistoryData(
        items: response.items, buddyLastCheckin: response.buddyLastCheckin);
  }

  Map<String, dynamic> toJson() =>
      SafetyHistoryResponse(items: items, buddyLastCheckin: buddyLastCheckin)
          .toJson();
}

final _safetyCacheProvider =
    Provider<SafetyCacheStore>((_) => const SafetyCacheStore());

final safetyStateProvider = StreamProvider.autoDispose
    .family<SafetyCached<SafetyState>, int>((ref, eventId) async* {
  final api = ref.watch(apiProvider);
  final net = ref.watch(networkStatusProvider);
  final cache = ref.watch(_safetyCacheProvider);
  final key = 'safety_state_$eventId';

  Future<SafetyCached<SafetyState>?> cached() async {
    final hit = await cache.read(key);
    if (hit == null) return null;
    return SafetyCached(
        data: SafetyState.fromJson(hit.payload),
        cacheStatus:
            SafetyCacheStatus(isCached: true, lastSyncAt: hit.lastSyncAt));
  }

  if (net == NetworkState.offline) {
    final hit = await cached();
    if (hit != null) yield hit;
    return;
  }

  while (true) {
    try {
      final state = await api.getSafetyState(eventId);
      await cache.write(key, state.toJson());
      yield SafetyCached(
        data: state,
        cacheStatus: SafetyCacheStatus(
            isCached: false, lastSyncAt: DateTime.now().toUtc()),
      );
    } catch (_) {
      final hit = await cached();
      if (hit != null) yield hit;
    }
    await Future<void>.delayed(net == NetworkState.degraded
        ? const Duration(seconds: 10)
        : const Duration(seconds: 5));
  }
});

final safetyHistoryProvider = StreamProvider.autoDispose
    .family<SafetyCached<SafetyHistoryData>, int>((ref, eventId) async* {
  final api = ref.watch(apiProvider);
  final net = ref.watch(networkStatusProvider);
  final cache = ref.watch(_safetyCacheProvider);
  final key = 'safety_history_$eventId';

  Future<SafetyCached<SafetyHistoryData>?> cached() async {
    final hit = await cache.read(key);
    if (hit == null) return null;
    return SafetyCached(
        data: SafetyHistoryData.fromJson(hit.payload),
        cacheStatus:
            SafetyCacheStatus(isCached: true, lastSyncAt: hit.lastSyncAt));
  }

  if (net == NetworkState.offline) {
    final hit = await cached();
    if (hit != null) yield hit;
    return;
  }

  try {
    final response = await api.getSafetyHistory(eventId, limit: 50);
    final data = SafetyHistoryData(
        items: response.items, buddyLastCheckin: response.buddyLastCheckin);
    await cache.write(key, data.toJson());
    yield SafetyCached(
      data: data,
      cacheStatus: SafetyCacheStatus(
          isCached: false, lastSyncAt: DateTime.now().toUtc()),
    );
  } catch (_) {
    final hit = await cached();
    if (hit != null) yield hit;
  }
});
