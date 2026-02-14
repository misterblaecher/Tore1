import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/providers.dart';
import '../../state.dart';
import 'ticker_models.dart';

class TickerState {
  final List<TickerItem> items;
  final String? nextCursor;
  final bool loading;
  final String? error;
  final bool unstableConnection;

  const TickerState({
    this.items = const [],
    this.nextCursor,
    this.loading = false,
    this.error,
    this.unstableConnection = false,
  });

  TickerState copyWith({
    List<TickerItem>? items,
    String? nextCursor,
    bool? loading,
    String? error,
    bool? unstableConnection,
  }) {
    return TickerState(
      items: items ?? this.items,
      nextCursor: nextCursor ?? this.nextCursor,
      loading: loading ?? this.loading,
      error: error,
      unstableConnection: unstableConnection ?? this.unstableConnection,
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
  StreamSubscription<String>? _sseSub;
  int _pollSeconds = 5;

  Future<void> _bootstrap() async {
    await refresh();
    await _connectSse();
    _startPolling();
  }

  Future<void> refresh() async {
    state = state.copyWith(loading: true, error: null);
    try {
      final api = ref.read(apiProvider);
      final page = await api.tickerFeed(eventId, limit: 40);
      final raw = (page['items'] as List<dynamic>? ?? []).cast<Map<String, dynamic>>();
      final parsed = raw.map(TickerItem.fromJson).toList()..sort((a, b) => b.ts.compareTo(a.ts));
      state = state.copyWith(
        items: _dedup(parsed),
        nextCursor: page['next_cursor']?.toString(),
        loading: false,
        unstableConnection: false,
      );
    } on DioException catch (e) {
      if (e.response?.statusCode == 429) {
        _pollSeconds = (_pollSeconds * 2).clamp(5, 30);
      }
      state = state.copyWith(loading: false, error: 'connexion instable', unstableConnection: true);
    } catch (_) {
      state = state.copyWith(loading: false, error: 'connexion instable', unstableConnection: true);
    }
  }

  Future<void> _connectSse() async {
    final dio = ref.read(apiClientProvider).dio;
    try {
      final response = await dio.get<ResponseBody>(
        '/events/$eventId/ticker/stream',
        options: Options(responseType: ResponseType.stream),
      );
      _sseSub = response.data!.stream
          .map((chunk) => chunk.toList())
          .transform(utf8.decoder)
          .transform(const LineSplitter())
          .listen(_handleSseLine, onError: (_) {
        state = state.copyWith(unstableConnection: true);
      });
    } catch (_) {
      state = state.copyWith(unstableConnection: true);
    }
  }

  void _handleSseLine(String line) {
    if (!line.startsWith('data: ')) return;
    final payload = line.substring(6).trim();
    if (payload.isEmpty) return;
    final parsed = TickerItem.fromJson(Map<String, dynamic>.from(jsonDecode(payload) as Map));
    final merged = _dedup([parsed, ...state.items])..sort((a, b) => b.ts.compareTo(a.ts));
    state = state.copyWith(items: merged, unstableConnection: false);
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(Duration(seconds: _pollSeconds), (_) => refresh());
  }

  List<TickerItem> _dedup(List<TickerItem> values) {
    final seen = <String>{};
    return values.where((e) => seen.add(e.id)).toList();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _sseSub?.cancel();
    super.dispose();
  }
}

final tickerControllerProvider = StateNotifierProvider.autoDispose
    .family<TickerController, TickerState, int>((ref, eventId) {
  return TickerController(ref, eventId);
});
