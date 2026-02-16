import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class CacheStatus {
  const CacheStatus({required this.isCached, this.lastSyncAt, required this.isStale});

  final bool isCached;
  final DateTime? lastSyncAt;
  final bool isStale;
}

class GlossaryCacheEntry {
  const GlossaryCacheEntry({required this.payload, required this.status});

  final Map<String, dynamic> payload;
  final CacheStatus status;
}

class GlossaryCacheStore {
  const GlossaryCacheStore();

  static const Duration ttl = Duration(days: 7);

  String publicTermsKey(int committeeId, Map<String, dynamic> filters) => 'glossary_public_terms_${committeeId}_${_hashFilters(filters)}';
  String privateTermsKey(int committeeId, Map<String, dynamic> filters) => 'glossary_private_terms_${committeeId}_${_hashFilters(filters)}';

  static String publicSettingsKey(int committeeId) => 'glossary_public_settings_$committeeId';
  static String privateSettingsKey(int committeeId) => 'glossary_private_settings_$committeeId';
  static const String publicCommitteesKey = 'glossary_committees_public';

  Future<void> write(String key, Map<String, dynamic> payload) async {
    final prefs = await SharedPreferences.getInstance();
    final now = DateTime.now().toUtc();
    await prefs.setString(
      key,
      jsonEncode({'payload': payload, 'lastSyncAt': now.toIso8601String(), 'ttlSeconds': ttl.inSeconds}),
    );
  }

  Future<GlossaryCacheEntry?> read(String key) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(key);
    if (raw == null || raw.isEmpty) return null;
    final decoded = Map<String, dynamic>.from(jsonDecode(raw) as Map);
    final payload = decoded['payload'];
    if (payload is! Map) return null;
    final lastSyncAt = DateTime.tryParse((decoded['lastSyncAt'] ?? '').toString())?.toUtc();
    final stale = lastSyncAt == null || DateTime.now().toUtc().isAfter(lastSyncAt.add(ttl));
    return GlossaryCacheEntry(
      payload: Map<String, dynamic>.from(payload),
      status: CacheStatus(isCached: true, lastSyncAt: lastSyncAt, isStale: stale),
    );
  }

  String _hashFilters(Map<String, dynamic> filters) {
    final encoded = jsonEncode(filters);
    return encoded.hashCode.abs().toString();
  }
}
