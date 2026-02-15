import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/network_state_provider.dart';
import '../../../core/qr/qr_parser.dart';
import '../../../core/qr/qr_validator.dart';
import '../../qr/presentation/qr_scanner_screen.dart';
import '../data/entry_offline_queue.dart';
import '../data/entry_service.dart';

class EntryModeScreen extends ConsumerStatefulWidget {
  const EntryModeScreen({super.key, required this.eventId});

  final int? eventId;

  @override
  ConsumerState<EntryModeScreen> createState() => _EntryModeScreenState();
}

class _EntryModeScreenState extends ConsumerState<EntryModeScreen> {
  int _total = 0;
  int _delta10 = 0;
  bool _loading = true;
  String _banner = 'Prêt à scanner';
  Color _bannerColor = const Color(0xFF1F2937);
  bool _pendingEstimate = false;
  DateTime _lastScanAt = DateTime.fromMillisecondsSinceEpoch(0);
  String _lastRaw = '';
  Timer? _syncTimer;

  List<EntryQueueItem> _queue = [];
  final List<_ScanResult> _recent = [];

  @override
  void initState() {
    super.initState();
    unawaited(_load());
    _syncTimer = Timer.periodic(const Duration(seconds: 8), (_) => unawaited(_syncPending()));
  }

  @override
  void dispose() {
    _syncTimer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    if (widget.eventId == null) {
      setState(() => _loading = false);
      return;
    }
    final store = ref.read(entryOfflineQueueStoreProvider);
    _queue = await store.load();
    await _refreshStats();
    await _refreshLogs();
    if (!mounted) return;
    setState(() => _loading = false);
  }

  Future<void> _refreshStats() async {
    if (widget.eventId == null) return;
    try {
      final count = await ref.read(entryServiceProvider).getEntryCount(widget.eventId!);
      if (!mounted) return;
      final pending = _queue.where((q) => q.eventId == widget.eventId && q.status == 'pending').length;
      setState(() {
        _total = (count['entryCount'] ?? 0) as int;
        _pendingEstimate = pending > 0;
      });
    } catch (_) {}
    try {
      final stats = await ref.read(entryServiceProvider).getEntryStats(widget.eventId!);
      if (!mounted) return;
      setState(() {
        _delta10 = (stats['accepted_last_10_min'] ?? _delta10) as int;
      });
    } catch (_) {}
  }

  Future<void> _refreshLogs() async {
    if (widget.eventId == null) return;
    final logs = await ref.read(entryServiceProvider).getEntryLogs(eventId: widget.eventId!, limit: 5);
    if (!mounted) return;
    setState(() {
      _recent
        ..clear()
        ..addAll(logs.map((r) => _ScanResult(
              status: (r['decision'] == 'ACCEPT') ? 'accepted' : ((r['reason'] == 'already_used') ? 'already_checked' : 'invalid'),
              reason: (r['reason'] ?? '').toString(),
              at: DateTime.tryParse((r['created_at'] ?? '').toString()) ?? DateTime.now(),
            )));
    });
  }

  Future<void> _openScanner() async {
    final raw = await Navigator.of(context).push<String>(MaterialPageRoute(builder: (_) => const QrScannerScreen(mode: QrScannerMode.pickRaw)));
    if (raw == null || raw.trim().isEmpty || widget.eventId == null) return;

    final now = DateTime.now();
    if (_lastRaw == raw && now.difference(_lastScanAt).inMilliseconds < 800) return;
    _lastRaw = raw;
    _lastScanAt = now;

    final payload = ref.read(qrParserProvider).parse(raw);
    final validation = await ref.read(qrValidatorProvider).validate(payload);
    if (!validation.isOk) {
      _applyFeedback(status: 'invalid', reason: validation.reason ?? 'INVALID');
      return;
    }
    await _handleScan(raw, scannedAt: now);
  }

  Future<void> _handleScan(String raw, {required DateTime scannedAt}) async {
    final eventId = widget.eventId;
    if (eventId == null) return;
    final status = ref.read(networkStatusProvider);
    final queueMode = status != NetworkState.online;
    final item = EntryQueueItem(
      id: '$eventId-${scannedAt.millisecondsSinceEpoch}-${raw.hashCode}',
      eventId: eventId,
      rawQr: raw,
      scannedAt: scannedAt,
      idempotencyKey: 'entry-$eventId-${scannedAt.millisecondsSinceEpoch}-${raw.hashCode}',
    );

    if (queueMode) {
      await _enqueue(item, reason: 'PENDING SYNC');
      _applyFeedback(status: 'pending', reason: 'PENDING SYNC');
      return;
    }

    try {
      final res = await ref.read(entryServiceProvider).checkin(
            eventId: eventId,
            rawQr: raw,
            deviceId: 'orga-mobile',
            idempotencyKey: item.idempotencyKey,
            scannedAt: scannedAt,
          );
      _applyFeedback(status: (res['status'] ?? 'invalid').toString(), reason: (res['status'] ?? '').toString().toUpperCase());
      await _refreshStats();
      await _refreshLogs();
    } catch (e) {
      await _enqueue(item, reason: e.toString());
      _applyFeedback(status: 'pending', reason: 'PENDING SYNC');
    }
  }

