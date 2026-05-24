import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import 'client_log.dart';

abstract class IdempotencyPersistence {
  Future<Map<String, String>> loadAll();
  Future<void> saveAll(Map<String, String> data);
  Future<void> clear();
}

class SharedPrefsIdempotencyPersistence implements IdempotencyPersistence {
  static const key = 'tore_rebuild_idempotency_v1';

  @override
  Future<Map<String, String>> loadAll() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(key);
    if (raw == null) return {};
    return (jsonDecode(raw) as Map<String, dynamic>)
        .map((k, v) => MapEntry(k, v as String));
  }

  @override
  Future<void> saveAll(Map<String, String> data) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(key, jsonEncode(data));
  }

  @override
  Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(key);
  }
}

class IdempotencyStats {
  const IdempotencyStats(
      {required this.count, this.latestIntent, this.latestKey});

  final int count;
  final String? latestIntent;
  final String? latestKey;
}

class IdempotencyResolution {
  const IdempotencyResolution({required this.key, required this.replayed});
  final String key;
  final bool replayed;
}

class IdempotencyStore {
  IdempotencyStore({required IdempotencyPersistence persistence})
      : _persistence = persistence;

  final IdempotencyPersistence _persistence;

  Future<IdempotencyResolution> keyForIntent(String intent) async {
    final map = await _persistence.loadAll();
    final existing = map[intent];
    if (existing != null)
      return IdempotencyResolution(key: existing, replayed: true);
    final generated =
        'idem_${DateTime.now().millisecondsSinceEpoch}_${intent.hashCode.abs()}';
    map[intent] = generated;
    await _persistence.saveAll(map);
    return IdempotencyResolution(key: generated, replayed: false);
  }

  Future<IdempotencyStats> stats() async {
    final map = await _persistence.loadAll();
    if (map.isEmpty) return const IdempotencyStats(count: 0);
    final latest = map.entries.last;
    return IdempotencyStats(
        count: map.length, latestIntent: latest.key, latestKey: latest.value);
  }

  Future<void> clear() => _persistence.clear();
}

class IdempotentWriter {
  IdempotentWriter({required IdempotencyStore store}) : _store = store;

  final IdempotencyStore _store;

  Future<String> write({
    required String endpoint,
    required Map<String, dynamic> body,
    required String intent,
  }) async {
    final resolution = await _store.keyForIntent(intent);
    await ClientLog.instance.log(
        resolution.replayed ? 'write.replay' : 'write.sent',
        {'path': endpoint, 'idempotency_key': resolution.key});
    final wireBody = {...body, 'idempotency_key': resolution.key};
    await Future<void>.delayed(const Duration(milliseconds: 180));
    return 'POST $endpoint\nX-Idempotency-Key: ${resolution.key}\n${jsonEncode(wireBody)}';
  }
}
