import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class SafetyCacheEntry {
  const SafetyCacheEntry({required this.payload, this.lastSyncAt});

  final Map<String, dynamic> payload;
  final DateTime? lastSyncAt;
}

class SafetyCacheStore {
  const SafetyCacheStore();

  static const Duration ttl = Duration(hours: 24);

  Future<void> write(String key, Map<String, dynamic> payload) async {
    final prefs = await SharedPreferences.getInstance();
    final now = DateTime.now().toUtc();
    await prefs.setString(
      key,
      jsonEncode({
        'payload': payload,
        'exp': now.add(ttl).toIso8601String(),
        'lastSyncAt': now.toIso8601String(),
      }),
    );
  }

  Future<SafetyCacheEntry?> read(String key) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(key);
    if (raw == null || raw.isEmpty) return null;
    final decoded = Map<String, dynamic>.from(jsonDecode(raw) as Map);
    final exp = DateTime.tryParse((decoded['exp'] ?? '').toString())?.toUtc();
    if (exp != null && exp.isBefore(DateTime.now().toUtc())) return null;
    final payload = decoded['payload'];
    if (payload is! Map) return null;
    return SafetyCacheEntry(
      payload: Map<String, dynamic>.from(payload),
      lastSyncAt: DateTime.tryParse((decoded['lastSyncAt'] ?? '').toString())?.toUtc(),
    );
  }
}
