import 'package:dio/dio.dart';

import 'core/network/api_client.dart';
import 'features/polymarket/polymarket_models.dart';
import 'shared/cache/cache_store.dart';
import 'shared/cache/offline_no_cache_exception.dart';

class MenuFetchResult {
  final List<dynamic> items;
  final bool fromCache;

  const MenuFetchResult({required this.items, required this.fromCache});
}

class EventRankingFetchResult {
  final Map<String, dynamic> payload;
  final bool fromCache;

  const EventRankingFetchResult({required this.payload, required this.fromCache});
}

class CommitteeFetchResult {
  final dynamic payload;
  final bool fromCache;

  const CommitteeFetchResult({required this.payload, required this.fromCache});
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

  Future<Map<String, dynamic>> eventContext(int eventId) async =>
      Map<String, dynamic>.from(
        (await _client.dio.get('/events/$eventId/context')).data as Map,
      );

  Future<Map<String, dynamic>> eventState(int eventId) async =>
      Map<String, dynamic>.from(
        (await _client.dio.get('/events/$eventId/state')).data as Map,
      );

  Future<Map<String, dynamic>> getMusic(int eventId) async =>
      Map<String, dynamic>.from((await _client.dio.get('/events/$eventId/music')).data as Map);

  Future<Map<String, dynamic>> voteMusic({
    required int eventId,
    required Map<String, dynamic> candidate,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/music/vote',
      data: {'candidate': candidate},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> adminMusicSettings({
    required int eventId,
    required Map<String, dynamic> payload,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/music/admin/settings',
      data: payload,
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> adminMusicForce({
    required int eventId,
    required Map<String, dynamic> candidate,
    required String idempotencyKey,
    String? reason,
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/music/admin/force',
      data: {'candidate': candidate, if (reason != null) 'reason': reason},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }


  Future<Map<String, dynamic>> adminMusicRoundStart({
    required int eventId,
    required int durationSec,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/music/admin/round/start',
      data: {'durationSec': durationSec},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> adminMusicRoundEnd({
    required int eventId,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/music/admin/round/end',
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> adminMusicNowPlaying({
    required int eventId,
    required Map<String, dynamic> candidate,
    required String idempotencyKey,
    String? reason,
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/music/admin/now-playing',
      data: {'candidate': candidate, if (reason != null) 'reason': reason},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> adminMusicSkip({
    required int eventId,
    required String idempotencyKey,
    required String reason,
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/music/admin/skip',
      data: {'reason': reason},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }
  Future<Map<String, dynamic>> adminMusicClear({
    required int eventId,
    required String idempotencyKey,
    String? reason,
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/music/admin/clear',
      data: {if (reason != null) 'reason': reason},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> joinEvent({
    required int eventId,
    String? idempotencyKey,
    String? acceptedCharterVersion,
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/join',
      data: {
        if (acceptedCharterVersion != null) 'accepted_charter_version': acceptedCharterVersion,
      },
      options: idempotencyKey == null ? null : Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> joinEventByCode({
    required String code,
    String? idempotencyKey,
    String? acceptedCharterVersion,
  }) async {
    final res = await _client.dio.post(
      '/events/join_by_code',
      data: {
        'code': code,
        if (acceptedCharterVersion != null) 'accepted_charter_version': acceptedCharterVersion,
      },
      options: idempotencyKey == null ? null : Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> eventCharter(int eventId) async {
    final res = await _client.dio.get('/events/$eventId/charter');
    return Map<String, dynamic>.from(res.data as Map);
  }



  Future<Map<String, dynamic>> modulesState() async =>
      Map<String, dynamic>.from((await _client.dio.get('/modules')).data as Map);

  Future<CommitteeFetchResult> committeesWithCacheStatus() async {
    const cacheKey = 'committees_list';
    try {
      final data = (await _client.dio.get('/committees')).data as List<dynamic>;
      await _cache.setJson(cacheKey, {'items': data}, ttl: const Duration(days: 1));
      return CommitteeFetchResult(payload: data, fromCache: false);
    } catch (_) {
      final cached = await _cache.getJson(cacheKey);
      final items = cached?['items'];
      if (items is List<dynamic>) return CommitteeFetchResult(payload: items, fromCache: true);
      throw const OfflineNoCacheException('committees_list');
    }
  }

  Future<Map<String, dynamic>> committee(int committeeId) async =>
      Map<String, dynamic>.from((await _client.dio.get('/committees/$committeeId')).data as Map);

  Future<List<dynamic>> committeeYears(int committeeId) async =>
      (await _client.dio.get('/committees/$committeeId/years')).data as List<dynamic>;

  Future<CommitteeFetchResult> committeeMeWithCacheStatus(int committeeId) async {
    final cacheKey = 'committee_me_$committeeId';
    try {
      final data = Map<String, dynamic>.from((await _client.dio.get('/committees/$committeeId/me')).data as Map);
      await _cache.setJson(cacheKey, data, ttl: const Duration(days: 1));
      return CommitteeFetchResult(payload: data, fromCache: false);
    } catch (_) {
      final cached = await _cache.getJson(cacheKey);
      if (cached != null) return CommitteeFetchResult(payload: cached, fromCache: true);
      throw const OfflineNoCacheException('committee_me');
    }
  }

  Future<Map<String, dynamic>> committeeJoinByCode({
    required int committeeId,
    required String code,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/committees/$committeeId/join_by_code',
      data: {'code': code},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> committeeMembers(int committeeId) async =>
      Map<String, dynamic>.from((await _client.dio.get('/committees/$committeeId/members')).data as Map);

  Future<Map<String, dynamic>> createCommitteeInviteCode({
    required int committeeId,
    String? expiresAtIso,
    int? usesLeft,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/committees/$committeeId/invite_codes',
      data: {'expiresAt': expiresAtIso, 'usesLeft': usesLeft},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> setCommitteeMemberRole({
    required int committeeId,
    required String userId,
    required String role,
    required String reason,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/committees/$committeeId/members/$userId/role',
      data: {'role': role, 'reason': reason},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> revokeCommitteeMember({
    required int committeeId,
    required String userId,
    required String reason,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/committees/$committeeId/members/$userId/revoke',
      data: {'reason': reason},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<CommitteeFetchResult> committeeForumCategoriesWithCacheStatus({
    required int committeeId,
    required int yearId,
  }) async {
    final cacheKey = 'committee_forum_categories_${committeeId}_$yearId';
    try {
      final data = (await _client.dio.get('/committees/$committeeId/forum/categories', queryParameters: {'year_id': yearId})).data as List<dynamic>;
      await _cache.setJson(cacheKey, {'items': data}, ttl: const Duration(days: 7));
      return CommitteeFetchResult(payload: data, fromCache: false);
    } catch (_) {
      final cached = await _cache.getJson(cacheKey);
      final items = cached?['items'];
      if (items is List<dynamic>) return CommitteeFetchResult(payload: items, fromCache: true);
      throw const OfflineNoCacheException('committee_forum_categories');
    }
  }

  Future<CommitteeFetchResult> committeeForumPostsWithCacheStatus({
    required int committeeId,
    required int yearId,
    required int categoryId,
    String? cursor,
    int limit = 20,
  }) async {
    final cacheKey = 'committee_forum_posts_${committeeId}_${yearId}_$categoryId';
    try {
      final data = Map<String, dynamic>.from(
        (await _client.dio.get(
          '/committees/$committeeId/forum/posts',
          queryParameters: {'year_id': yearId, 'category_id': categoryId, if (cursor != null) 'cursor': cursor, 'limit': limit},
        ))
            .data as Map,
      );
      await _cache.setJson(cacheKey, data, ttl: const Duration(days: 7));
      return CommitteeFetchResult(payload: data, fromCache: false);
    } catch (_) {
      final cached = await _cache.getJson(cacheKey);
      if (cached != null) return CommitteeFetchResult(payload: cached, fromCache: true);
      throw const OfflineNoCacheException('committee_forum_posts');
    }
  }

  Future<Map<String, dynamic>> committeeForumPostDetail({required int committeeId, required int postId}) async =>
      Map<String, dynamic>.from((await _client.dio.get('/committees/$committeeId/forum/posts/$postId')).data as Map);

  Future<Map<String, dynamic>> createCommitteeForumPost({
    required int committeeId,
    required int yearId,
    required int categoryId,
    required String title,
    required String body,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/committees/$committeeId/forum/posts',
      data: {'yearId': yearId, 'categoryId': categoryId, 'title': title, 'body': body},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> committeeForumModAction({
    required int committeeId,
    required int postId,
    required String action,
    required Map<String, dynamic> body,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/committees/$committeeId/forum/posts/$postId/$action',
      data: body,
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> createCommitteeForumCategory({
    required int committeeId,
    required int yearId,
    required String name,
    int? orderIndex,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/committees/$committeeId/forum/categories',
      data: {'yearId': yearId, 'name': name, if (orderIndex != null) 'orderIndex': orderIndex},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> updateCommitteeForumCategory({
    required int committeeId,
    required int categoryId,
    String? name,
    int? orderIndex,
    bool? isArchived,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.put(
      '/committees/$committeeId/forum/categories/$categoryId',
      data: {'name': name, 'orderIndex': orderIndex, 'isArchived': isArchived}..removeWhere((key, value) => value == null),
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

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

  Future<EventRankingFetchResult> eventRankingWithCacheStatus(int eventId) async {
    final cacheKey = 'event_ranking_$eventId';
    try {
      final res = await _client.dio.get(
        '/events/$eventId/ranking',
        options: Options(
          connectTimeout: const Duration(seconds: 5),
          receiveTimeout: const Duration(seconds: 5),
          sendTimeout: const Duration(seconds: 5),
        ),
      );
      final payload = Map<String, dynamic>.from(res.data as Map);
      await _cache.setJson(cacheKey, payload, ttl: const Duration(days: 7));
      return EventRankingFetchResult(payload: payload, fromCache: false);
    } catch (_) {
      final cached = await _cache.getJson(cacheKey);
      if (cached != null) {
        return EventRankingFetchResult(payload: cached, fromCache: true);
      }
      throw const OfflineNoCacheException('event_ranking');
    }
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
    required int barId,
    required int eventId,
    required String userId,
    required String paymentMode,
    required List<Map<String, dynamic>> items,
    String? zoneId,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/orders',
      data: {
        'bar_id': barId,
        'event_id': eventId,
        'user_id': userId,
        'payment_mode': paymentMode,
        'items': items,
        if (zoneId != null && zoneId.isNotEmpty) 'zone_id': int.tryParse(zoneId),
        'idempotency_key': idempotencyKey,
      },
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }




  Future<Map<String, dynamic>> getOrder(int orderId) async {
    final res = await _client.dio.get('/orders/$orderId');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> liveOrders({required int eventId, String? status, String? cursor, int limit = 40}) async {
    final res = await _client.dio.get(
      '/orders/live',
      queryParameters: {
        'event_id': eventId,
        if (status != null && status.isNotEmpty) 'status': status,
        if (cursor != null && cursor.isNotEmpty) 'cursor': cursor,
        'limit': limit,
      },
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> issueOrderClientQr({
    required int orderId,
    String? idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/orders/$orderId/client-qr',
      options: idempotencyKey == null
          ? null
          : Options(headers: {'Idempotency-Key': idempotencyKey}),
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

  Future<Map<String, dynamic>> broadcasts(int eventId, {int limit = 50}) async {
    final res = await _client.dio.get(
      '/events/$eventId/broadcasts',
      queryParameters: {'limit': limit},
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> tickerFeed(int eventId, {String? cursor, String? since, List<String>? types, int limit = 50}) async {
    final res = await _client.dio.get(
      '/events/$eventId/ticker',
      queryParameters: {
        if (cursor != null && cursor.isNotEmpty) 'cursor': cursor,
        if (since != null && since.isNotEmpty) 'since': since,
        if (types != null && types.isNotEmpty) 'types': types.join(','),
        'limit': limit,
      },
    );
    return Map<String, dynamic>.from(res.data as Map);
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

  Future<Map<String, dynamic>> walletMe() async {
    final res = await _client.dio.get('/wallet/me');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> walletLedger({String? cursor, int limit = 30}) async {
    final res = await _client.dio.get(
      '/wallet/me/ledger',
      queryParameters: {
        if (cursor != null && cursor.isNotEmpty) 'cursor': cursor,
        'limit': limit,
      },
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> walletGift({
    required String toUserId,
    required int amountCents,
    required String idempotencyKey,
    int? eventId,
  }) async {
    final res = await _client.dio.post(
      '/wallet/transfers',
      data: {
        if (eventId != null) 'event_id': eventId,
        'to_user_id': toUserId,
        'amount': amountCents,
      },
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> walletGiftReceiveQr({int? eventId}) async {
    final res = await _client.dio.get(
      '/wallet/gifts/receive-qr',
      queryParameters: {
        if (eventId != null) 'event_id': eventId,
      },
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> mePrivacy() async {
    final res = await _client.dio.get('/me/privacy');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> putMePrivacy({
    required String visibility,
    required bool showIdentityInBar,
  }) async {
    final key = 'privacy-$visibility-${showIdentityInBar ? 1 : 0}';
    final res = await _client.dio.put(
      '/me/privacy',
      data: {
        'visibility': visibility,
        'show_identity_in_bar': showIdentityInBar,
      },
      options: Options(headers: {'Idempotency-Key': key}),
    );
    return Map<String, dynamic>.from(res.data as Map);
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



  Future<CursorPage<MarketLite>> fetchPolymarketMarkets({
    required String scope,
    int? eventId,
    required String status,
    String type = 'all',
    String? cursor,
    int limit = 20,
  }) async {
    final endpoint = scope == 'global'
        ? '/polymarket/global'
        : (scope == 'event' && eventId != null ? '/events/$eventId/polymarket' : '/polymarket/markets');
    final params = scope == 'global'
        ? <String, dynamic>{
            'status': status,
            'type': type,
            if (cursor != null && cursor.isNotEmpty) 'cursor': cursor,
            'limit': limit,
          }
        : endpoint.startsWith('/events/')
        ? <String, dynamic>{
            'status': status,
            'type': type,
            if (cursor != null && cursor.isNotEmpty) 'cursor': cursor,
            'limit': limit,
          }
        : <String, dynamic>{
            'scope': scope,
            if (eventId != null) 'event_id': eventId,
            'status': status,
            if (cursor != null && cursor.isNotEmpty) 'cursor': cursor,
            'limit': limit,
          };
    final res = await _client.dio.get(
      endpoint,
      queryParameters: params,
    );
    final data = Map<String, dynamic>.from(res.data as Map);
    final items = ((data['items'] as List?) ?? const [])
        .map((e) => MarketLite.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
    return CursorPage(items: items, nextCursor: data['next_cursor']?.toString());
  }

  Future<MarketDetailResponse> fetchPolymarketMarket(int marketId, {String? cursor, int limit = 20}) async {
    final res = await _client.dio.get(
      '/polymarket/markets/$marketId',
      queryParameters: {
        if (cursor != null && cursor.isNotEmpty) 'cursor': cursor,
        'limit': limit,
      },
    );
    final data = Map<String, dynamic>.from(res.data as Map);
    return MarketDetailResponse.fromJson(data);
  }

  Future<Map<String, dynamic>> postPolymarketPosition({
    required int marketId,
    int? eventId,
    required String side,
    required int amountCents,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      eventId == null ? '/polymarket/markets/$marketId/buy' : '/events/$eventId/polymarket/$marketId/buy',
      data: {
        'side': side,
        'amountTickets': amountCents,
      },
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> createEventPolymarketMarket({
    required int eventId,
    required String question,
    required String type,
    String? rules,
  }) async {
    final idem = 'event-create-$eventId-${DateTime.now().millisecondsSinceEpoch}';
    final res = await _client.dio.post(
      '/events/$eventId/polymarket',
      data: {'question': question, 'type': type, if (rules != null) 'rules': rules},
      options: Options(headers: {'Idempotency-Key': idem}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> resolveEventPolymarketMarket({
    required int eventId,
    required int marketId,
    required String outcome,
    required String reason,
  }) async {
    final idem = 'event-resolve-$eventId-$marketId-${DateTime.now().millisecondsSinceEpoch}';
    final res = await _client.dio.post(
      '/events/$eventId/polymarket/$marketId/resolve',
      data: {'outcome': outcome, 'reason': reason},
      options: Options(headers: {'Idempotency-Key': idem}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<CursorPage<PositionRow>> fetchMyPositions({
    required String scope,
    int? eventId,
    String status = 'open',
    String? cursor,
    int limit = 20,
  }) async {
    final res = await _client.dio.get(
      '/polymarket/positions',
      queryParameters: {
        'scope': scope,
        if (eventId != null) 'event_id': eventId,
        'status': status,
        if (cursor != null && cursor.isNotEmpty) 'cursor': cursor,
        'limit': limit,
      },
    );
    final data = Map<String, dynamic>.from(res.data as Map);
    final items = ((data['items'] as List?) ?? const [])
        .map((e) => PositionRow.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
    return CursorPage(items: items, nextCursor: data['next_cursor']?.toString());
  }

  Future<CursorPage<TradeRow>> fetchMyHistory({
    required int marketId,
    String? cursor,
    int limit = 20,
  }) async {
    final res = await _client.dio.get(
      '/polymarket/markets/$marketId/my-history',
      queryParameters: {
        if (cursor != null && cursor.isNotEmpty) 'cursor': cursor,
        'limit': limit,
      },
    );
    final data = Map<String, dynamic>.from(res.data as Map);
    final items = ((data['items'] as List?) ?? const [])
        .map((e) => TradeRow.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
    return CursorPage(items: items, nextCursor: data['next_cursor']?.toString());
  }
  Future<Map<String, dynamic>> getEvent(int eventId) async {
    final res = await _client.dio.get('/events/$eventId');
    return Map<String, dynamic>.from(res.data as Map);
  }
}
