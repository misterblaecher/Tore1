import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ClientLogEntry {
  const ClientLogEntry({
    required this.ts,
    required this.event,
    required this.fields,
  });

  final DateTime ts;
  final String event;
  final Map<String, dynamic> fields;

  Map<String, dynamic> toJson() => {
        'ts': ts.toIso8601String(),
        'event': event,
        'fields': fields,
      };

  factory ClientLogEntry.fromJson(Map<String, dynamic> json) => ClientLogEntry(
        ts: DateTime.tryParse(json['ts']?.toString() ?? '') ?? DateTime.now(),
        event: json['event']?.toString() ?? 'unknown',
        fields: (json['fields'] as Map?)?.cast<String, dynamic>() ?? const {},
      );
}

class ClientLog {
  ClientLog._();

  static const _persistedTailKey = 'tore_rebuild_client_log_tail_v1';
  static const int _capacity = 250;
  static const int _tailLimit = 80;
  static final ClientLog instance = ClientLog._();

  final List<ClientLogEntry> _entries = <ClientLogEntry>[];

  List<ClientLogEntry> entries({String? filter}) {
    final rows = filter == null || filter.isEmpty ? _entries : _entries.where((e) => e.event == filter);
    return rows.toList().reversed.toList(growable: false);
  }

  Set<String> get eventTypes => _entries.map((e) => e.event).toSet();

  Future<void> hydrate() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_persistedTailKey);
    if (raw == null || raw.isEmpty) return;
    final decoded = jsonDecode(raw) as List<dynamic>;
    _entries
      ..clear()
      ..addAll(decoded.whereType<Map<String, dynamic>>().map(ClientLogEntry.fromJson));
  }

  Future<void> clear() async {
    _entries.clear();
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_persistedTailKey);
  }

  Future<void> log(String event, Map<String, dynamic> fields) async {
    final sanitized = _sanitize(fields);
    _entries.add(ClientLogEntry(ts: DateTime.now(), event: event, fields: sanitized));
    if (_entries.length > _capacity) {
      _entries.removeRange(0, _entries.length - _capacity);
    }
    await _persistTail();
    assert(() {
      debugPrint('[client-log] $event ${jsonEncode(sanitized)}');
      return true;
    }());
  }

  Map<String, dynamic> _sanitize(Map<String, dynamic> fields) {
    final blocked = {'email', 'phone', 'name', 'token', 'password', 'address'};
    return fields.map((k, v) {
      final lower = k.toLowerCase();
      if (blocked.any(lower.contains)) return MapEntry(k, '[redacted]');
      if (v is String && v.length > 180) return MapEntry(k, '${v.substring(0, 180)}...');
      return MapEntry(k, v);
    });
  }

  Future<void> _persistTail() async {
    final prefs = await SharedPreferences.getInstance();
    final tail = _entries.length <= _tailLimit ? _entries : _entries.sublist(_entries.length - _tailLimit);
    await prefs.setString(_persistedTailKey, jsonEncode(tail.map((e) => e.toJson()).toList()));
  }
}
