import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_exception.dart';
import '../../core/network/error_mapper.dart';
import '../../state.dart';
import '../../shared/utils/runtime_write_guard.dart';
import '../../shared/utils/write_gate.dart';
import '../../shared/widgets/service_limited_banner.dart';
import 'polymarket_models.dart';

class MarketDetailScreen extends ConsumerStatefulWidget {
  const MarketDetailScreen({super.key, required this.marketId});

  final int marketId;

  @override
  ConsumerState<MarketDetailScreen> createState() => _MarketDetailScreenState();
}

class _MarketDetailScreenState extends ConsumerState<MarketDetailScreen> {
  MarketDetail? _market;
  List<TradeRow> _history = [];
  String? _nextCursor;
  bool _loading = true;
  bool _submitting = false;
  String? _bannerReason;
  final _customCtrl = TextEditingController();
  int _amount = 100;
  final Set<String> _historyIds = <String>{};

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _customCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final res = await ref.read(apiProvider).fetchPolymarketMarket(widget.marketId);
      if (!mounted) return;
      setState(() {
        _market = res.market;
        _history = res.myHistory;
        _historyIds
          ..clear()
          ..addAll(res.myHistory.map((e) => e.id));
        _nextCursor = res.nextCursor;
      });
      await _resolveRuntimeBlock();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(ErrorMapper.runtimeBlockedMessage(e) ?? ErrorMapper.message(e))));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _resolveRuntimeBlock() async {
    final eventId = _market?.eventId;
    if (eventId == null) return;
    try {
      final event = await ref.read(apiProvider).getEvent(eventId);
      final reason = _extractRuntimeReason(event);
      if (mounted) setState(() => _bannerReason = reason);
    } catch (_) {}
  }

  String? _extractRuntimeReason(Map<String, dynamic> json) {
    final reason = json['reason']?.toString();
    final state = (json['runtime_state'] ?? json['state'] ?? json['status'])?.toString().toLowerCase();
    if (json['event_paused'] == true) return 'event_paused';
    if (json['read_only'] == true) return 'read_only';
    if (json['frozen'] == true) return 'frozen';
    if (json['closed'] == true) return 'closed';
    return normalizeRuntimeBlockReason(state: state, reason: reason);
  }

  bool get _writeBlocked => _bannerReason != null;

  Future<void> _submit(String side) async {
    if (_submitting || _writeBlocked || _market == null) return;
    setState(() => _submitting = true);
    final key = 'pm-${widget.marketId}-${side.toLowerCase()}-$_amount-v1';
    try {
      await ref.read(apiProvider).postPolymarketPosition(
            marketId: widget.marketId,
            side: side,
            amountCents: _amount,
            idempotencyKey: key,
          );
      if (!mounted) return;
      await _load();
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Position placée ✅')));
    } catch (e) {
      if (!mounted) return;
      final msg = ErrorMapper.message(e);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
      final runtimeReason = normalizeRuntimeBlockReason(reason: _extractErrorReason(e));
      if (runtimeReason != null) setState(() => _bannerReason = runtimeReason);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  String? _extractErrorReason(Object e) {
    if (e is ApiException) {
      final detail = e.details;
      if (detail is Map && detail['detail'] is Map) {
        return (detail['detail'] as Map)['reason']?.toString();
      }
    }
    return null;
  }

  Future<void> _loadMoreHistory() async {
    if (_nextCursor == null) return;
    try {
      final page = await ref.read(apiProvider).fetchMyHistory(marketId: widget.marketId, cursor: _nextCursor);
      if (!mounted) return;
      setState(() {
        final fresh = page.items.where((e) => _historyIds.add(e.id)).toList();
        _history = [..._history, ...fresh];
        _nextCursor = page.nextCursor;
      });
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final readOnly = isReadOnly(ref);
    final degradedBlocked = isWriteDegradedBlocked(ref, WriteIntent.critical);
    if (_loading) return Scaffold(appBar: AppBar(title: const Text('Market')), body: const Center(child: CircularProgressIndicator()));
    final m = _market;
    if (m == null) return Scaffold(appBar: AppBar(title: const Text('Market')), body: const Center(child: Text('Introuvable')));
    final resolvedBlocked = m.status == 'resolved';
    final writeBlocked = isWriteBlocked(readOnly: readOnly, degradedBlocked: degradedBlocked, runtimeBlocked: _writeBlocked) || resolvedBlocked;
    return Scaffold(
      appBar: AppBar(title: const Text('Market Detail')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.all(14),
          children: [
            Text(m.question, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            Text('YES ${(m.yesPct * 100).toStringAsFixed(0)}% / NO ${(m.noPct * 100).toStringAsFixed(0)}%'),
            const SizedBox(height: 6),
            LinearProgressIndicator(value: m.yesPct, minHeight: 10),
            const SizedBox(height: 6),
            Text('Pool: ${m.poolTickets} • Volume: ${m.volume} tickets'),
            if ((m.description ?? '').isNotEmpty) Text(m.description!),
            if (m.outcome != null)
              Text('Résultat: ${m.outcome} ${m.myPositionTotal == 0 ? '' : ((m.outcome == 'YES' && m.myPositionYes > 0) || (m.outcome == 'NO' && m.myPositionNo > 0) ? '• WIN' : '• LOSE')}'),
            const SizedBox(height: 12),
            Text('My position: YES ${m.myPositionYes} / NO ${m.myPositionNo} (Total ${m.myPositionTotal})'),
            if (writeBlocked)
              Padding(
                padding: const EdgeInsets.only(top: 10),
                child: ServiceLimitedBanner(
                  message: resolvedBlocked ? 'Market résolu: achats désactivés.' : writeBlockedMessage(readOnly: readOnly, degradedBlocked: degradedBlocked, runtimeReason: _bannerReason),
                ),
              ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              children: [100, 250, 500, 1000]
                  .map((e) => ChoiceChip(
                        label: Text('$e'),
                        selected: _amount == e,
                        onSelected: writeBlocked ? null : (_) => setState(() => _amount = e),
                      ))
                  .toList(),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _customCtrl,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Montant tickets'),
              onSubmitted: (v) {
                final parsed = int.tryParse(v);
                if (parsed == null || parsed < 1) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Montant invalide (minimum 1).')),
                  );
                  return;
                }
                setState(() => _amount = parsed);
              },
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: FilledButton(
                    onPressed: (_submitting || writeBlocked) ? null : () => _submit('yes'),
                    child: const Text('Buy YES'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton(
                    onPressed: (_submitting || writeBlocked) ? null : () => _submit('no'),
                    child: const Text('Buy NO'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            const Text('My History', style: TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            ..._history.map((h) => ListTile(
                  dense: true,
                  title: Text('${h.side.toUpperCase()} - ${h.amount}'),
                  subtitle: Text(h.status),
                  trailing: Text(TimeOfDay.fromDateTime(h.ts).format(context)),
                )),
            if (_nextCursor != null)
              TextButton(onPressed: _loadMoreHistory, child: const Text('Charger plus')),
          ],
        ),
      ),
    );
  }
}
