import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../api.dart';
import '../../core/network/network_state_provider.dart';
import '../../state.dart';
import '../../shared/cache/cache_providers.dart';
import 'ticker_models.dart';

class TickerState {
  final List<TickerItem> items;
  final String? nextCursor;
  final bool loading;
  final String? error;
  final bool unstableConnection;
  final DateTime? lastSyncAt;

  const TickerState({
    this.items = const [],
    this.nextCursor,
    this.loading = false,
    this.error,
    this.unstableConnection = false,
    this.lastSyncAt,
  });

  TickerState copyWith({
    List<TickerItem>? items,
    String? nextCursor,
    bool? loading,
    String? error,
    bool? unstableConnection,
    DateTime? lastSyncAt,
  }) {
    return TickerState(
      items: items ?? this.items,
      nextCursor: nextCursor ?? this.nextCursor,
      loading: loading ?? this.loading,
      error: error,
      unstableConnection: unstableConnection ?? this.unstableConnection,
      lastSyncAt: lastSyncAt ?? this.lastSyncAt,
    );
  }
}

class TickerController extends StateNotifier<TickerState> {
  TickerController(this.ref, this.eventId) : super(const TickerState(loading: true)) {
    _bootstrap();
  }

  final Ref ref;
  final int eventId;
  Timer? _pollTimer;
  static const int _maxItems = 100;

  String get _cacheKey => 'ticker_$eventId';

  Future<void> _bootstrap() async {
    await _loadCache();
    await refresh();
    _startPolling();
  }

  Future<void> _loadCache() async {
    final cache = ref.read(cacheStoreProvider);
    final cached = await cache.getJson(_cacheKey);
    if (cached == null) return;
    final raw = (cached['items'] as List<dynamic>? ?? const []);
    final parsed = raw
        .whereType<Map>()
        .map((e) => TickerItem.fromJson(Map<String, dynamic>.from(e)))
        .toList();
    state = state.copyWith(items: _dedup(parsed), loading: false);
  }

  Future<void> _saveCache() async {
    final cache = ref.read(cacheStoreProvider);
    await cache.setJson(_cacheKey, {
      'items': state.items.take(_maxItems).map((e) => {
        'id': e.id,
        'type': e.type,
        'ts': e.ts.toIso8601String(),
        'severity': e.severity,
        'moduleKey': e.moduleKey,
        'payloadCompact': switch (e.payload) {
          BroadcastTickerPayload p => {'message': p.message, 'level': p.level},
          OrderTickerPayload p => {'kind': p.kind, 'orderId': p.orderId, 'status': p.status, 'totalTickets': p.totalTickets, 'userLabel': p.userLabel},
          PriceTickerPayload p => {'drinkName': p.drinkName, 'fromPrice': p.fromPrice, 'toPrice': p.toPrice, 'direction': p.direction},
          GiftTickerPayload p => {'amount': p.amount, 'fromLabel': p.fromLabel, 'toLabel': p.toLabel},
          _ => <String, dynamic>{},
        }
      }).toList(),
      'lastSyncAt': state.lastSyncAt?.toIso8601String(),
    }, ttl: const Duration(days: 1));
  }

  Future<void> refresh() async {
    state = state.copyWith(loading: true, error: null);
    final network = ref.read(networkStatusProvider);
    if (network == NetworkState.offline) {
      state = state.copyWith(loading: false, unstableConnection: true);
      return;
    }
    try {
      final api = ref.read(apiProvider);
      final since = state.items.isNotEmpty ? state.items.first.ts.toIso8601String() : null;
      final page = await api.tickerFeed(eventId, since: since, limit: 50);
      final raw = (page['items'] as List<dynamic>? ?? []).cast<Map<String, dynamic>>();
      final parsed = raw.map(TickerItem.fromJson).toList();
      final merged = _dedup([...parsed, ...state.items])..sort((a, b) => b.ts.compareTo(a.ts));
      final clipped = merged.take(_maxItems).toList();
      state = state.copyWith(
        items: clipped,
        nextCursor: page['nextCursor']?.toString() ?? page['next_cursor']?.toString(),
        loading: false,
        unstableConnection: false,
        lastSyncAt: DateTime.now(),
      );
      await _saveCache();
    } on DioException catch (e) {
      if (e.response?.statusCode == 429) {
        state = state.copyWith(loading: false, error: 'rate limited', unstableConnection: true);
      } else {
        state = state.copyWith(loading: false, error: 'connexion instable', unstableConnection: true);
      }
    } catch (_) {
      state = state.copyWith(loading: false, error: 'connexion instable', unstableConnection: true);
    }
  }

  void _startPolling() {
    _pollTimer?.cancel();
    final network = ref.read(networkStatusProvider);
    if (network == NetworkState.offline) return;
    final seconds = network == NetworkState.degraded ? 5 : 2;
    _pollTimer = Timer.periodic(Duration(seconds: seconds), (_) => refresh());
  }

  List<TickerItem> _dedup(List<TickerItem> values) {
    final seen = <String>{};
    return values.where((e) => seen.add(e.id)).toList();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }
}

final AutoDisposeStateNotifierProviderFamily<TickerController, TickerState, int>
    tickerControllerProvider = StateNotifierProvider.autoDispose
        .family<TickerController, TickerState, int>((ref, eventId) {
      ref.listen(networkStatusProvider, (_, __) {
        ref.read(tickerControllerProvider(eventId).notifier)._startPolling();
      });
      return TickerController(ref, eventId);
    });
