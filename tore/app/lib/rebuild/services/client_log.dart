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
    final sanitized = scrubJsonMap(fields);
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

  Future<void> _persistTail() async {
    final prefs = await SharedPreferences.getInstance();
    final tail = _entries.length <= _tailLimit ? _entries : _entries.sublist(_entries.length - _tailLimit);
    await prefs.setString(_persistedTailKey, jsonEncode(tail.map((e) => e.toJson()).toList()));
  }
}

String scrubUrlQueryParams(String rawUrl) {
  final uri = Uri.tryParse(rawUrl);
  if (uri == null || !uri.hasQuery) return _redactFreeText(rawUrl);
  final scrubbed = <String, String>{};
  for (final entry in uri.queryParameters.entries) {
    final key = entry.key.toLowerCase();
    scrubbed[entry.key] = _isSensitiveKey(key) ? '[redacted]' : _redactFreeText(entry.value);
  }
  final out = uri.replace(queryParameters: scrubbed);
  return out.toString();
}

Map<String, dynamic> scrubJsonMap(Map<String, dynamic> fields) {
  return fields.map((k, v) {
    final keyLower = k.toLowerCase();
    if (_isSensitiveKey(keyLower)) return MapEntry(k, '[redacted]');
    if (v is Map<String, dynamic>) return MapEntry(k, scrubJsonMap(v));
    if (v is Map) return MapEntry(k, scrubJsonMap(v.cast<String, dynamic>()));
    if (v is List) {
      return MapEntry(
        k,
        v
            .map((item) => item is Map<String, dynamic> ? scrubJsonMap(item) : item is String ? _redactFreeText(item) : item)
            .toList(growable: false),
      );
    }
    if (keyLower.contains('user') && v is String) return MapEntry(k, _maskIdentifier(v));
    if (v is String) {
      final redacted = keyLower.contains('url') ? scrubUrlQueryParams(v) : _redactFreeText(v);
      if (redacted.length > 180) return MapEntry(k, '${redacted.substring(0, 180)}...');
      return MapEntry(k, redacted);
    }
    return MapEntry(k, v);
  });
}

bool _isSensitiveKey(String lowerKey) {
  const blocked = <String>{'email', 'phone', 'name', 'token', 'password', 'address', 'authorization', 'auth', 'jwt', 'secret', 'bearer', 'key'};
  return blocked.any(lowerKey.contains);
}

String _maskIdentifier(String value) {
  final clean = value.trim();
  if (clean.length <= 6) return '[redacted]';
  return '${clean.substring(0, 3)}***${clean.substring(clean.length - 3)}';
}

String _redactFreeText(String input) {
  var out = input;
  out = out.replaceAll(RegExp(r'Bearer\s+[A-Za-z0-9\-\._~\+\/=]+', caseSensitive: false), 'Bearer [redacted]');
  out = out.replaceAll(RegExp(r'([?&](token|auth|key|authorization)=)[^&\s]+', caseSensitive: false), r'$1[redacted]');
  out = out.replaceAll(RegExp(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', caseSensitive: false), '[redacted-email]');
  out = out.replaceAll(RegExp(r'\+?[0-9][0-9\s().-]{7,}[0-9]'), '[redacted-phone]');
  out = out.replaceAll(RegExp(r'eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+'), '[redacted-jwt]');
  return out;
}
