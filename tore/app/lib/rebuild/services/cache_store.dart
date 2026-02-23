import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/event_context.dart';
import '../models/snapshot.dart';

class CacheStore {
  static const _meKey = 'tore_rebuild_me_snapshot_v1';
  static const _eventPrefix = 'tore_rebuild_event_ctx_v1_';

  String barsKey() => 'bars:v1';
  String barEventsKey(String barId, String filter) => 'bar_events:$barId:v1:$filter';
  String menuKey(String scope, String id) => 'menu:$scope:$id:v1';
  String walletKey(String scope, String id) => 'wallet:$scope:$id:v1';
  String tickerKey(String eventId) => 'ticker:$eventId:v1';
  String ordersKey(String scope, String id) => 'orders:$scope:$id:v1';
  String zonesKey(String barId) => 'zones:$barId:v1';

  Future<UserSnapshot?> loadCachedUser() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_meKey);
    if (raw == null) return null;
    return UserSnapshot.fromJson(jsonDecode(raw) as Map<String, dynamic>);
  }

  Future<EventContext?> loadCachedEvent(String eventId) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString('$_eventPrefix$eventId');
    if (raw == null) return null;
    return EventContext.fromJson(jsonDecode(raw) as Map<String, dynamic>);
  }

  Future<void> saveUser(UserSnapshot snapshot) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_meKey, jsonEncode(snapshot.toJson()));
  }

  Future<void> saveEvent(EventContext context) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('$_eventPrefix${context.eventId}', jsonEncode(context.toJson()));
  }

  Future<void> saveJson(String key, Map<String, dynamic> payload) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      key,
      jsonEncode({
        'timestamp': DateTime.now().millisecondsSinceEpoch,
        'payload': payload,
      }),
    );
  }

  Future<CachePayload?> loadJson(String key, {Duration? ttl}) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(key);
    if (raw == null) return null;
    final decoded = jsonDecode(raw) as Map<String, dynamic>;
    final ts = (decoded['timestamp'] as num?)?.toInt() ?? 0;
    final payload = (decoded['payload'] as Map?)?.cast<String, dynamic>() ?? <String, dynamic>{};
    final age = DateTime.now().difference(DateTime.fromMillisecondsSinceEpoch(ts));
    return CachePayload(payload: payload, isStale: ttl != null && age > ttl, cachedAt: DateTime.fromMillisecondsSinceEpoch(ts));
  }
}

class CachePayload {
  const CachePayload({required this.payload, required this.isStale, required this.cachedAt});

  final Map<String, dynamic> payload;
  final bool isStale;
  final DateTime cachedAt;
}
