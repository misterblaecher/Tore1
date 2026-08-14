import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class CacheStore {
  CacheStore._();

  static final CacheStore _instance = CacheStore._();

  factory CacheStore() => _instance;

  Future<SharedPreferences> get _prefs async => SharedPreferences.getInstance();

  Future<void> setJson(
    String key,
    Map<String, dynamic> json, {
    Duration ttl = const Duration(minutes: 10),
  }) async {
    final expiresAt = DateTime.now().add(ttl).millisecondsSinceEpoch;
    final payload = jsonEncode(<String, dynamic>{
      'expiresAt': expiresAt,
      'value': json,
    });

    final prefs = await _prefs;
    await prefs.setString(key, payload);
  }

  Future<Map<String, dynamic>?> getJson(String key) async {
    final prefs = await _prefs;
    final raw = prefs.getString(key);
    if (raw == null || raw.isEmpty) return null;

    try {
      final decoded = jsonDecode(raw) as Map<String, dynamic>;
      final expiresAt = decoded['expiresAt'];
      if (expiresAt is num) {
        final now = DateTime.now().millisecondsSinceEpoch;
        if (expiresAt.toInt() <= now) {
          await clearKey(key);
          return null;
        }
      }

      final value = decoded['value'];
      if (value is Map<String, dynamic>) {
        return value;
      }
      if (value is Map) {
        return Map<String, dynamic>.from(value);
      }
    } catch (_) {
      await clearKey(key);
    }

    return null;
  }

  Future<void> clearKey(String key) async {
    final prefs = await _prefs;
    await prefs.remove(key);
  }

  Future<void> clearAll() async {
    final prefs = await _prefs;
    await prefs.clear();
  }

  String publicKey(String resource) => 'tore_cache.public.$resource';

  String ownerKey(String userId) => 'tore_cache.owner.$userId.profile';

  String capabilitiesKey(String userId) =>
      'tore_cache.capabilities.$userId.effective';

  String affiliationsKey(String userId) =>
      'tore_cache.affiliations.$userId.list';

  Future<void> clearPrivateForUser(String userId) async {
    final prefs = await _prefs;
    final prefixes = <String>[
      'tore_cache.owner.$userId.',
      'tore_cache.capabilities.$userId.',
      'tore_cache.affiliations.$userId.',
    ];
    final keys = prefs.getKeys().where(
          (key) => prefixes.any(key.startsWith),
        );
    for (final key in keys.toList()) {
      await prefs.remove(key);
    }
  }

  Future<void> clearAllPrivate() async {
    final prefs = await _prefs;
    const prefixes = <String>[
      'tore_cache.owner.',
      'tore_cache.capabilities.',
      'tore_cache.affiliations.',
    ];
    final keys = prefs.getKeys().where(
          (key) => prefixes.any(key.startsWith),
        );
    for (final key in keys.toList()) {
      await prefs.remove(key);
    }
    await prefs.remove('cached_me');
  }
}
