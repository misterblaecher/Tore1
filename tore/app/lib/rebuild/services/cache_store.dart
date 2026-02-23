import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/event_context.dart';
import '../models/snapshot.dart';

class CacheStore {
  static const _meKey = 'tore_rebuild_me_snapshot_v1';
  static const _eventPrefix = 'tore_rebuild_event_ctx_v1_';

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
}
