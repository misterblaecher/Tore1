import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/network/error_mapper.dart';
import '../data/entry_service.dart';

class EntryModeScreen extends ConsumerStatefulWidget {
  const EntryModeScreen({super.key, required this.eventId});

  final int? eventId;

  @override
  ConsumerState<EntryModeScreen> createState() => _EntryModeScreenState();
}

class _EntryModeScreenState extends ConsumerState<EntryModeScreen> {
  static const _queueKey = 'entry_queue_v1';
  static const _deviceIdKey = 'entry_device_id_v1';

  int _total = 0;
  int _lastHour = 0;
  bool _loading = true;
  bool _flushing = false;
  String? _deviceId;
  final List<_EntryAction> _history = [];

  @override
  void initState() {
    super.initState();
    _loadInitial();
  }

  Future<void> _loadInitial() async {
    final eventId = widget.eventId;
    if (eventId == null) {
      setState(() => _loading = false);
      return;
    }

    final prefs = await SharedPreferences.getInstance();
    final deviceId = _getOrCreateDeviceId(prefs);
    _deviceId = deviceId;

    await _refreshStats();
    await _refreshLogs();
    await _flushQueue();
    if (mounted) {
      setState(() => _loading = false);
    }
  }

  String _getOrCreateDeviceId(SharedPreferences prefs) {
    final existing = prefs.getString(_deviceIdKey);
    if (existing != null && existing.isNotEmpty) return existing;
    final fresh = _generateUuid();
    prefs.setString(_deviceIdKey, fresh);
    return fresh;
  }

  String _generateUuid() {
    final rand = Random.secure();
    String hex(int len) => List.generate(len, (_) => rand.nextInt(16).toRadixString(16)).join();
    return '${hex(8)}-${hex(4)}-${hex(4)}-${hex(4)}-${hex(12)}';
  }

  Future<void> _refreshStats() async {
    final eventId = widget.eventId;
    if (eventId == null) return;
    try {
      final service = ref.read(entryServiceProvider);
      final stats = await service.getEntryStats(eventId);
      setState(() {
        _total = (stats['total'] ?? 0) as int;
        _lastHour = (stats['last_hour'] ?? 0) as int;
      });
    } catch (_) {
      // Hors-ligne: on garde les derniers compteurs affichés.
    }
  }

  Future<void> _refreshLogs() async {
    final eventId = widget.eventId;
    if (eventId == null) return;
    try {
      final service = ref.read(entryServiceProvider);
      final logs = await service.getEntryLogs(eventId: eventId, limit: 20);
      setState(() {
        _history
          ..clear()
          ..addAll(
            logs.map(
              (row) => _EntryAction(
                delta: (row['delta'] ?? 0) as int,
                source: (row['source'] ?? 'manual').toString(),
                createdAt: DateTime.tryParse((row['created_at'] ?? '').toString()) ?? DateTime.now(),
                status: 'Serveur',
                offline: false,
                idempotencyKey: (row['idempotency_key'] ?? '').toString(),
              ),
            ),
          );
      });
    } catch (_) {
      // Pas de logs si hors-ligne.
    }
  }

