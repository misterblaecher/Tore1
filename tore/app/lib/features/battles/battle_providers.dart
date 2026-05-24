import 'dart:async';
import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../state.dart';
import '../../core/network/network_state_provider.dart';
import 'battle_models.dart';

class BattleCached<T> {
  const BattleCached({required this.data, required this.fromCache});
  final T data;
  final bool fromCache;
}

class _Cache {
  static const _ttl = Duration(hours: 24);
  Future<void> write(String k, Map<String, dynamic> p) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
        k,
        jsonEncode({
          'payload': p,
          'exp': DateTime.now().toUtc().add(_ttl).toIso8601String()
        }));
  }

  Future<Map<String, dynamic>?> read(String k) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(k);
    if (raw == null) return null;
    final d = Map<String, dynamic>.from(jsonDecode(raw) as Map);
    final exp = DateTime.tryParse((d['exp'] ?? '').toString());
    if (exp != null && exp.isBefore(DateTime.now().toUtc())) return null;
    return d['payload'] is Map
        ? Map<String, dynamic>.from(d['payload'] as Map)
        : null;
  }
}

final _cacheProvider = Provider<_Cache>((_) => _Cache());
final battlesStateProvider = StreamProvider.autoDispose
    .family<BattleCached<BattleStatePayload>, int>((ref, eventId) async* {
  final api = ref.watch(apiProvider);
  final net = ref.watch(networkStatusProvider);
  final cache = ref.watch(_cacheProvider);
  final key = 'btl_state_$eventId';
  Future<BattleCached<BattleStatePayload>?> c() async {
    final p = await cache.read(key);
    if (p == null) return null;
    return BattleCached(data: BattleStatePayload.fromJson(p), fromCache: true);
  }

  if (net == NetworkState.offline) {
    final hit = await c();
    if (hit != null) yield hit;
    return;
  }
  while (true) {
    try {
      final data = await api.getBattleState(eventId);
      await cache.write(key, data.toJson());
      yield BattleCached(data: data, fromCache: false);
    } catch (_) {
      final hit = await c();
      if (hit != null) yield hit;
    }
    await Future<void>.delayed(net == NetworkState.degraded
        ? const Duration(seconds: 5)
        : const Duration(seconds: 2));
  }
});
final battlesLeaderboardProvider = StreamProvider.autoDispose
    .family<BattleCached<BattleLeaderboard>, int>((ref, eventId) async* {
  final api = ref.watch(apiProvider);
  final net = ref.watch(networkStatusProvider);
  final cache = ref.watch(_cacheProvider);
  final key = 'btl_lb_$eventId';
  Future<BattleCached<BattleLeaderboard>?> c() async {
    final p = await cache.read(key);
    if (p == null) return null;
    return BattleCached(data: BattleLeaderboard.fromJson(p), fromCache: true);
  }

  if (net == NetworkState.offline) {
    final hit = await c();
    if (hit != null) yield hit;
    return;
  }
  while (true) {
    try {
      final data = await api.getBattleLeaderboard(eventId);
      await cache.write(key, data.toJson());
      yield BattleCached(data: data, fromCache: false);
    } catch (_) {
      final hit = await c();
      if (hit != null) yield hit;
    }
    await Future<void>.delayed(net == NetworkState.degraded
        ? const Duration(seconds: 20)
        : const Duration(seconds: 10));
  }
});
