import 'package:dio/dio.dart';

import 'core/network/api_client.dart';
import 'shared/cache/cache_store.dart';
import 'shared/cache/offline_no_cache_exception.dart';

class MenuFetchResult {
  final List<dynamic> items;
  final bool fromCache;

  const MenuFetchResult({required this.items, required this.fromCache});
}

class Api {
  final ApiClient _client;
  final CacheStore _cache;

  Api.fromClient(this._client, {CacheStore? cacheStore})
      : _cache = cacheStore ?? CacheStore();

  // Si tu veux garder l'ancien constructeur temporairement :
  Api(String baseUrl)
      : _client = ApiClient.create(baseUrl: baseUrl),
        _cache = CacheStore();

  Future<List<dynamic>> bars() async =>
      (await _client.dio.get('/bars')).data as List<dynamic>;

  Future<List<dynamic>> events(int barId) async =>
      (await _client.dio.get('/bars/$barId/events')).data as List<dynamic>;

  Future<Map<String, dynamic>> event(int eventId) async =>
      Map<String, dynamic>.from(
        (await _client.dio.get('/events/$eventId')).data as Map,
      );

  Future<List<dynamic>> menu(int eventId) async {
    final result = await menuWithCacheStatus(eventId);
    return result.items;
  }

  Future<MenuFetchResult> menuWithCacheStatus(int eventId) async {
    final cacheKey = 'event_menu_$eventId';
    try {
      final res = await _client.dio.get(
        '/events/$eventId/menu',
        options: Options(
          connectTimeout: const Duration(seconds: 5),
          receiveTimeout: const Duration(seconds: 5),
          sendTimeout: const Duration(seconds: 5),
        ),
      );
      final data = (res.data as List<dynamic>).cast<dynamic>();
      await _cache.setJson(
        cacheKey,
        <String, dynamic>{'items': data},
        ttl: const Duration(minutes: 30),
      );
      return MenuFetchResult(items: data, fromCache: false);
    } catch (_) {
      final cached = await _cache.getJson(cacheKey);
      final items = cached?['items'];
      if (items is List<dynamic>) {
        return MenuFetchResult(items: items, fromCache: true);
      }
      throw const OfflineNoCacheException('menu');
    }
  }

  Future<List<dynamic>> leaderboard({int? eventId}) async {
    final res = await _client.dio.get(
      '/leaderboard',
      queryParameters: eventId == null ? null : {'event_id': eventId},
    );
    return res.data as List<dynamic>;
  }

  Future<Map<String, dynamic>> ticketBalance({
    required int eventId,
    required String userId,
  }) async {
    final res = await _client.dio.get(
      '/tickets/balance',
      queryParameters: {'event_id': eventId, 'user_id': userId},
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<void> creditTickets({
    required int eventId,
    required String userId,
    required int delta,
  }) async {
    await _client.dio.post(
      '/tickets/credit',
      data: {'event_id': eventId, 'user_id': userId, 'delta': delta},
    );
  }

  Future<Map<String, dynamic>> createOrder({
    required int eventId,
    required String userId,
    required String payMode,
    required List<Map<String, dynamic>> items,
  }) async {
    final res = await _client.dio.post(
      '/orders',
      data: {
        'event_id': eventId,
        'user_id': userId,
        'pay_mode': payMode,
        'items': items,
      },
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  // -------- MARKET / GRAPHS --------

  /// Price history for a drink during an event.
  /// Backend may expose different routes; we try a couple of common ones.
  Future<List<dynamic>> drinkHistory({
    required int eventId,
    required int drinkId,
    String? range,
  }) async {
    final qp = <String, dynamic>{};
    if (range != null && range.isNotEmpty) qp['range'] = range;

    try {
      final res = await _client.dio.get(
        '/events/$eventId/drinks/$drinkId/history',
        queryParameters: qp.isEmpty ? null : qp,
      );
      return res.data as List<dynamic>;
    } catch (e) {
      // Fallback (some backends expose a generic history endpoint)
      final res = await _client.dio.get(
        '/drinks/$drinkId/history',
        queryParameters: {
          'event_id': eventId,
          ...qp,
        },
      );
      return res.data as List<dynamic>;
    }
  }

  Future<List<dynamic>> topMovers(int eventId) async {
    try {
      final res = await _client.dio.get('/events/$eventId/top_movers');
      return res.data as List<dynamic>;
    } catch (e) {
      final res = await _client.dio.get(
        '/top_movers',
        queryParameters: {'event_id': eventId},
      );
      return res.data as List<dynamic>;
    }
  }

  // -------- TICKER --------

  Future<List<dynamic>> ticker(int eventId) async {
    try {
      final res = await _client.dio.get('/events/$eventId/ticker');
      return res.data as List<dynamic>;
    } catch (e) {
      final res = await _client.dio.get(
        '/ticker',
        queryParameters: {'event_id': eventId},
      );
      return res.data as List<dynamic>;
    }
  }

  // -------- CHECK-IN --------

  Future<Map<String, dynamic>> createCheckin({
    required int eventId,
    required String userId,
    required int drinkId,
    required int qty,
    bool staffMode = false,
  }) async {
    try {
      final res = await _client.dio.post(
        '/events/$eventId/checkins',
        data: {
          'user_id': userId,
          'drink_id': drinkId,
          'qty': qty,
          if (staffMode) 'staff': true,
        },
      );
      return Map<String, dynamic>.from(res.data as Map);
    } catch (e) {
      // Fallback: treat as order (if backend uses /orders for checkins)
      final res = await _client.dio.post(
        '/orders',
        data: {
          'event_id': eventId,
          'user_id': userId,
          'pay_mode': staffMode ? 'checkin_staff' : 'checkin',
          'items': [
            {'drink_id': drinkId, 'qty': qty},
          ],
        },
      );
      return Map<String, dynamic>.from(res.data as Map);
    }
  }

  // -------- WALLET HISTORY --------

  Future<List<dynamic>> walletHistory({
    required int eventId,
    required String userId,
    int? limit,
    String? cursor,
  }) async {
    final qp = <String, dynamic>{'user_id': userId};
    if (limit != null) qp['limit'] = limit;
    if (cursor != null) qp['cursor'] = cursor;

    try {
      final res = await _client.dio.get(
        '/events/$eventId/wallet/history',
        queryParameters: qp,
      );
      return res.data as List<dynamic>;
    } catch (e) {
      final res = await _client.dio.get(
        '/tickets/history',
        queryParameters: {
          'event_id': eventId,
          ...qp,
        },
      );
      return res.data as List<dynamic>;
    }
  }

  // -------- ADMIN --------

  Future<List<dynamic>> adminPrices(int eventId) async {
    final res = await _client.dio.get('/admin/events/$eventId/prices');
    return res.data as List<dynamic>;
  }

  Future<Map<String, dynamic>> setEventPrices({
    required int eventId,
    required List<Map<String, dynamic>> prices,
  }) async {
    final res = await _client.dio.post(
      '/admin/events/$eventId/prices',
      data: {'prices': prices},
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> setTicketValue({
    required int eventId,
    required int ticketValueCents,
  }) async {
    final res = await _client.dio.post(
      '/admin/events/$eventId/ticket_value',
      data: {'ticket_value_cents': ticketValueCents},
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> getEvent(int eventId) async {
    final res = await _client.dio.get('/events/$eventId');
    return Map<String, dynamic>.from(res.data as Map);
  }
}
