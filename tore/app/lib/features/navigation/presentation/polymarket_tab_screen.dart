import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_context/app_context.dart';
import '../../../core/network/error_mapper.dart';
import '../../../core/network/network_state_provider.dart';
import '../../../shared/cache/cache_providers.dart';
import '../../../state.dart';
import '../../events/presentation/event_config_providers.dart';
import '../../polymarket/market_detail_screen.dart';
import '../../polymarket/my_positions_screen.dart';
import '../../polymarket/polymarket_models.dart';

class PolymarketTabScreen extends ConsumerStatefulWidget {
  const PolymarketTabScreen({super.key, this.initialScope = 'global'});

  final String initialScope;

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
  String _scope = 'global';
  String _filter = 'all';
  final Set<int> _seenIds = <int>{};
  final Set<String> _seenCursors = <String>{};
  bool _fromCache = false;

  @override
  void initState() {
    super.initState();
    _scope = widget.initialScope;
    _scrollController.addListener(_onScroll);
    WidgetsBinding.instance.addPostFrameCallback((_) => _refresh());
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  String get _cacheKey => 'polymarket_global_$_filter';

  ({String status, String type}) get _queryFilters {
    switch (_filter) {
      case 'live':
        return (status: 'live', type: 'all');
      case 'objective':
        return (status: 'all', type: 'objective');
      case 'subjective':
        return (status: 'all', type: 'subjective');
      case 'resolved':
        return (status: 'resolved', type: 'all');
      default:
        return (status: 'all', type: 'all');
    }
  }

  Future<void> _refresh() async {
    setState(() {
      _initialLoading = true;
      _hasError = false;
      _error = null;
      _nextCursor = null;
      _items = [];
      _fromCache = false;
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

  Future<void> _hydrateCache() async {
    final cached = await ref.read(cacheStoreProvider).getJson(_cacheKey);
    if (cached == null) return;
    final raw = (cached['items'] as List<dynamic>? ?? const []);
    final items = raw.map((e) => MarketLite.fromJson(Map<String, dynamic>.from(e as Map))).toList();
    if (!mounted || items.isEmpty) return;
    setState(() {
      _items = items;
      _seenIds
        ..clear()
        ..addAll(items.map((e) => e.id));
      _nextCursor = null;
      _hasError = false;
      _fromCache = true;
      _initialLoading = false;
    });
  }

  Future<void> _loadMore() async {
    if (_loading) return;
    if (!_initialLoading && (_nextCursor == null)) return;
    if (_nextCursor != null && _seenCursors.contains(_nextCursor)) return;
    if (_nextCursor != null) _seenCursors.add(_nextCursor!);
    _loading = true;
    final ctx = ref.read(appContextProvider);
    final q = _queryFilters;
    try {
      final page = await ref.read(apiProvider).fetchPolymarketMarkets(
            scope: _scope,
            eventId: _scope == 'event' ? ctx.activeEventId : null,
            status: q.status,
            type: q.type,
            cursor: _nextCursor,
          );
      if (!mounted) return;
      setState(() {
        final fresh = page.items.where((e) => _seenIds.add(e.id)).toList();
        _items = [..._items, ...fresh];
        _nextCursor = page.nextCursor;
        _initialLoading = false;
        _fromCache = false;
      });
      if (_scope == 'global' && _nextCursor == null) {
        await ref.read(cacheStoreProvider).setJson(
          _cacheKey,
          {'items': _items.map((e) => {'id': e.id, 'question': e.question, 'status': e.status, 'scope': e.scope, 'type': e.type, 'yesPrice': e.yesPrice, 'noPrice': e.noPrice, 'yesPct': e.yesPct, 'noPct': e.noPct, 'poolTickets': e.poolTickets, 'volumeTickets': e.volume}).toList()},
          ttl: const Duration(minutes: 30),
        );
      }
    } catch (e) {
      if (!mounted) return;
      await _hydrateCache();
      if (_items.isNotEmpty) return;
      setState(() {
        _hasError = true;
        _error = ErrorMapper.message(e);
        _initialLoading = false;
      });
    } finally {
      _loading = false;
    }
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

    if (hasEvent && !polymarketEnabled && _scope == 'event') {
      return Scaffold(appBar: AppBar(title: const Text('Polymarket')), body: const Center(child: Text('Module Polymarket indisponible pour cet event.')));
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
          if (hasEvent)
            Padding(
              padding: const EdgeInsets.all(12),
              child: SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: 'global', label: Text('GLOBAL')),
                  ButtonSegment(value: 'event', label: Text('EVENT')),
                ],
                selected: {_scope},
                onSelectionChanged: (s) {
                  setState(() => _scope = s.first);
                  _refresh();
                },
              ),
            ),
          SizedBox(
            height: 40,
            child: ListView(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              scrollDirection: Axis.horizontal,
              children: [
                _chip('all', 'Tous'),
                _chip('live', 'Live'),
                _chip('objective', 'Objectifs'),
                _chip('subjective', 'Subjectifs'),
                _chip('resolved', 'Résolus'),
              ],
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

  Widget _chip(String value, String label) => Padding(
        padding: const EdgeInsets.only(right: 8),
        child: ChoiceChip(
          selected: _filter == value,
          label: Text(label),
          onSelected: (_) {
            setState(() => _filter = value);
            _refresh();
          },
        ),
      );

  Widget _buildList() {
    if (_initialLoading) return const Center(child: CircularProgressIndicator());
    if (_hasError) {
      return ListView(children: [const SizedBox(height: 180), Center(child: Text(_error ?? 'Erreur')), const SizedBox(height: 12), Center(child: OutlinedButton(onPressed: _refresh, child: const Text('Réessayer')))]);
    }
    if (_items.isEmpty) {
      return ListView(children: const [SizedBox(height: 200), Center(child: Text('Aucun market disponible pour ce filtre.'))]);
    }

    final network = ref.watch(networkStatusProvider);
    return ListView.builder(
      controller: _scrollController,
      itemCount: _items.length + 2,
      itemBuilder: (context, i) {
        if (i == 0 && (network == NetworkState.offline || _fromCache)) {
          return const Padding(
            padding: EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            child: Text('Offline • affichage du cache local', style: TextStyle(color: Colors.orange)),
          );
        }
        final index = i - 1;
        if (index == _items.length) {
          if (_nextCursor == null) return const SizedBox(height: 32);
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Center(child: OutlinedButton.icon(onPressed: _loadMore, icon: const Icon(Icons.expand_more), label: const Text('Charger plus'))),
          );
        }
        if (index < 0) return const SizedBox.shrink();
        final m = _items[index];
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
    final yesPct = (market.yesPct * 100).toStringAsFixed(0);
    final noPct = (market.noPct * 100).toStringAsFixed(0);
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
              Row(children: [Expanded(child: Text(market.question, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600))), Chip(label: Text(market.status.toUpperCase()))]),
              LinearProgressIndicator(value: market.yesPct, minHeight: 8),
              const SizedBox(height: 4),
              Row(children: [Text('YES $yesPct%'), const Spacer(), Text('NO $noPct%')]),
              const SizedBox(height: 4),
              Text('Pool: ${market.poolTickets} • Volume: ${market.volume}'),
            ],
          ),
        ),
      ),
    );
  }
}
