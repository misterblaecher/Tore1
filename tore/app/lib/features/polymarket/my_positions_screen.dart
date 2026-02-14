import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/error_mapper.dart';
import '../../state.dart';
import 'market_detail_screen.dart';
import 'polymarket_models.dart';

class MyPositionsScreen extends ConsumerStatefulWidget {
  const MyPositionsScreen({super.key, required this.scope, required this.eventId});

  final String scope;
  final int? eventId;

  @override
  ConsumerState<MyPositionsScreen> createState() => _MyPositionsScreenState();
}

class _MyPositionsScreenState extends ConsumerState<MyPositionsScreen> {
  final _ctrl = ScrollController();
  List<PositionRow> _items = [];
  String? _nextCursor;
  bool _loading = true;
  bool _paging = false;
  String? _error;
  final Set<int> _seenMarketIds = <int>{};
  final Set<String> _seenCursors = <String>{};

  @override
  void initState() {
    super.initState();
    _ctrl.addListener(() {
      if (_ctrl.position.pixels > _ctrl.position.maxScrollExtent - 260) _loadMore();
    });
    _refresh();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  Future<void> _refresh() async {
    setState(() {
      _items = [];
      _nextCursor = null;
      _loading = true;
      _error = null;
      _seenMarketIds.clear();
      _seenCursors.clear();
    });
    await _loadMore();
  }

  Future<void> _loadMore() async {
    if (_paging) return;
    if (!_loading && _nextCursor == null) return;
    if (_nextCursor != null && _seenCursors.contains(_nextCursor)) return;
    if (_nextCursor != null) _seenCursors.add(_nextCursor!);
    _paging = true;
    try {
      final page = await ref.read(apiProvider).fetchMyPositions(
            scope: widget.scope,
            eventId: widget.eventId,
            status: 'open',
            cursor: _nextCursor,
          );
      if (!mounted) return;
      setState(() {
        final fresh = page.items.where((e) => _seenMarketIds.add(e.marketId)).toList();
        _items = [..._items, ...fresh];
        _nextCursor = page.nextCursor;
        _error = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = ErrorMapper.message(e));
    } finally {
      _paging = false;
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Positions')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : (_error != null)
                ? ListView(
                    children: [
                      const SizedBox(height: 180),
                      Center(child: Text(_error!)),
                      const SizedBox(height: 12),
                      Center(child: OutlinedButton(onPressed: _refresh, child: const Text('Réessayer'))),
                    ],
                  )
                : _items.isEmpty
                    ? ListView(
                        children: const [
                          SizedBox(height: 200),
                          Center(child: Text('Aucune position pour le moment.')),
                        ],
                      )
            : ListView.builder(
                controller: _ctrl,
                itemCount: _items.length + 1,
                itemBuilder: (_, i) {
                  if (i == _items.length) {
                    if (_nextCursor == null) return const SizedBox(height: 30);
                    return Padding(
                      padding: const EdgeInsets.all(12),
                      child: Center(
                        child: OutlinedButton.icon(
                          onPressed: _loadMore,
                          icon: const Icon(Icons.expand_more),
                          label: const Text('Charger plus'),
                        ),
                      ),
                    );
                  }
                  final p = _items[i];
                  return ListTile(
                    title: Text(p.question, maxLines: 2, overflow: TextOverflow.ellipsis),
                    subtitle: Text('Total ${p.total} | ${p.status}${p.outcome != null ? ' | outcome ${p.outcome}' : ''}'),
                    onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => MarketDetailScreen(marketId: p.marketId))),
                  );
                },
              ),
      ),
    );
  }
}
