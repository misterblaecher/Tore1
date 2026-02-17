import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/network_state_provider.dart';
import '../../../core/perf/perf_tracer.dart';
import '../../../core/perf/scan_suppression.dart';
import '../../../core/qr/qr_parser.dart';
import '../../../core/qr/qr_validator.dart';
import '../../events/presentation/staff_backup_join_screen.dart';
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
  bool _manualMode = false;
  bool _pendingEstimate = false;
  String _manualReason = 'QR illisible';
  final TextEditingController _noteCtrl = TextEditingController();
  String _banner = 'Prêt à scanner';
  Color _bannerColor = const Color(0xFF1F2937);
  final ScanSuppression _suppression = ScanSuppression(cooldown: const Duration(milliseconds: 800));
  final List<String> _reasonChips = const ['QR illisible', 'caméra HS', 'file rush', 'autre…'];

  Timer? _syncTimer;
  List<EntryQueueItem> _queue = [];

  @override
  void initState() {
    super.initState();
    unawaited(_load());
    _syncTimer = Timer.periodic(const Duration(seconds: 8), (_) => unawaited(_syncPending()));
  }

  @override
  void dispose() {
    _syncTimer?.cancel();
    _noteCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    if (widget.eventId == null) return;
    _queue = await ref.read(entryOfflineQueueStoreProvider).load();
    await _refreshStats();
    if (!mounted) return;
    setState(() => _loading = false);
  }

  Future<void> _refreshStats() async {
    if (widget.eventId == null) return;
    try {
      final count = await ref.read(entryServiceProvider).getEntryCount(widget.eventId!);
      if (!mounted) return;
      final pending = _queue.where((q) => q.eventId == widget.eventId && q.status == 'pending' && q.delta > 0).fold<int>(0, (a, b) => a + b.delta);
      setState(() {
        _total = (count['entryCount'] ?? 0) as int;
        _pendingEstimate = pending > 0;
      });
    } catch (_) {}
    try {
      final stats = await ref.read(entryServiceProvider).getEntryStats(widget.eventId!);
      if (!mounted) return;
      setState(() => _delta10 = (stats['accepted_last_10_min'] ?? _delta10) as int);
    } catch (_) {}
  }

  Future<void> _openScanner() async {
    final raw = await Navigator.of(context).push<String>(MaterialPageRoute(builder: (_) => const QrScannerScreen(mode: QrScannerMode.pickRaw)));
    if (raw == null || raw.trim().isEmpty || widget.eventId == null) return;
    if (_suppression.shouldSuppress(hash: hashQr(raw), now: DateTime.now())) return;
    final payload = ref.read(qrParserProvider).parse(raw);
    final validation = await ref.read(qrValidatorProvider).validate(payload);
    if (!validation.isOk) return _feedback('invalid', validation.reason ?? 'INVALID', type: 'QR');
    await _performCheckin(raw);
  }

  Future<void> _performCheckin(String raw) async {
    final eventId = widget.eventId;
    if (eventId == null) return;
    final scannedAt = DateTime.now();
    final item = EntryQueueItem(
      id: '$eventId-${scannedAt.millisecondsSinceEpoch}-${raw.hashCode}',
      eventId: eventId,
      type: 'CHECKIN',
      rawQr: raw,
      scannedAt: scannedAt,
      idempotencyKey: 'entry-$eventId-${scannedAt.millisecondsSinceEpoch}-${raw.hashCode}',
    );
    if (ref.read(networkStatusProvider) != NetworkState.online) {
      await _enqueue(item, 'PENDING SYNC');
      return _feedback('pending', '+1 ajouté (PENDING SYNC)', type: 'QR');
    }
    try {
      final res = await ref.read(entryServiceProvider).checkin(eventId: eventId, rawQr: raw, deviceId: 'orga-mobile', idempotencyKey: item.idempotencyKey, scannedAt: scannedAt);
      _feedback((res['status'] ?? 'accepted').toString(), 'QR ${(res['status'] ?? 'accepted').toString()}', type: 'QR');
      unawaited(_refreshStats());
    } catch (_) {
      await _enqueue(item, 'PENDING SYNC');
      _feedback('pending', '+1 ajouté (PENDING SYNC)', type: 'QR');
    }
  }

  Future<void> _manualIncrement(int delta) async {
    final eventId = widget.eventId;
    if (eventId == null) return;
    if (delta < 0) {
      final ok = await showDialog<bool>(
            context: context,
            builder: (ctx) => AlertDialog(
              title: const Text('Confirmer correction'),
              content: const Text('Retirer 1 entrée ?'),
              actions: [TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Annuler')), FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Retirer'))],
            ),
          ) ??
          false;
      if (!ok) return;
      return _feedback('invalid', 'Correction -1 non autorisée sur ce mode', type: 'MANUAL');
    }

    final now = DateTime.now();
    final item = EntryQueueItem(
      id: 'manual-$eventId-${now.millisecondsSinceEpoch}-$delta',
      eventId: eventId,
      type: 'MANUAL',
      scannedAt: now,
      idempotencyKey: 'manual-$eventId-${now.millisecondsSinceEpoch}-$delta',
      delta: delta,
      reason: _manualReason,
      note: _noteCtrl.text.trim().isEmpty ? null : _noteCtrl.text.trim(),
    );

    if (ref.read(networkStatusProvider) != NetworkState.online) {
      await _enqueue(item, 'PENDING SYNC');
      return _feedback('pending', '${delta > 0 ? '+' : ''}$delta ajouté (PENDING SYNC)', type: 'MANUAL');
    }
    try {
      await ref.read(entryServiceProvider).manualIncrement(eventId: eventId, delta: delta.abs(), reason: _manualReason, note: item.note, idempotencyKey: item.idempotencyKey);
      _feedback('accepted', '${delta > 0 ? '+' : ''}$delta ajouté', type: 'MANUAL');
      unawaited(_refreshStats());
    } catch (_) {
      await _enqueue(item, 'PENDING SYNC');
      _feedback('pending', '${delta > 0 ? '+' : ''}$delta ajouté (PENDING SYNC)', type: 'MANUAL');
    }
  }

  Future<void> _enqueue(EntryQueueItem item, String reason) async {
    item.lastError = reason;
    _queue.insert(0, item);
    await ref.read(entryOfflineQueueStoreProvider).save(_queue);
    await _refreshStats();
    if (mounted) setState(() {});
  }

  Future<void> _syncPending() async {
    if (widget.eventId == null || ref.read(networkStatusProvider) != NetworkState.online) return;
    bool updated = false;
    for (final item in _queue.where((i) => i.status == 'pending' && i.eventId == widget.eventId)) {
      try {
        if (item.type == 'MANUAL') {
          await ref.read(entryServiceProvider).manualIncrement(
                eventId: item.eventId,
                delta: item.delta.abs(),
                reason: item.reason ?? 'file rush',
                note: item.note,
                idempotencyKey: item.idempotencyKey,
              );
        } else {
          await ref.read(entryServiceProvider).checkin(
                eventId: item.eventId,
                rawQr: item.rawQr ?? '',
                deviceId: 'orga-mobile',
                idempotencyKey: item.idempotencyKey,
                scannedAt: item.scannedAt,
              );
        }
        item.status = 'synced';
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

  void _feedback(String status, String reason, {required String type}) {
    HapticFeedback.selectionClick();
    SystemSound.play(SystemSoundType.click);
    _bannerColor = status == 'accepted' ? const Color(0xFF166534) : (status == 'pending' ? const Color(0xFF1D4ED8) : const Color(0xFFB91C1C));
    _banner = reason;
    ref.read(entryUiStateProvider.notifier).push(_ScanResult(status: status, reason: reason, at: DateTime.now(), type: type));
    if (mounted) {
      setState(() {});
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(reason), duration: const Duration(milliseconds: 700)));
    }
  }

  Future<void> _exportCsv() async {
    if (widget.eventId == null) return;
    final csv = await ref.read(entryServiceProvider).exportCsv(widget.eventId!);
    await Clipboard.setData(ClipboardData(text: csv));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('CSV copié (inclut MANUAL)')));
  }

  @override
  Widget build(BuildContext context) {
    if (widget.eventId == null) return const Scaffold(body: Center(child: Text('event_id manquant')));
    if (_loading) return const Scaffold(body: Center(child: CircularProgressIndicator()));

    final net = ref.watch(networkStatusProvider);
    final pending = _queue.where((q) => q.status == 'pending' && q.eventId == widget.eventId).toList();
    final totalDisplay = _total + pending.fold<int>(0, (a, b) => a + (b.delta > 0 ? b.delta : 0));
    final recents = ref.watch(entryUiStateProvider).recent;

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            children: [
              Row(children: [
                Text('Event #${widget.eventId}'),
                const Spacer(),
                TextButton.icon(onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => StaffBackupJoinScreen(prefillEventId: widget.eventId))), icon: const Icon(Icons.keyboard), label: const Text('Entrer un code')),
                IconButton(onPressed: _exportCsv, icon: const Icon(Icons.download)),
              ]),
              SwitchListTile(value: _manualMode, onChanged: (v) => setState(() => _manualMode = v), title: const Text('Mode manuel'), secondary: const Icon(Icons.touch_app)),
              Container(padding: const EdgeInsets.all(8), decoration: BoxDecoration(color: _bannerColor, borderRadius: BorderRadius.circular(8)), width: double.infinity, child: Text(_banner)),
              Expanded(
                child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                  const Text('ENTRÉES'),
                  Text('${_pendingEstimate ? '~' : ''}$totalDisplay', style: const TextStyle(fontSize: 96, fontWeight: FontWeight.w900)),
                  Text('Δ10m: $_delta10'),
                  const SizedBox(height: 12),
                  if (!_manualMode)
                    ElevatedButton.icon(onPressed: _openScanner, icon: const Icon(Icons.qr_code_scanner), label: const Text('SCAN', style: TextStyle(fontSize: 24)))
                  else ...[
                    Wrap(spacing: 8, children: _reasonChips.map((r) => ChoiceChip(label: Text(r), selected: _manualReason == r, onSelected: (_) => setState(() => _manualReason = r))).toList()),
                    TextField(controller: _noteCtrl, decoration: const InputDecoration(labelText: 'Note (optionnel)')),
                    const SizedBox(height: 8),
                    Wrap(spacing: 8, runSpacing: 8, children: [
                      FilledButton(onPressed: () => _manualIncrement(1), child: const Text('+1')),
                      FilledButton(onPressed: () => _manualIncrement(5), child: const Text('+5')),
                      FilledButton(onPressed: () => _manualIncrement(10), child: const Text('+10')),
                      OutlinedButton(onPressed: () => _manualIncrement(-1), child: const Text('-1')),
                    ]),
                  ],
                ]),
              ),
              Row(children: [Text('Status: ${net.name.toUpperCase()}'), const Spacer(), Text('Queue: ${pending.length}'), TextButton(onPressed: _syncPending, child: const Text('Sync now'))]),
              Container(
                color: const Color(0xFF111827),
                padding: const EdgeInsets.all(8),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Text('Derniers événements (8)'),
                  SizedBox(
                    height: 150,
                    child: ListView.builder(
                      itemCount: recents.length,
                      itemBuilder: (context, i) {
                        final item = recents[i];
                        return Text('[${_fmt(item.at)}] ${item.type} — ${item.reason}');
                      },
                    ),
                  ),
                ]),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _fmt(DateTime ts) => '${ts.hour.toString().padLeft(2, '0')}:${ts.minute.toString().padLeft(2, '0')}';
}

class EntryUiState {
  const EntryUiState({this.recent = const []});
  final List<_ScanResult> recent;
  EntryUiState copyWith({List<_ScanResult>? recent}) => EntryUiState(recent: recent ?? this.recent);
}

class EntryUiStateNotifier extends StateNotifier<EntryUiState> {
  EntryUiStateNotifier() : super(const EntryUiState());
  static const int maxRecent = 8;
  void push(_ScanResult result) => state = state.copyWith(recent: [result, ...state.recent].take(maxRecent).toList(growable: false));
}

final entryUiStateProvider = StateNotifierProvider<EntryUiStateNotifier, EntryUiState>((ref) => EntryUiStateNotifier());

class _ScanResult {
  _ScanResult({required this.status, required this.reason, required this.at, required this.type});
  final String status;
  final String reason;
  final DateTime at;
  final String type;
}
