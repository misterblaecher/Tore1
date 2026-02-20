import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

const int communityExplorerDebounceMs = 350;

String communityExplorerHashParams(Map<String, String> params) {
  final entries = params.entries.toList()..sort((a, b) => a.key.compareTo(b.key));
  final normalized = entries.map((e) => '${e.key}=${e.value}').join('&');
  var hash = 0x811c9dc5;
  for (final code in normalized.codeUnits) {
    hash ^= code;
    hash = (hash * 0x01000193) & 0xffffffff;
  }
  return hash.toRadixString(16).padLeft(8, '0');
}

class CommunityExplorerCache {
  CommunityExplorerCache({this.ttl = const Duration(hours: 24)});

  final Duration ttl;

  String _key(Map<String, String> params) => 'community_explorer_${communityExplorerHashParams(params)}';

  Future<void> save(Map<String, String> params, Map<String, dynamic> payload) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      _key(params),
      jsonEncode({'savedAt': DateTime.now().toIso8601String(), 'payload': payload}),
    );
  }

  Future<({Map<String, dynamic>? payload, bool isStale, DateTime? lastSyncAt})> read(Map<String, String> params) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key(params));
    if (raw == null || raw.isEmpty) return (payload: null, isStale: true, lastSyncAt: null);
    final parsed = Map<String, dynamic>.from(jsonDecode(raw) as Map);
    final payload = Map<String, dynamic>.from((parsed['payload'] as Map?) ?? const <String, dynamic>{});
    final savedAt = DateTime.tryParse(parsed['savedAt']?.toString() ?? '');
    if (savedAt == null) return (payload: payload, isStale: true, lastSyncAt: null);
    return (payload: payload, isStale: DateTime.now().difference(savedAt) > ttl, lastSyncAt: savedAt);
  }
}
