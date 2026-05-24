import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class OrgaPostsCache {
  OrgaPostsCache({this.ttl = const Duration(hours: 24)});

  final Duration ttl;

  String _key(int orgId) => 'orga_posts_cache_$orgId';

  Future<void> save(int orgId, List<Map<String, dynamic>> items) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
        _key(orgId),
        jsonEncode(
            {'savedAt': DateTime.now().toIso8601String(), 'items': items}));
  }

  Future<(List<Map<String, dynamic>>, bool isStale)> read(int orgId) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key(orgId));
    if (raw == null || raw.isEmpty) return (<Map<String, dynamic>>[], true);
    final parsed = Map<String, dynamic>.from(jsonDecode(raw) as Map);
    final List<Map<String, dynamic>> items =
        ((parsed['items'] as List?) ?? const <dynamic>[])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
    final savedAt = DateTime.tryParse(parsed['savedAt']?.toString() ?? '');
    if (savedAt == null) return (items, true);
    final isStale = DateTime.now().difference(savedAt) > ttl;
    return (items, isStale);
  }
}
