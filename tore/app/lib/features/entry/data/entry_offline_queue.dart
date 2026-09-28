import 'dart:async';
import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/qr/qr_parser.dart';
import '../../../core/qr/qr_validator.dart';
import 'entry_service.dart';

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

  bool get isPending => status == 'pending';
  bool get isFailed => status == 'failed';

  EntryQueueItem copyWith(
          {String? status, String? lastError, bool clearLastError = false}) =>
      EntryQueueItem(
        id: id,
        eventId: eventId,
        type: type,
        rawQr: rawQr,
        scannedAt: scannedAt,
        idempotencyKey: idempotencyKey,
        delta: delta,
        reason: reason,
        note: note,
        status: status ?? this.status,
        lastError: clearLastError ? null : (lastError ?? this.lastError),
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'eventId': eventId,
        'type': type,
        if (type == 'CHECKIN') 'rawQr': rawQr,
        'scannedAt': scannedAt.toIso8601String(),
        'idempotencyKey': idempotencyKey,
        if (type == 'MANUAL') 'delta': delta,
        if (type == 'MANUAL') 'reason': reason,
        if (type == 'MANUAL' && note != null) 'note': note,
        'status': status,
        if (lastError != null) 'lastError': lastError,
      };

  static EntryQueueItem fromJson(Map<String, dynamic> json) => EntryQueueItem(
        id: (json['id'] ?? '').toString(),
        eventId: (json['eventId'] ?? 0) as int,
        type: (json['type'] ?? 'CHECKIN').toString().toUpperCase(),
        rawQr: json['rawQr']?.toString(),
        scannedAt: DateTime.tryParse((json['scannedAt'] ?? '').toString()) ??
            DateTime.now(),
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
  static const pendingTtl = Duration(days: 7);
  static const failedTtl = Duration(days: 14);

  Future<List<EntryQueueItem>> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key);
    if (raw == null || raw.isEmpty) return [];
    final list = (jsonDecode(raw) as List<dynamic>?) ?? const [];
    final items = list
        .map((row) =>
            EntryQueueItem.fromJson(Map<String, dynamic>.from(row as Map)))
        .where((item) => item.id.isNotEmpty && item.idempotencyKey.isNotEmpty)
        .toList();
    final kept = items.where((item) {
      final age = DateTime.now().difference(item.scannedAt);
      return item.status != 'sent' &&
          age < (item.isFailed ? failedTtl : pendingTtl);
    }).toList();
    if (kept.length != items.length) await save(kept);
    return kept;
  }

  Future<void> save(List<EntryQueueItem> items) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
        _key, jsonEncode(items.map((e) => e.toJson()).toList()));
  }
}

final entryOfflineQueueStoreProvider = Provider<EntryOfflineQueueStore>((ref) {
  return EntryOfflineQueueStore();
});

final entryOfflineQueueProvider = Provider<EntryOfflineQueue>((ref) {
  return EntryOfflineQueue(
    store: ref.watch(entryOfflineQueueStoreProvider),
    service: ref.watch(entryServiceProvider),
    parser: ref.watch(qrParserProvider),
    validator: ref.watch(qrValidatorProvider),
  );
});

class EntryQueueSyncResult {
  const EntryQueueSyncResult(
      {required this.sent, required this.failed, required this.pending});
  final int sent;
  final int failed;
  final int pending;
}

class EntryOfflineQueue {
  EntryOfflineQueue(
      {required this.store,
      required this.service,
      required this.parser,
      required this.validator});

  final EntryOfflineQueueStore store;
  final EntryService service;
  final QrParser parser;
  final QrValidator validator;
  final Set<String> _recentQrHashes = {};
  Future<void> _writeTail = Future.value();

  Future<T> _write<T>(Future<T> Function() action) async {
    final previous = _writeTail;
    final done = Completer<void>();
    _writeTail = done.future;
    await previous;
    try {
      return await action();
    } finally {
      done.complete();
    }
  }

  String _qrKey(int eventId, String rawQr) =>
      '$eventId:${sha256.convert(utf8.encode(rawQr.trim()))}';

  Future<bool> hasQr(int eventId, String rawQr) async {
    if (_recentQrHashes.contains(_qrKey(eventId, rawQr))) return true;
    final items = await load();
    return items.any((item) =>
        item.type == 'CHECKIN' &&
        item.eventId == eventId &&
        item.rawQr?.trim() == rawQr.trim());
  }

  void recordCheckedQr(int eventId, String rawQr) {
    _recentQrHashes.add(_qrKey(eventId, rawQr));
    if (_recentQrHashes.length > 1000)
      _recentQrHashes.remove(_recentQrHashes.first);
  }

  Future<List<EntryQueueItem>> load() async {
    await _writeTail;
    return store.load();
  }

  Future<bool> enqueue(EntryQueueItem item) => _write(() async {
        final items = await store.load();
        if (items.any((e) =>
                e.id == item.id ||
                e.idempotencyKey == item.idempotencyKey ||
                (item.type == 'CHECKIN' &&
                    e.type == 'CHECKIN' &&
                    e.eventId == item.eventId &&
                    e.rawQr?.trim() == item.rawQr?.trim())) ||
            (item.rawQr != null &&
                _recentQrHashes.contains(_qrKey(item.eventId, item.rawQr!)))) {
          return false;
        }
        await store.save([...items, item]);
        return true;
      });

  Future<void> _remove(String id) => _write(() async {
        final items = await store.load();
        items.removeWhere((item) => item.id == id);
        await store.save(items);
      });

  Future<void> _fail(String id, String reason) => _write(() async {
        final items = await store.load();
        final index = items.indexWhere((item) => item.id == id);
        if (index < 0) return;
        items[index] =
            items[index].copyWith(status: 'failed', lastError: reason);
        await store.save(items);
      });

  Future<EntryQueueSyncResult> replay() async {
    final items = await load();
    var sent = 0;
    var failed = 0;
    for (var index = 0; index < items.length; index++) {
      final item = items[index];
      if (!item.isPending) continue;
      try {
        if (item.type == 'MANUAL') {
          await service.manualIncrement(
              eventId: item.eventId,
              delta: item.delta,
              reason: item.reason ?? 'offline',
              note: item.note,
              idempotencyKey: item.idempotencyKey);
        } else {
          final validation = await validator.validate(
            parser.parse(item.rawQr ?? ''),
            requireServerVerification: true,
          );
          if (validation.isPending) break;
          if (!validation.isOk) {
            await _fail(
                item.id, validation.reason ?? 'QR refusé par le serveur');
            failed++;
            continue;
          }
          await service.checkin(
              eventId: item.eventId,
              rawQr: item.rawQr ?? '',
              deviceId: 'orga-mobile',
              idempotencyKey: item.idempotencyKey,
              scannedAt: item.scannedAt);
          recordCheckedQr(item.eventId, item.rawQr ?? '');
        }
        await _remove(item.id);
        sent++;
      } catch (error) {
        if (EntryService.isPermanentWriteFailure(error)) {
          await _fail(item.id, EntryService.describeWriteFailure(error));
          failed++;
          continue;
        }
        break;
      }
    }
    return EntryQueueSyncResult(
        sent: sent,
        failed: failed,
        pending: (await load()).where((item) => item.isPending).length);
  }

  Future<void> retry(String id) => _write(() async {
        final items = await store.load();
        final index = items.indexWhere((item) => item.id == id);
        if (index < 0) return;
        items[index] =
            items[index].copyWith(status: 'pending', clearLastError: true);
        await store.save(items);
      });
}
