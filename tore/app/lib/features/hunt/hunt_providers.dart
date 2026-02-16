import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../api.dart';
import '../../core/network/network_state_provider.dart';
import '../../state.dart';
import 'hunt_models.dart';

class HuntCached<T> {
  const HuntCached({required this.data, required this.fromCache, this.lastSyncAt});
  final T data;
  final bool fromCache;
  final DateTime? lastSyncAt;
}

class HuntCacheStore {
  static const _ttl = Duration(hours: 24);

  Future<void> write(String key, Map<String, dynamic> payload) async {
    final prefs = await SharedPreferences.getInstance();
    final item = {
      'payload': payload,
      'lastSyncAt': DateTime.now().toUtc().toIso8601String(),
      'expiresAt': DateTime.now().toUtc().add(_ttl).toIso8601String(),
    };
    await prefs.setString(key, jsonEncode(item));
  }

  Future<Map<String, dynamic>?> read(String key) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(key);
    if (raw == null || raw.isEmpty) return null;
    try {
      final decoded = Map<String, dynamic>.from(jsonDecode(raw) as Map);
      final exp = DateTime.tryParse((decoded['expiresAt'] ?? '').toString());
      if (exp != null && exp.isBefore(DateTime.now().toUtc())) return null;
      return decoded;
    } catch (_) {
      return null;
    }
  }
}

final huntCacheStoreProvider = Provider<HuntCacheStore>((_) => HuntCacheStore());

final activeHuntProvider = StreamProvider.autoDispose.family<HuntCached<ActiveHunt>, int>((ref, eventId) async* {
  final api = ref.watch(apiProvider);
  final cache = ref.watch(huntCacheStoreProvider);
  final network = ref.watch(networkStatusProvider);
  final key = 'hunt_active_$eventId';

  Future<HuntCached<ActiveHunt>?> loadCache() async {
    final cached = await cache.read(key);
    final payload = cached?['payload'];
    if (payload is! Map) return null;
    return HuntCached(
      data: ActiveHunt.fromJson(Map<String, dynamic>.from(payload)),
      fromCache: true,
      lastSyncAt: DateTime.tryParse((cached?['lastSyncAt'] ?? '').toString()),
    );
  }

  if (network == NetworkState.offline) {
    final cached = await loadCache();
    if (cached != null) yield cached;
    return;
  }

  while (true) {
    try {
      final data = await api.getActiveHunt(eventId);
      await cache.write(key, data.toJson());
      yield HuntCached(data: data, fromCache: false, lastSyncAt: DateTime.now());
    } catch (_) {
      final cached = await loadCache();
      if (cached != null) yield cached;
    }
    await Future<void>.delayed(network == NetworkState.degraded ? const Duration(seconds: 5) : const Duration(seconds: 2));
  }
});

class HuntLeaderboardKey {
  const HuntLeaderboardKey({required this.eventId, required this.huntId});
  final int eventId;
  final int huntId;
}

final huntLeaderboardProvider = StreamProvider.autoDispose.family<HuntCached<HuntLeaderboard>, HuntLeaderboardKey>((ref, keyData) async* {
  final api = ref.watch(apiProvider);
  final cache = ref.watch(huntCacheStoreProvider);
  final network = ref.watch(networkStatusProvider);
  final key = 'hunt_lb_${keyData.eventId}_${keyData.huntId}';

  Future<HuntCached<HuntLeaderboard>?> loadCache() async {
    final cached = await cache.read(key);
    final payload = cached?['payload'];
    if (payload is! Map) return null;
    return HuntCached(
      data: HuntLeaderboard.fromJson(Map<String, dynamic>.from(payload)),
      fromCache: true,
      lastSyncAt: DateTime.tryParse((cached?['lastSyncAt'] ?? '').toString()),
    );
  }

  if (network == NetworkState.offline) {
    final cached = await loadCache();
    if (cached != null) yield cached;
    return;
  }

  while (true) {
    try {
      final data = await api.getHuntLeaderboard(keyData.eventId, keyData.huntId);
      await cache.write(key, data.toJson());
      yield HuntCached(data: data, fromCache: false, lastSyncAt: DateTime.now());
    } catch (_) {
      final cached = await loadCache();
      if (cached != null) yield cached;
    }
    await Future<void>.delayed(network == NetworkState.degraded ? const Duration(seconds: 10) : const Duration(seconds: 5));
  }
});