  Future<void> _submitEntry({
    required int delta,
    required String source,
    String? rawQr,
  }) async {
    final eventId = widget.eventId;
    if (eventId == null || _deviceId == null) return;

    final action = _EntryAction(
      delta: delta,
      source: source,
      createdAt: DateTime.now(),
      status: 'Envoi…',
      offline: false,
      idempotencyKey: _generateUuid(),
      rawQr: rawQr,
      deviceId: _deviceId!,
      eventId: eventId,
    );

    _addHistory(action);

    try {
      final service = ref.read(entryServiceProvider);
      final stats = await service.postEntryScan(
        eventId: eventId,
        delta: delta,
        source: source,
        deviceId: _deviceId!,
        idempotencyKey: action.idempotencyKey,
        rawQr: rawQr,
      );
      _updateStats(stats);
      _updateHistoryStatus(action.idempotencyKey, 'Synchronisé', false);
      await _flushQueue();
    } catch (e) {
      if (_isNetworkError(e)) {
        await _enqueueOffline(action);
        _updateHistoryStatus(action.idempotencyKey, 'Hors-ligne', true);
      } else if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Erreur: ${ErrorMapper.message(e)}')),
        );
      }
    }
  }

  bool _isNetworkError(Object e) {
    if (e is DioException) {
      return e.type == DioExceptionType.connectionError ||
          e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.sendTimeout ||
          e.type == DioExceptionType.receiveTimeout;
    }
    return e is SocketException;
  }

  Future<void> _enqueueOffline(_EntryAction action) async {
    final prefs = await SharedPreferences.getInstance();
    final queue = _loadQueue(prefs);
    queue.add(action.toQueueJson());
    await prefs.setString(_queueKey, jsonEncode(queue));
  }

  Future<void> _flushQueue() async {
    if (_flushing) return;
    _flushing = true;
    try {
      final eventId = widget.eventId;
      if (eventId == null) return;
      final prefs = await SharedPreferences.getInstance();
      final queue = _loadQueue(prefs);
      if (queue.isEmpty) return;

      final service = ref.read(entryServiceProvider);
      final remaining = <Map<String, dynamic>>[];

      for (final item in queue) {
        final action = _EntryAction.fromQueueJson(item);
        try {
          final stats = await service.postEntryScan(
            eventId: action.eventId ?? eventId,
            delta: action.delta,
            source: action.source,
            deviceId: action.deviceId ?? _deviceId ?? '',
            idempotencyKey: action.idempotencyKey,
            rawQr: action.rawQr,
          );
          _updateStats(stats);
          _updateHistoryStatus(action.idempotencyKey, 'Synchronisé', false);
        } catch (_) {
          remaining.add(item);
          break;
        }
      }

      await prefs.setString(_queueKey, jsonEncode(remaining));
    } finally {
      _flushing = false;
    }
  }

  List<Map<String, dynamic>> _loadQueue(SharedPreferences prefs) {
    final raw = prefs.getString(_queueKey);
    if (raw == null || raw.isEmpty) return [];
    final decoded = jsonDecode(raw);
    if (decoded is List) {
      return decoded.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
    }
    return [];
  }

  void _updateStats(Map<String, dynamic> stats) {
    setState(() {
      _total = (stats['total'] ?? _total) as int;
      _lastHour = (stats['last_hour'] ?? _lastHour) as int;
    });
  }

  void _addHistory(_EntryAction action) {
    setState(() {
      _history.insert(0, action);
      if (_history.length > 20) {
        _history.removeRange(20, _history.length);
      }
    });
  }

  void _updateHistoryStatus(String idempotencyKey, String status, bool offline) {
    final idx = _history.indexWhere((item) => item.idempotencyKey == idempotencyKey);
    if (idx == -1) return;
    setState(() {
      _history[idx] = _history[idx].copyWith(status: status, offline: offline);
    });
  }

  Future<void> _openScanner() async {
    final raw = await Navigator.of(context).push<String>(
      MaterialPageRoute(builder: (_) => const _EntryScannerScreen()),
    );
    if (raw == null || raw.isEmpty) return;
    await _submitEntry(delta: 1, source: 'scan', rawQr: raw);
  }

  @override
  Widget build(BuildContext context) {
    final eventId = widget.eventId;
    if (eventId == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Entrée & Comptage')),
        body: const Center(child: Text('QR invalide: event_id manquant.')),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Entrée & Comptage')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                  child: _CounterCard(total: _total, lastHour: _lastHour),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: Wrap(
                    spacing: 12,
                    runSpacing: 12,
                    children: [
                      ElevatedButton.icon(
                        onPressed: _openScanner,
                        icon: const Icon(Icons.qr_code_scanner),
                        label: const Text('Scanner'),
                      ),
                      OutlinedButton.icon(
                        onPressed: () => _submitEntry(delta: 1, source: 'manual'),
                        icon: const Icon(Icons.exposure_plus_1),
                        label: const Text('+1 manuel'),
                      ),
                      OutlinedButton.icon(
                        onPressed: () => _submitEntry(delta: -1, source: 'manual'),
                        icon: const Icon(Icons.exposure_minus_1),
                        label: const Text('-1 correction'),
                      ),
                    ],
                  ),
                ),
                const Padding(
                  padding: EdgeInsets.fromLTRB(16, 8, 16, 4),
                  child: Text(
                    'Historique (20 dernières actions)',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
                Expanded(
                  child: _history.isEmpty
                      ? const Center(child: Text('Aucune action pour le moment.'))
                      : ListView.builder(
                          padding: const EdgeInsets.fromLTRB(8, 4, 8, 12),
                          itemCount: _history.length,
                          itemBuilder: (context, index) {
                            final action = _history[index];
                            return _HistoryTile(action: action);
                          },
                        ),
                ),
              ],
            ),
    );
  }
}

