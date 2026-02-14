import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/error_mapper.dart';
import '../../state.dart';
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
        _nextCursor = res.nextCursor;
      });
      await _resolveRuntimeBlock();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(ErrorMapper.message(e))));
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
    if (reason == 'event_paused' || reason == 'read_only' || reason == 'frozen') return reason;
    if (json['event_paused'] == true || state == 'pause' || state == 'paused') return 'event_paused';
    if (json['read_only'] == true || state == 'read_only') return 'read_only';
    if (json['frozen'] == true || state == 'frozen') return 'frozen';
    return null;
  }

  bool get _writeBlocked => _bannerReason == 'event_paused' || _bannerReason == 'read_only' || _bannerReason == 'frozen';

  Future<void> _submit(String side) async {
    if (_submitting || _writeBlocked || _market == null) return;
    setState(() => _submitting = true);
    final key = 'pm-${widget.marketId}-${side.toLowerCase()}-$_amount';
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
      if (msg.contains('pause')) setState(() => _bannerReason = 'event_paused');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _loadMoreHistory() async {
    if (_nextCursor == null) return;
    try {
      final page = await ref.read(apiProvider).fetchMyHistory(marketId: widget.marketId, cursor: _nextCursor);
      if (!mounted) return;
      setState(() {
        _history = [..._history, ...page.items];
        _nextCursor = page.nextCursor;
      });
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return Scaffold(appBar: AppBar(title: const Text('Market')), body: const Center(child: CircularProgressIndicator()));
    final m = _market;
    if (m == null) return Scaffold(appBar: AppBar(title: const Text('Market')), body: const Center(child: Text('Introuvable')));
    return Scaffold(
      appBar: AppBar(title: const Text('Market Detail')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.all(14),
          children: [
            Text(m.question, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            Text('Status: ${m.status} | YES ${(m.yesPrice * 100).toStringAsFixed(0)}% / NO ${(m.noPrice * 100).toStringAsFixed(0)}%'),
            Text('Volume: ${m.volume}'),
            if (m.outcome != null) Text('Outcome: ${m.outcome}'),
            const SizedBox(height: 12),
            Text('My position: YES ${m.myPositionYes} / NO ${m.myPositionNo} (Total ${m.myPositionTotal})'),
            if (_bannerReason != null)
              Container(
                margin: const EdgeInsets.only(top: 10),
                padding: const EdgeInsets.all(10),
                color: Colors.amber.shade100,
                child: Text('Trading désactivé: $_bannerReason'),
              ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              children: [100, 250, 500, 1000]
                  .map((e) => ChoiceChip(
                        label: Text('$e'),
                        selected: _amount == e,
                        onSelected: (_) => setState(() => _amount = e),
                      ))
                  .toList(),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _customCtrl,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Custom amount (cents)'),
              onSubmitted: (v) {
                final parsed = int.tryParse(v);
                if (parsed != null && parsed > 0) setState(() => _amount = parsed);
              },
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: FilledButton(
                    onPressed: (_submitting || _writeBlocked) ? null : () => _submit('yes'),
                    child: const Text('YES'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton(
                    onPressed: (_submitting || _writeBlocked) ? null : () => _submit('no'),
                    child: const Text('NO'),
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
