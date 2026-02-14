import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/error_mapper.dart';
import '../../qr/presentation/qr_scanner_screen.dart';
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
  String? _runtimeReason;
  String _banner = 'Prêt à scanner';
  Color _bannerColor = const Color(0xFF1F2937);
  final List<_ScanResult> _recent = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  String _scanId() {
    final rand = Random.secure();
    return '${DateTime.now().millisecondsSinceEpoch}-${rand.nextInt(999999)}';
  }

  Future<void> _load() async {
    if (widget.eventId == null) {
      setState(() => _loading = false);
      return;
    }
    setState(() => _loading = true);
    await _refreshStats();
    await _refreshLogs();
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _refreshStats() async {
    if (widget.eventId == null) return;
    final service = ref.read(entryServiceProvider);
    final stats = await service.getEntryStats(widget.eventId!);
    if (!mounted) return;
    setState(() {
      _total = (stats['entry_count'] ?? _total) as int;
      _delta10 = (stats['accepted_last_10_min'] ?? _delta10) as int;
      _runtimeReason = stats['runtime_reason']?.toString();
    });
  }

  Future<void> _refreshLogs() async {
    if (widget.eventId == null) return;
    final service = ref.read(entryServiceProvider);
    final logs = await service.getEntryLogs(eventId: widget.eventId!, limit: 5);
    if (!mounted) return;
    setState(() {
      _recent
        ..clear()
        ..addAll(logs.map((r) => _ScanResult(
              status: (r['decision'] == 'ACCEPT') ? 'accepted' : ((r['reason'] == 'already_used') ? 'duplicate' : 'denied'),
              reason: (r['reason'] ?? '').toString(),
              at: DateTime.tryParse((r['created_at'] ?? '').toString()) ?? DateTime.now(),
            )));
    });
  }

  Future<void> _submitToken(String token) async {
    final eventId = widget.eventId;
    if (eventId == null || token.trim().isEmpty) return;

    final service = ref.read(entryServiceProvider);
    try {
      final res = await service.scanEntry(eventId: eventId, token: token.trim(), scanId: _scanId());
      final status = (res['status'] ?? 'denied').toString();
      final reason = (res['reason'] ?? '').toString();
      _applyFeedback(status: status, reason: reason);
      await _refreshStats();
      await _refreshLogs();
    } catch (e) {
      _applyFeedback(status: 'network', reason: ErrorMapper.message(e));
    }
  }

  void _applyFeedback({required String status, required String reason}) {
    Color color;
    String msg;
    switch (status) {
      case 'accepted':
        color = const Color(0xFF166534);
        msg = '✅ Validé';
        break;
      case 'duplicate':
        color = const Color(0xFFA16207);
        msg = '⚠️ Déjà scanné';
        break;
      case 'network':
        color = const Color(0xFF1D4ED8);
        msg = '📡 Erreur réseau — Retry';
        break;
      default:
        color = const Color(0xFFB91C1C);
        msg = '⛔ Refusé';
        break;
    }

    setState(() {
      _bannerColor = color;
      _banner = reason.isEmpty ? msg : '$msg • $reason';
      _recent.insert(0, _ScanResult(status: status, reason: reason, at: DateTime.now()));
      if (_recent.length > 5) {
        _recent.removeRange(5, _recent.length);
      }
    });
  }

  Future<void> _openScanner() async {
    final raw = await Navigator.of(context).push<String>(
      MaterialPageRoute(builder: (_) => const QrScannerScreen(mode: QrScannerMode.pickRaw)),
    );
    if (raw == null || raw.isEmpty) return;
    await _submitToken(raw);
  }

  @override
  Widget build(BuildContext context) {
    if (widget.eventId == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Entry Staff')),
        body: const Center(child: Text('event_id manquant.')),
      );
    }

    return Scaffold(
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    if (_runtimeReason == 'event_paused' || _runtimeReason == 'module_off')
                      Container(
                        padding: const EdgeInsets.all(10),
                        margin: const EdgeInsets.only(bottom: 10),
                        decoration: BoxDecoration(color: const Color(0xFF7C2D12), borderRadius: BorderRadius.circular(10)),
                        child: Text('Entrée bloquée: $_runtimeReason'),
                      ),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(color: _bannerColor, borderRadius: BorderRadius.circular(12)),
                      child: Text(_banner, style: const TextStyle(fontWeight: FontWeight.w700)),
                    ),
                    const SizedBox(height: 16),
                    Expanded(
                      child: Center(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Text('ENTRÉES', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700)),
                            Text(
                              '$_total',
                              style: const TextStyle(fontSize: 120, fontWeight: FontWeight.w900, height: 1),
                            ),
                            Text('Δ 10 min: $_delta10', style: const TextStyle(fontSize: 24)),
                            const SizedBox(height: 20),
                            SizedBox(
                              width: 280,
                              height: 64,
                              child: ElevatedButton.icon(
                                onPressed: _openScanner,
                                icon: const Icon(Icons.qr_code_scanner, size: 30),
                                label: const Text('SCANNER', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800)),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(color: const Color(0xFF111827), borderRadius: BorderRadius.circular(10)),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('5 derniers', style: TextStyle(fontWeight: FontWeight.w700)),
                          const SizedBox(height: 6),
                          for (final item in _recent)
                            Text('[${_fmt(item.at)}] ${item.status} ${item.reason.isEmpty ? '' : '• ${item.reason}'}'),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
    );
  }

  String _fmt(DateTime ts) {
    final hh = ts.hour.toString().padLeft(2, '0');
    final mm = ts.minute.toString().padLeft(2, '0');
    final ss = ts.second.toString().padLeft(2, '0');
    return '$hh:$mm:$ss';
  }
}

class _ScanResult {
  _ScanResult({required this.status, required this.reason, required this.at});

  final String status;
  final String reason;
  final DateTime at;
}