class _CounterCard extends StatelessWidget {
  const _CounterCard({required this.total, required this.lastHour});

  final int total;
  final int lastHour;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Total entrées', style: TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text(
              '$total',
              style: Theme.of(context).textTheme.displayMedium?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text('Dernière heure: $lastHour'),
          ],
        ),
      ),
    );
  }
}

class _HistoryTile extends StatelessWidget {
  const _HistoryTile({required this.action});

  final _EntryAction action;

  @override
  Widget build(BuildContext context) {
    final time = TimeOfDay.fromDateTime(action.createdAt);
    final label = MaterialLocalizations.of(context).formatTimeOfDay(time);
    final sign = action.delta >= 0 ? '+' : '';
    final subtitleParts = <String>[
      action.sourceLabel,
      action.status,
      if (action.offline) 'Offline',
    ];
    return ListTile(
      leading: Icon(action.delta >= 0 ? Icons.add_circle_outline : Icons.remove_circle_outline),
      title: Text('$sign${action.delta} • $label'),
      subtitle: Text(subtitleParts.join(' • ')),
    );
  }
}

class _EntryScannerScreen extends StatefulWidget {
  const _EntryScannerScreen();

  @override
  State<_EntryScannerScreen> createState() => _EntryScannerScreenState();
}

class _EntryScannerScreenState extends State<_EntryScannerScreen> {
  bool _handled = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Scanner une entrée')),
      body: MobileScanner(
        onDetect: (capture) {
          if (_handled) return;
          final barcode = capture.barcodes.isNotEmpty ? capture.barcodes.first : null;
          final raw = barcode?.rawValue ?? '';
          if (raw.isEmpty) return;
          _handled = true;
          Navigator.of(context).pop(raw);
        },
      ),
    );
  }
}

class _EntryAction {
  _EntryAction({
    required this.delta,
    required this.source,
    required this.createdAt,
    required this.status,
    required this.offline,
    required this.idempotencyKey,
    this.rawQr,
    this.deviceId,
    this.eventId,
  });

  final int delta;
  final String source;
  final DateTime createdAt;
  final String status;
  final bool offline;
  final String idempotencyKey;
  final String? rawQr;
  final String? deviceId;
  final int? eventId;

  String get sourceLabel => source == 'scan' ? 'Scan' : 'Manuel';

  _EntryAction copyWith({String? status, bool? offline}) {
    return _EntryAction(
      delta: delta,
      source: source,
      createdAt: createdAt,
      status: status ?? this.status,
      offline: offline ?? this.offline,
      idempotencyKey: idempotencyKey,
      rawQr: rawQr,
      deviceId: deviceId,
      eventId: eventId,
    );
  }

  Map<String, dynamic> toQueueJson() {
    return {
      'event_id': eventId,
      'delta': delta,
      'source': source,
      'created_at': createdAt.toIso8601String(),
      'idempotency_key': idempotencyKey,
      'raw_qr': rawQr,
      'device_id': deviceId,
    };
  }

  static _EntryAction fromQueueJson(Map<String, dynamic> json) {
    return _EntryAction(
      eventId: json['event_id'] as int?,
      delta: (json['delta'] ?? 0) as int,
      source: (json['source'] ?? 'manual').toString(),
      createdAt: DateTime.tryParse((json['created_at'] ?? '').toString()) ?? DateTime.now(),
      status: 'Synchronisation…',
      offline: true,
      idempotencyKey: (json['idempotency_key'] ?? '').toString(),
      rawQr: json['raw_qr'] as String?,
      deviceId: json['device_id'] as String?,
    );
  }
}
