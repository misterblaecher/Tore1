import 'dart:async';

import 'package:dio/dio.dart';
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
  String _manualReason = 'QR illisible';
  final TextEditingController _noteCtrl = TextEditingController();
  String _banner = 'Prêt à scanner';
  Color _bannerColor = const Color(0xFF1F2937);
  String? _statsError;
  final ScanSuppression _suppression =
      ScanSuppression(cooldown: const Duration(milliseconds: 800));
  final List<String> _reasonChips = const [
    'QR illisible',
    'caméra HS',
    'file rush',
    'autre…'
  ];

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  @override
  void dispose() {
    _noteCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    if (widget.eventId == null) return;
    await _refreshStats();
    if (!mounted) return;
    setState(() => _loading = false);
  }

  Future<void> _refreshStats() async {
    if (widget.eventId == null) return;
    int? total;
    int? delta10;
    Object? failure;
    try {
      final count = await ref
          .read(entryServiceProvider)
          .getEntryCount(widget.eventId!);
      total = (count['entryCount'] ?? 0) as int;
    } catch (error) {
      failure = error;
    }
    try {
      final stats =
          await ref.read(entryServiceProvider).getEntryStats(widget.eventId!);
      delta10 = (stats['accepted_last_10_min'] ?? _delta10) as int;
    } catch (error) {
      failure ??= error;
    }
    if (!mounted) return;
    setState(() {
      if (total != null) _total = total;
      if (delta10 != null) _delta10 = delta10;
      _statsError = failure == null
          ? null
          : 'Compteurs temporairement indisponibles — dernière valeur conservée';
    });
  }

  Future<void> _openScanner() async {
    if (ref.read(networkStatusProvider) != NetworkState.online) {
      return _feedback('invalid', 'Serveur indisponible', type: 'QR');
    }
    final raw = await Navigator.of(context).push<String>(MaterialPageRoute(
        builder: (_) => const QrScannerScreen(mode: QrScannerMode.pickRaw)));
    if (raw == null || raw.trim().isEmpty || widget.eventId == null) return;
    if (_suppression.shouldSuppress(hash: hashQr(raw), now: DateTime.now()))
      return;
    try {
      final payload = ref.read(qrParserProvider).parse(raw);
      final validation = await ref.read(qrValidatorProvider).validate(payload);
      if (!validation.isOk) {
        return _feedback('invalid', validation.reason ?? 'QR non reconnu',
            type: 'QR');
      }
      await _performCheckin(raw);
    } catch (error) {
      _feedback('invalid', _operatorError(error, fallback: 'QR refusé'),
          type: 'QR');
    }
  }

  Future<void> _performCheckin(String raw) async {
    final eventId = widget.eventId;
    if (eventId == null) return;
    final scannedAt = DateTime.now();
    if (ref.read(networkStatusProvider) != NetworkState.online) {
      return _feedback('invalid', 'Serveur indisponible — entrée non validée',
          type: 'QR');
    }
    final idempotencyKey =
        'entry-$eventId-${scannedAt.millisecondsSinceEpoch}-${raw.hashCode}';
    try {
      final res = await ref.read(entryServiceProvider).checkin(
          eventId: eventId,
          rawQr: raw,
          deviceId: 'orga-mobile',
          idempotencyKey: idempotencyKey,
          scannedAt: scannedAt);
      _feedback((res['status'] ?? 'accepted').toString(),
          'QR ${(res['status'] ?? 'accepted').toString()}',
          type: 'QR');
      unawaited(_refreshStats());
    } catch (error) {
      _feedback('invalid',
          _operatorError(error, fallback: 'Entrée non validée'),
          type: 'QR');
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
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(ctx, false),
                    child: const Text('Annuler')),
                FilledButton(
                    onPressed: () => Navigator.pop(ctx, true),
                    child: const Text('Retirer'))
              ],
            ),
          ) ??
          false;
      if (!ok) return;
      return _feedback('invalid', 'Correction -1 non autorisée sur ce mode',
          type: 'MANUAL');
    }

    final now = DateTime.now();
    if (ref.read(networkStatusProvider) != NetworkState.online) {
      return _feedback(
          'invalid', 'Serveur indisponible — correction non enregistrée',
          type: 'MANUAL');
    }
    final idempotencyKey =
        'manual-$eventId-${now.millisecondsSinceEpoch}-$delta';
    final note = _noteCtrl.text.trim().isEmpty ? null : _noteCtrl.text.trim();
    try {
      await ref.read(entryServiceProvider).manualIncrement(
          eventId: eventId,
          delta: delta.abs(),
          reason: _manualReason,
          note: note,
          idempotencyKey: idempotencyKey);
      _feedback('accepted', '${delta > 0 ? '+' : ''}$delta ajouté',
          type: 'MANUAL');
      unawaited(_refreshStats());
    } catch (error) {
      _feedback('invalid',
          _operatorError(error, fallback: 'Correction non enregistrée'),
          type: 'MANUAL');
    }
  }

  void _feedback(String status, String reason, {required String type}) {
    HapticFeedback.selectionClick();
    SystemSound.play(SystemSoundType.click);
    _bannerColor = status == 'accepted'
        ? const Color(0xFF166534)
        : (status == 'pending'
            ? const Color(0xFF1D4ED8)
            : const Color(0xFFB91C1C));
    _banner = reason;
    ref.read(entryUiStateProvider.notifier).push(ScanResult(
        status: status, reason: reason, at: DateTime.now(), type: type));
    if (mounted) {
      setState(() {});
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(reason), duration: const Duration(milliseconds: 700)));
    }
  }

  Future<void> _exportCsv() async {
    if (widget.eventId == null) return;
    try {
      final csv =
          await ref.read(entryServiceProvider).exportCsv(widget.eventId!);
      await Clipboard.setData(ClipboardData(text: csv));
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('CSV copié (inclut MANUAL)')));
    } catch (error) {
      _feedback('invalid', _operatorError(error, fallback: 'Export indisponible'),
          type: 'EXPORT');
    }
  }

  String _operatorError(Object error, {required String fallback}) {
    if (error is DioException) {
      final status = error.response?.statusCode;
      final body = error.response?.data;
      if (body is Map) {
        final detail = body['detail'];
        final reason = detail is Map
            ? (detail['message'] ?? detail['reason'])
            : detail;
        if (reason != null && reason.toString().trim().isNotEmpty) {
          return '$fallback — ${reason.toString()}';
        }
      }
      if (status != null) return '$fallback — HTTP $status';
      return '$fallback — réseau indisponible';
    }
    return '$fallback — opération non confirmée';
  }

  @override
  Widget build(BuildContext context) {
    if (widget.eventId == null)
      return const Scaffold(body: Center(child: Text('event_id manquant')));
    if (_loading)
      return const Scaffold(body: Center(child: CircularProgressIndicator()));

    final net = ref.watch(networkStatusProvider);
    final recents = ref.watch(entryUiStateProvider).recent;

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      'Event #${widget.eventId}',
                      softWrap: true,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Flexible(
                    child: Align(
                      alignment: Alignment.centerRight,
                      child: Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        alignment: WrapAlignment.end,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          TextButton.icon(
                            onPressed: () => Navigator.of(context).push(
                                MaterialPageRoute(
                                    builder: (_) => StaffBackupJoinScreen(
                                        prefillEventId: widget.eventId))),
                            icon: const Icon(Icons.keyboard),
                            label: const Text('Entrer un code'),
                          ),
                          IconButton(
                              onPressed: _exportCsv,
                              icon: const Icon(Icons.download)),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
              SwitchListTile(
                  value: _manualMode,
                  onChanged: (v) => setState(() => _manualMode = v),
                  title: const Text('Mode manuel'),
                  secondary: const Icon(Icons.touch_app)),
              Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                      color: _bannerColor,
                      borderRadius: BorderRadius.circular(8)),
                  width: double.infinity,
                  child: Text(_banner)),
              if (_statsError != null)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(_statsError!,
                      style: const TextStyle(color: Colors.orange)),
                ),
              Expanded(
                child: SingleChildScrollView(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(minHeight: 280),
                    child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Text('ENTRÉES'),
                          FittedBox(
                            fit: BoxFit.scaleDown,
                            child: Text(
                              '$_total',
                              style: const TextStyle(
                                  fontSize: 96, fontWeight: FontWeight.w900),
                            ),
                          ),
                          Text('Δ10m: $_delta10'),
                          const SizedBox(height: 12),
                          if (!_manualMode)
                            ElevatedButton.icon(
                                onPressed: net == NetworkState.online
                                    ? _openScanner
                                    : null,
                                icon: const Icon(Icons.qr_code_scanner),
                                label: const Text('SCAN',
                                    style: TextStyle(fontSize: 24)))
                          else ...[
                            Wrap(
                                spacing: 8,
                                children: _reasonChips
                                    .map((r) => ChoiceChip(
                                        label: Text(r),
                                        selected: _manualReason == r,
                                        onSelected: (_) =>
                                            setState(() => _manualReason = r)))
                                    .toList()),
                            TextField(
                                controller: _noteCtrl,
                                decoration: const InputDecoration(
                                    labelText: 'Note (optionnel)')),
                            const SizedBox(height: 8),
                            Wrap(spacing: 8, runSpacing: 8, children: [
                              FilledButton(
                                  onPressed: net == NetworkState.online
                                      ? () => _manualIncrement(1)
                                      : null,
                                  child: const Text('+1')),
                              FilledButton(
                                  onPressed: net == NetworkState.online
                                      ? () => _manualIncrement(5)
                                      : null,
                                  child: const Text('+5')),
                              FilledButton(
                                  onPressed: net == NetworkState.online
                                      ? () => _manualIncrement(10)
                                      : null,
                                  child: const Text('+10')),
                              OutlinedButton(
                                  onPressed: net == NetworkState.online
                                      ? () => _manualIncrement(-1)
                                      : null,
                                  child: const Text('-1')),
                            ]),
                          ],
                        ]),
                  ),
                ),
              ),
              Wrap(
                spacing: 12,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Text('Status: ${net.name.toUpperCase()}'),
                  Text(net == NetworkState.online
                      ? 'Validation serveur requise'
                      : 'Entrées bloquées hors ligne'),
                ],
              ),
              Container(
                color: const Color(0xFF111827),
                padding: const EdgeInsets.all(8),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Derniers événements (8)'),
                      SizedBox(
                        height: 150,
                        child: ListView.builder(
                          itemCount: recents.length,
                          itemBuilder: (context, i) {
                            final item = recents[i];
                            return Text(
                                '[${_fmt(item.at)}] ${item.type} — ${item.reason}');
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

  String _fmt(DateTime ts) =>
      '${ts.hour.toString().padLeft(2, '0')}:${ts.minute.toString().padLeft(2, '0')}';
}

class EntryUiState {
  const EntryUiState({this.recent = const []});
  final List<ScanResult> recent;
  EntryUiState copyWith({List<ScanResult>? recent}) =>
      EntryUiState(recent: recent ?? this.recent);
}

class EntryUiStateNotifier extends StateNotifier<EntryUiState> {
  EntryUiStateNotifier() : super(const EntryUiState());
  static const int maxRecent = 8;
  void push(ScanResult result) => state = state.copyWith(
      recent:
          [result, ...state.recent].take(maxRecent).toList(growable: false));
}

final entryUiStateProvider =
    StateNotifierProvider<EntryUiStateNotifier, EntryUiState>(
        (ref) => EntryUiStateNotifier());

class ScanResult {
  ScanResult(
      {required this.status,
      required this.reason,
      required this.at,
      required this.type});
  final String status;
  final String reason;
  final DateTime at;
  final String type;
}