  Future<void> _enqueue(EntryQueueItem item, {required String reason}) async {
    _queue.insert(0, item..lastError = reason);
    await ref.read(entryOfflineQueueStoreProvider).save(_queue);
    setState(() => _pendingEstimate = true);
  }

  Future<void> _syncPending() async {
    if (widget.eventId == null) return;
    if (ref.read(networkStatusProvider) != NetworkState.online) return;

    bool updated = false;
    for (final item in _queue.where((q) => q.status == 'pending' && q.eventId == widget.eventId).take(25)) {
      try {
        await ref.read(entryServiceProvider).checkin(
              eventId: item.eventId,
              rawQr: item.rawQr,
              deviceId: 'orga-mobile',
              idempotencyKey: item.idempotencyKey,
              scannedAt: item.scannedAt,
            );
        item.status = 'synced';
        item.lastError = null;
        updated = true;
      } catch (e) {
        item.status = 'failed';
        item.lastError = e.toString();
      }
    }
    if (updated) {
      await ref.read(entryOfflineQueueStoreProvider).save(_queue);
      await _refreshStats();
      if (mounted) setState(() {});
    }
  }

  void _applyFeedback({required String status, required String reason}) {
    Color color;
    HapticFeedback.vibrate();
    switch (status) {
      case 'accepted':
        color = const Color(0xFF166534);
        HapticFeedback.heavyImpact();
        SystemSound.play(SystemSoundType.click);
        break;
      case 'already_checked':
        color = const Color(0xFFB45309);
        HapticFeedback.lightImpact();
        break;
      case 'pending':
        color = const Color(0xFF1D4ED8);
        HapticFeedback.selectionClick();
        break;
      default:
        color = const Color(0xFFB91C1C);
        HapticFeedback.mediumImpact();
    }

    setState(() {
      _bannerColor = color;
      _banner = reason;
      _recent.insert(0, _ScanResult(status: status, reason: reason, at: DateTime.now()));
      if (_recent.length > 5) _recent.removeRange(5, _recent.length);
    });
  }

  Future<void> _exportCsv() async {
    if (widget.eventId == null) return;
    try {
      final csv = await ref.read(entryServiceProvider).exportCsv(widget.eventId!);
      await Clipboard.setData(ClipboardData(text: csv));
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('CSV copié dans le presse-papiers')));
    } catch (_) {
      final rows = _recent.map((r) => '${r.at.toIso8601String()},${r.status},${r.reason.replaceAll(',', ' ')}').join('\n');
      final fallback = 'timestamp,status,reason\n$rows';
      await Clipboard.setData(ClipboardData(text: fallback));
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Export local copié')));
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.eventId == null) {
      return const Scaffold(body: Center(child: Text('event_id manquant')));
    }

    final net = ref.watch(networkStatusProvider);
    final pendingCount = _queue.where((q) => q.status == 'pending' && q.eventId == widget.eventId).length;
    final totalDisplay = _total + pendingCount;

    return Scaffold(
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(children: [
                      Text('Event #${widget.eventId}', style: const TextStyle(fontWeight: FontWeight.w700)),
                      const SizedBox(width: 8),
                      Container(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4), color: const Color(0xFF15803D), child: const Text('LIVE')),
                      const Spacer(),
                      Text(TimeOfDay.now().format(context)),
                      IconButton(onPressed: _exportCsv, icon: const Icon(Icons.download)),
                    ]),
                    Container(padding: const EdgeInsets.all(8), decoration: BoxDecoration(color: _bannerColor, borderRadius: BorderRadius.circular(8)), child: Text(_banner)),
                    const SizedBox(height: 8),
                    Expanded(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Text('ENTRÉES', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
                          Text('${_pendingEstimate ? '~' : ''}$totalDisplay', style: const TextStyle(fontSize: 108, fontWeight: FontWeight.w900, height: 1)),
                          Text('Δ10m: $_delta10', style: const TextStyle(fontSize: 20)),
                          const SizedBox(height: 16),
                          SizedBox(
                            width: 260,
                            height: 62,
                            child: ElevatedButton.icon(onPressed: _openScanner, icon: const Icon(Icons.qr_code_scanner), label: const Text('SCAN', style: TextStyle(fontSize: 26))),
                          ),
                        ],
                      ),
                    ),
                    Row(children: [
                      Text('Status: ${net.name.toUpperCase()}'),
                      const Spacer(),
                      Text('Queue: $pendingCount'),
                      const SizedBox(width: 8),
                      TextButton(onPressed: _syncPending, child: const Text('Sync now')),
                    ]),
                    Container(
                      padding: const EdgeInsets.all(8),
                      color: const Color(0xFF111827),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Derniers scans', style: TextStyle(fontWeight: FontWeight.w700)),
                          for (final item in _recent.take(5)) Text('[${_fmt(item.at)}] ${item.status} • ${item.reason}'),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
    );
  }

  String _fmt(DateTime ts) => '${ts.hour.toString().padLeft(2, '0')}:${ts.minute.toString().padLeft(2, '0')}:${ts.second.toString().padLeft(2, '0')}';
}

class _ScanResult {
  _ScanResult({required this.status, required this.reason, required this.at});

  final String status;
  final String reason;
  final DateTime at;
}
