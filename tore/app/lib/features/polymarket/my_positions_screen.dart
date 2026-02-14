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
    });
    await _loadMore();
  }

  Future<void> _loadMore() async {
    if (_paging) return;
    if (!_loading && _nextCursor == null) return;
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
        _items = [..._items, ...page.items];
        _nextCursor = page.nextCursor;
      });
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(ErrorMapper.message(e))));
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
            : ListView.builder(
                controller: _ctrl,
                itemCount: _items.length + 1,
                itemBuilder: (_, i) {
                  if (i == _items.length) return _nextCursor == null ? const SizedBox(height: 30) : const Padding(padding: EdgeInsets.all(12), child: Center(child: CircularProgressIndicator()));
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
