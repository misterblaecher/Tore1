import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

abstract class IdempotencyPersistence {
  Future<Map<String, String>> loadAll();
  Future<void> saveAll(Map<String, String> data);
}

class SharedPrefsIdempotencyPersistence implements IdempotencyPersistence {
  static const key = 'tore_rebuild_idempotency_v1';

  @override
  Future<Map<String, String>> loadAll() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(key);
    if (raw == null) return {};
    return (jsonDecode(raw) as Map<String, dynamic>).map((k, v) => MapEntry(k, v as String));
  }

  @override
  Future<void> saveAll(Map<String, String> data) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(key, jsonEncode(data));
  }
}

class IdempotencyStore {
  IdempotencyStore({required IdempotencyPersistence persistence}) : _persistence = persistence;

  final IdempotencyPersistence _persistence;

  Future<String> keyForIntent(String intent) async {
    final map = await _persistence.loadAll();
    final existing = map[intent];
    if (existing != null) return existing;
    final generated = 'idem_${DateTime.now().millisecondsSinceEpoch}_${intent.hashCode.abs()}';
    map[intent] = generated;
    await _persistence.saveAll(map);
    return generated;
  }
}

class IdempotentWriter {
  IdempotentWriter({required IdempotencyStore store}) : _store = store;

  final IdempotencyStore _store;

  Future<String> write({
    required String endpoint,
    required Map<String, dynamic> body,
    required String intent,
  }) async {
    final key = await _store.keyForIntent(intent);
    final wireBody = {...body, 'idempotency_key': key};
    await Future<void>.delayed(const Duration(milliseconds: 180));
    return 'POST $endpoint\nX-Idempotency-Key: $key\n${jsonEncode(wireBody)}';
  }
}
