import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_context/app_context.dart';
import '../../../core/network/error_mapper.dart';
import '../../../state.dart';
import '../../events/presentation/event_config_providers.dart';
import '../../polymarket/market_detail_screen.dart';
import '../../polymarket/my_positions_screen.dart';
import '../../polymarket/polymarket_models.dart';

class PolymarketTabScreen extends ConsumerStatefulWidget {
  const PolymarketTabScreen({super.key});

  @override
  ConsumerState<PolymarketTabScreen> createState() => _PolymarketTabScreenState();
}

class _PolymarketTabScreenState extends ConsumerState<PolymarketTabScreen> {
  final _scrollController = ScrollController();
  List<MarketLite> _items = [];
  String? _nextCursor;
  bool _loading = false;
  bool _initialLoading = true;
  bool _hasError = false;
  String? _error;
  String? _errorKind;
  String _scope = 'global';
  String _status = 'live';
  final Set<int> _seenIds = <int>{};
  final Set<String> _seenCursors = <String>{};

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    WidgetsBinding.instance.addPostFrameCallback((_) => _refresh());
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _refresh() async {
    setState(() {
      _initialLoading = true;
      _hasError = false;
      _error = null;
      _errorKind = null;
      _nextCursor = null;
      _items = [];
      _seenIds.clear();
      _seenCursors.clear();
    });
    await _loadMore();
  }

  void _onScroll() {
    if (_scrollController.position.pixels > _scrollController.position.maxScrollExtent - 280) {
      _loadMore();
    }
  }

  Future<void> _loadMore() async {
    if (_loading) return;
    if (!_initialLoading && (_nextCursor == null)) return;
    if (_nextCursor != null && _seenCursors.contains(_nextCursor)) return;
    if (_nextCursor != null) _seenCursors.add(_nextCursor!);
    _loading = true;
    final ctx = ref.read(appContextProvider);
    try {
      final page = await ref.read(apiProvider).fetchPolymarketMarkets(
            scope: _scope,
            eventId: _scope == 'event' ? ctx.activeEventId : null,
            status: _status,
            cursor: _nextCursor,
          );
      if (!mounted) return;
      setState(() {
        final fresh = page.items.where((e) => _seenIds.add(e.id)).toList();
        _items = [..._items, ...fresh];
        _nextCursor = page.nextCursor;
        _initialLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _hasError = true;
        _error = ErrorMapper.message(e);
        _errorKind = _resolveErrorKind(e);
        _initialLoading = false;
      });
    } finally {
      _loading = false;
    }
  }

  String _resolveErrorKind(Object e) {
    if (ErrorMapper.isForbidden(e)) return 'denied';
    if (ErrorMapper.isOffline(e)) return 'offline';
    return 'generic';
  }

  @override
  Widget build(BuildContext context) {
    final ctx = ref.watch(appContextProvider);
    final hasEvent = ctx.hasActiveEvent;
    final eventConfig = hasEvent ? ref.watch(eventConfigProvider(ctx.activeEventId!)) : null;
    final polymarketEnabled = eventConfig?.maybeWhen(
          data: (cfg) => cfg.polymarketEnabled,
          orElse: () => true,
        ) ?? true;

    if (hasEvent && !polymarketEnabled) {
      return Scaffold(
        appBar: AppBar(title: const Text('Polymarket')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.block_outlined, size: 44),
                const SizedBox(height: 8),
                const Text('Module Polymarket indisponible pour cet event.'),
                const SizedBox(height: 12),
                FilledButton(
                  onPressed: () => ref.read(appContextProvider.notifier).leaveEvent(),
                  child: const Text('Retour'),
                )
              ],
            ),
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Polymarket'),
        actions: [
          IconButton(
            tooltip: 'My Positions',
            onPressed: () {
              Navigator.of(context).push(MaterialPageRoute(builder: (_) => MyPositionsScreen(scope: _scope, eventId: _scope == 'event' ? ctx.activeEventId : null)));
            },
            icon: const Icon(Icons.account_balance_wallet_outlined),
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Expanded(
                  child: SegmentedButton<String>(
                    segments: [
                      const ButtonSegment(value: 'global', label: Text('GLOBAL')),
                      if (hasEvent) const ButtonSegment(value: 'event', label: Text('EVENT')),
                    ],
                    selected: {_scope},
                    onSelectionChanged: (s) {
                      setState(() => _scope = s.first);
                      _refresh();
                    },
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'live', label: Text('Live')),
                ButtonSegment(value: 'resolved', label: Text('Resolved')),
                ButtonSegment(value: 'cancelled', label: Text('Cancelled')),
              ],
              selected: {_status},
              onSelectionChanged: (s) {
                setState(() => _status = s.first);
                _refresh();
              },
            ),
          ),
          const SizedBox(height: 6),
          Expanded(
            child: RefreshIndicator(
              onRefresh: _refresh,
              child: _buildList(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildList() {
    if (_initialLoading) return const Center(child: CircularProgressIndicator());
    if (_hasError) {
      final title = _errorKind == 'offline'
          ? 'Tu es hors-ligne.'
          : (_errorKind == 'denied' ? 'Accès refusé.' : 'Impossible de charger les marchés.');
      return ListView(
        children: [
          const SizedBox(height: 180),
          Center(child: Text(title)),
          const SizedBox(height: 8),
          Center(child: Text(_error ?? 'Erreur')),
          const SizedBox(height: 12),
          Center(child: OutlinedButton(onPressed: _refresh, child: const Text('Réessayer'))),
        ],
      );
    }
    if (_items.isEmpty) {
      return ListView(
        children: const [
          SizedBox(height: 200),
          Center(child: Text('Aucun market disponible pour ce filtre.')),
        ],
      );
    }

    return ListView.builder(
      controller: _scrollController,
      itemCount: _items.length + 1,
      itemBuilder: (context, i) {
        if (i == _items.length) {
          if (_nextCursor == null) return const SizedBox(height: 32);
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Center(
              child: OutlinedButton.icon(
                onPressed: _loadMore,
                icon: const Icon(Icons.expand_more),
                label: const Text('Charger plus'),
              ),
            ),
          );
        }
        final m = _items[i];
        return _CompactCard(
          market: m,
          onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => MarketDetailScreen(marketId: m.id))),
        );
      },
    );
  }
}

class _CompactCard extends StatelessWidget {
  const _CompactCard({required this.market, required this.onTap});

  final MarketLite market;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    String statusLabel() {
      if (market.status == 'resolved') return 'RESOLU';
      if (market.status == 'cancelled') return 'CANCEL';
      return 'LIVE';
    }

    final yesPct = (market.yesPrice * 100).toStringAsFixed(0);
    final noPct = (market.noPrice * 100).toStringAsFixed(0);
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                Expanded(
                  child: Text(
                    market.question,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                ),
                const SizedBox(width: 8),
                Chip(label: Text(statusLabel())),
              ]),
              Row(
                children: [
                  Text('YES $yesPct%'),
                  const Spacer(),
                  Text('NO $noPct%'),
                ],
              ),
              const SizedBox(height: 4),
              Text('Volume: ${market.volume}'),
              if (market.myPositionTotal > 0)
                Text('My position: YES ${market.myPositionYes} / NO ${market.myPositionNo} (Total ${market.myPositionTotal})'),
            ],
          ),
        ),
      ),
    );
  }
}
