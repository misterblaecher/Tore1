import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class OrgaEventsCache {
  OrgaEventsCache({this.ttl = const Duration(hours: 24)});

  final Duration ttl;

  String publicKey(int orgId) => 'orga_public_events_$orgId';
  String privateKey(int orgId) => 'orga_private_events_$orgId';

  Future<void> savePublic(int orgId, Map<String, dynamic> payload) => _save(publicKey(orgId), payload);
  Future<void> savePrivate(int orgId, Map<String, dynamic> payload) => _save(privateKey(orgId), payload);

  Future<(Map<String, dynamic>?, bool isStale)> readPublic(int orgId) => _read(publicKey(orgId));
  Future<(Map<String, dynamic>?, bool isStale)> readPrivate(int orgId) => _read(privateKey(orgId));

  Future<void> _save(String key, Map<String, dynamic> payload) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(key, jsonEncode({'savedAt': DateTime.now().toUtc().toIso8601String(), 'payload': payload}));
  }

  Future<(Map<String, dynamic>?, bool isStale)> _read(String key) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(key);
    if (raw == null || raw.isEmpty) return (null, true);
    final parsed = Map<String, dynamic>.from(jsonDecode(raw) as Map);
    final payload = parsed['payload'];
    if (payload is! Map) return (null, true);
    final savedAt = DateTime.tryParse(parsed['savedAt']?.toString() ?? '');
    final stale = savedAt == null || DateTime.now().toUtc().difference(savedAt.toUtc()) > ttl;
    return (Map<String, dynamic>.from(payload), stale);
  }
}
