import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

class EntryQueueItem {
  EntryQueueItem({
    required this.id,
    required this.eventId,
    required this.scannedAt,
    required this.idempotencyKey,
    this.type = 'CHECKIN',
    this.rawQr,
    this.delta = 1,
    this.reason,
    this.note,
    this.status = 'pending',
    this.lastError,
  });

  final String id;
  final int eventId;
  final String type;
  final String? rawQr;
  final DateTime scannedAt;
  final String idempotencyKey;
  final int delta;
  final String? reason;
  final String? note;
  String status;
  String? lastError;

  Map<String, dynamic> toJson() => {
        'id': id,
        'eventId': eventId,
        'type': type,
        'rawQr': rawQr,
        'scannedAt': scannedAt.toIso8601String(),
        'idempotencyKey': idempotencyKey,
        'delta': delta,
        'reason': reason,
        'note': note,
        'status': status,
        'lastError': lastError,
      };

  static EntryQueueItem fromJson(Map<String, dynamic> json) => EntryQueueItem(
        id: (json['id'] ?? '').toString(),
        eventId: (json['eventId'] ?? 0) as int,
        type: (json['type'] ?? 'CHECKIN').toString().toUpperCase(),
        rawQr: json['rawQr']?.toString(),
        scannedAt: DateTime.tryParse((json['scannedAt'] ?? '').toString()) ?? DateTime.now(),
        idempotencyKey: (json['idempotencyKey'] ?? '').toString(),
        delta: (json['delta'] ?? 1) as int,
        reason: json['reason']?.toString(),
        note: json['note']?.toString(),
        status: (json['status'] ?? 'pending').toString(),
        lastError: json['lastError']?.toString(),
      );
}

class EntryOfflineQueueStore {
  static const _key = 'entry_offline_queue_v1';

  Future<List<EntryQueueItem>> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key);
    if (raw == null || raw.isEmpty) return [];
    final list = (jsonDecode(raw) as List<dynamic>?) ?? const [];
    return list
        .map((row) => EntryQueueItem.fromJson(Map<String, dynamic>.from(row as Map)))
        .where((item) => item.id.isNotEmpty && item.idempotencyKey.isNotEmpty)
        .toList();
  }

  Future<void> save(List<EntryQueueItem> items) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, jsonEncode(items.map((e) => e.toJson()).toList()));
  }
}

final entryOfflineQueueStoreProvider = Provider<EntryOfflineQueueStore>((ref) {
  return EntryOfflineQueueStore();
});
