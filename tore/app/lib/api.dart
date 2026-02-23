import 'package:dio/dio.dart';

import 'core/network/api_client.dart';
import 'features/hunt/hunt_models.dart';
import 'features/glossary/glossary_models.dart';
import 'features/battles/battle_models.dart';
import 'features/polymarket/polymarket_models.dart';
import 'features/safety/safety_models.dart';
import 'features/community/community_models.dart';
import 'features/community/data/orga_events_cache.dart';
import 'features/events/domain/event_public_view.dart';
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

class EventMapFetchResult {
  final Map<String, dynamic> payload;
  final bool fromCache;

  const EventMapFetchResult({required this.payload, required this.fromCache});
}

class CalendarEventsFetchResult {
  final List<Map<String, dynamic>> items;
  final bool fromCache;

  const CalendarEventsFetchResult({required this.items, required this.fromCache});
}

class Api {
  final ApiClient _client;
  final CacheStore _cache;
  final OrgaEventsCache _orgaEventsCache;

  Api.fromClient(this._client, {CacheStore? cacheStore, OrgaEventsCache? orgaEventsCache})
      : _cache = cacheStore ?? CacheStore(),
        _orgaEventsCache = orgaEventsCache ?? OrgaEventsCache();

  // Si tu veux garder l'ancien constructeur temporairement :
  Api(String baseUrl)
      : _client = ApiClient.create(baseUrl: baseUrl),
        _cache = CacheStore(),
        _orgaEventsCache = OrgaEventsCache();

  Future<List<dynamic>> bars() async =>
      (await _client.dio.get('/bars')).data as List<dynamic>;

  Future<List<dynamic>> events(int barId) async =>
      (await _client.dio.get('/bars/$barId/events')).data as List<dynamic>;

  // DEPRECATED legacy: préférer la version typée `myEvents()` plus bas.
  Future<Map<String, dynamic>> myEventsRaw() async =>
      Map<String, dynamic>.from((await _client.dio.get('/me/events')).data as Map);

  Future<Map<String, dynamic>> createSimpleEvent({
    required String name,
    required DateTime startsAt,
    required String venue,
  }) async {
    final end = startsAt.add(const Duration(hours: 6));
    final res = await _client.dio.post('/events', data: {
      'name': name,
      'starts_at': startsAt.toIso8601String(),
      'ends_at': end.toIso8601String(),
      if (venue.trim().isNotEmpty) 'venue': venue.trim(),
    });
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> teamEventCheckin({required int eventId}) async {
    final res = await _client.dio.post('/events/$eventId/checkin');
    return Map<String, dynamic>.from(res.data as Map);
  }

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

  Future<SafetyState> getSafetyState(int eventId) async {
    final data = Map<String, dynamic>.from((await _client.dio.get('/events/$eventId/safety/state')).data as Map);
    return SafetyState.fromJson(data);
  }

  Future<Map<String, dynamic>> setSafetyBuddy({
    required int eventId,
    required String buddyUserId,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/safety/buddy',
      data: {'buddyUserId': buddyUserId},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> safetyCheckin({
    required int eventId,
    required String type,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/safety/checkin',
      data: {'type': type},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<SafetyHistoryResponse> getSafetyHistory(int eventId, {int limit = 50}) async {
    final data = Map<String, dynamic>.from(
      (await _client.dio.get('/events/$eventId/safety/history', queryParameters: {'limit': limit})).data as Map,
    );
    return SafetyHistoryResponse.fromJson(data);
  }

  Future<ActiveHunt> getActiveHunt(int eventId) async {
    final data = Map<String, dynamic>.from((await _client.dio.get('/events/$eventId/hunts/active')).data as Map);
    return ActiveHunt.fromJson(data);
  }

  Future<HuntClaimResponse> claimHunt({
    required int eventId,
    required int huntId,
    required int checkpointId,
    required String token,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/hunts/$huntId/claim',
      data: {'checkpointId': checkpointId, 'token': token},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return HuntClaimResponse.fromJson(Map<String, dynamic>.from(res.data as Map));
  }

  Future<HuntLeaderboard> getHuntLeaderboard(int eventId, int huntId) async {
    final data = Map<String, dynamic>.from((await _client.dio.get('/events/$eventId/hunts/$huntId/leaderboard')).data as Map);
    return HuntLeaderboard.fromJson(data);
  }

  Future<HuntStealResponse> stealHunt({
    required int eventId,
    required int huntId,
    required String victimUserId,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/hunts/$huntId/steal',
      data: {'victimUserId': victimUserId},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return HuntStealResponse.fromJson(Map<String, dynamic>.from(res.data as Map));
  }


  Future<BattleStatePayload> getBattleState(int eventId) async {
    final data = Map<String, dynamic>.from((await _client.dio.get('/events/$eventId/battles/state')).data as Map);
    return BattleStatePayload.fromJson(data);
  }

  Future<Map<String, dynamic>> battleVote({required int eventId, required int roundId, required String choice, required String idempotencyKey}) async {
    final res = await _client.dio.post('/events/$eventId/battles/vote', data: {'roundId': roundId, 'choice': choice}, options: Options(headers: {'Idempotency-Key': idempotencyKey}));
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<BattleLeaderboard> getBattleLeaderboard(int eventId) async {
    final data = Map<String, dynamic>.from((await _client.dio.get('/events/$eventId/battles/leaderboard')).data as Map);
    return BattleLeaderboard.fromJson(data);
  }

  Future<Map<String, dynamic>> getMusic(int eventId) async =>
      Map<String, dynamic>.from((await _client.dio.get('/events/$eventId/music')).data as Map);


  Future<Map<String, dynamic>> getMusicPreEvent(int eventId) async =>
      Map<String, dynamic>.from((await _client.dio.get('/events/$eventId/music/pre_event')).data as Map);

  Future<Map<String, dynamic>> suggestMusicPreEvent({
    required int eventId,
    required String provider,
    required String externalUrl,
    required String idempotencyKey,
    String title = '',
    String artist = '',
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/music/pre_event/suggest',
      data: {'provider': provider, 'externalUrl': externalUrl, 'title': title, 'artist': artist},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> voteMusicPreEvent({
    required int eventId,
    required int suggestionId,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/music/pre_event/vote',
      data: {'suggestionId': suggestionId},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

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

  Future<Map<String, dynamic>> addMusicCandidate({
    required int eventId,
    required String provider,
    required String externalUrl,
    String? titleHint,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/music/candidates',
      data: {
        'provider': provider,
        'externalUrl': externalUrl,
        if (titleHint != null && titleHint.trim().isNotEmpty) 'titleHint': titleHint.trim(),
      },
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
      '/events/$eventId/music/force',
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
      '/events/$eventId/music/rounds/start',
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
      '/events/$eventId/music/rounds/close',
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
      '/events/$eventId/music/now_playing',
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
      '/events/$eventId/music/skip_winner',
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


  Future<EventPublicView> getEventPublic(int eventId) async {
    final cacheKey = 'event_public_$eventId';
    try {
      final data = Map<String, dynamic>.from((await _client.dio.get('/events/$eventId/public')).data as Map);
      await _cache.setJson(cacheKey, data, ttl: const Duration(hours: 24));
      return EventPublicView.fromJson(data);
    } on DioException {
      final cached = await _cache.getJson(cacheKey);
      if (cached == null) rethrow;
      return EventPublicView.fromJson(cached);
    }
  }

  Future<Map<String, dynamic>> joinPublicEvent({
    required int eventId,
    required String idempotencyKey,
    String? acceptedCharterVersion,
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/join_public',
      data: {
        if (acceptedCharterVersion != null) 'accepted_charter_version': acceptedCharterVersion,
      },
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

  Future<List<GlossaryCommittee>> glossaryPublicCommittees() async {
    final data = (await _client.dio.get('/glossary/committees')).data as List<dynamic>;
    return data.whereType<Map>().map((row) => GlossaryCommittee.fromJson(Map<String, dynamic>.from(row))).toList(growable: false);
  }

  Future<GlossarySettings> glossaryPublicSettings(int committeeId) async {
    final data = Map<String, dynamic>.from((await _client.dio.get('/glossary/committees/$committeeId/settings')).data as Map);
    return GlossarySettings.fromJson(data);
  }

  Future<GlossaryTermsPage> glossaryPublicTerms(
    int committeeId, {
    String? query,
    List<String>? tags,
    int? year,
    String? cursor,
    int? limit,
  }) async {
    final params = {
      if (query != null && query.isNotEmpty) 'query': query,
      if (tags != null && tags.isNotEmpty) 'tags': tags.join(','),
      if (year != null) 'year': year,
      if (cursor != null && cursor.isNotEmpty) 'cursor': cursor,
      if (limit != null) 'limit': limit,
    };
    final data = Map<String, dynamic>.from((await _client.dio.get('/glossary/committees/$committeeId/terms', queryParameters: params)).data as Map);
    return GlossaryTermsPage.fromJson(data);
  }

  Future<GlossarySettings> committeeGlossarySettings(int committeeId) async {
    final data = Map<String, dynamic>.from((await _client.dio.get('/committees/$committeeId/glossary/settings')).data as Map);
    return GlossarySettings.fromJson(data);
  }

  Future<Map<String, dynamic>> committeeSetGlossarySettings(int committeeId, bool publicEnabled, {required String idempotencyKey}) async {
    final res = await _client.dio.put(
      '/committees/$committeeId/glossary/settings',
      data: {'public_enabled': publicEnabled},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<GlossaryTermsPage> committeeGlossaryTerms(
    int committeeId, {
    String? query,
    List<String>? tags,
    int? year,
    String? cursor,
    int? limit,
  }) async {
    final params = {
      if (query != null && query.isNotEmpty) 'query': query,
      if (tags != null && tags.isNotEmpty) 'tags': tags.join(','),
      if (year != null) 'year': year,
      if (cursor != null && cursor.isNotEmpty) 'cursor': cursor,
      if (limit != null) 'limit': limit,
    };
    final data = Map<String, dynamic>.from((await _client.dio.get('/committees/$committeeId/glossary/terms', queryParameters: params)).data as Map);
    return GlossaryTermsPage.fromJson(data);
  }

  Future<GlossaryTerm> committeeCreateGlossaryTerm(int committeeId, Map<String, dynamic> payload, {required String idempotencyKey}) async {
    final res = await _client.dio.post(
      '/committees/$committeeId/glossary/terms',
      data: payload,
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return GlossaryTerm.fromJson(Map<String, dynamic>.from(res.data as Map));
  }

  Future<GlossaryTerm> committeeUpdateGlossaryTerm(int committeeId, int termId, Map<String, dynamic> payloadPatch, {required String idempotencyKey}) async {
    final res = await _client.dio.put(
      '/committees/$committeeId/glossary/terms/$termId',
      data: payloadPatch,
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return GlossaryTerm.fromJson(Map<String, dynamic>.from(res.data as Map));
  }

  Future<Map<String, dynamic>> committeeArchiveGlossaryTerm(int committeeId, int termId, {required String idempotencyKey}) async {
    final res = await _client.dio.post(
      '/committees/$committeeId/glossary/terms/$termId/archive',
      data: {'reason': 'archived_from_flutter'},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> committeeDeleteGlossaryTerm(int committeeId, int termId, String reason, {required String idempotencyKey}) async {
    final res = await _client.dio.post(
      '/committees/$committeeId/glossary/terms/$termId/delete',
      data: {'reason': reason},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

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

  Future<CommitteeFetchResult> committeeFinancesLedgerWithCacheStatus({
    required int committeeId,
    required int yearId,
  }) async {
    final cacheKey = 'committee_finances_ledger_${committeeId}_$yearId';
    try {
      final data = Map<String, dynamic>.from((await _client.dio.get('/committees/$committeeId/finances/ledger', queryParameters: {'year_id': yearId})).data as Map);
      await _cache.setJson(cacheKey, data, ttl: const Duration(days: 3));
      return CommitteeFetchResult(payload: data, fromCache: false);
    } catch (_) {
      final cached = await _cache.getJson(cacheKey);
      if (cached != null) return CommitteeFetchResult(payload: cached, fromCache: true);
      throw const OfflineNoCacheException('committee_finances_ledger');
    }
  }

  Future<CommitteeFetchResult> committeeFinancesSummaryWithCacheStatus({
    required int committeeId,
    required int yearId,
  }) async {
    final cacheKey = 'committee_finances_summary_${committeeId}_$yearId';
    try {
      final data = Map<String, dynamic>.from((await _client.dio.get('/committees/$committeeId/finances/summary', queryParameters: {'year_id': yearId})).data as Map);
      await _cache.setJson(cacheKey, data, ttl: const Duration(days: 3));
      return CommitteeFetchResult(payload: data, fromCache: false);
    } catch (_) {
      final cached = await _cache.getJson(cacheKey);
      if (cached != null) return CommitteeFetchResult(payload: cached, fromCache: true);
      throw const OfflineNoCacheException('committee_finances_summary');
    }
  }

  Future<Map<String, dynamic>> createCommitteeFinanceEntry({
    required int committeeId,
    required Map<String, dynamic> body,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post('/committees/$committeeId/finances/ledger', data: body, options: Options(headers: {'Idempotency-Key': idempotencyKey}));
    return Map<String, dynamic>.from(res.data as Map);
  }

  String committeeFinancesExportCsvUrl({required int committeeId, required int yearId}) =>
      '${_client.dio.options.baseUrl}/committees/$committeeId/finances/export.csv?year_id=$yearId';

  String committeeFinancesSnapshotUrl({required int committeeId, required int yearId}) =>
      '${_client.dio.options.baseUrl}/committees/$committeeId/finances/snapshot.json?year_id=$yearId';

  Future<Map<String, dynamic>> committeeBaptemeCampaign({required int committeeId, required int yearId}) async =>
      Map<String, dynamic>.from((await _client.dio.get('/committees/$committeeId/bapteme/campaign', queryParameters: {'year_id': yearId})).data as Map);

  Future<Map<String, dynamic>> createCommitteeBaptemeCampaign({
    required int committeeId,
    required int yearId,
    required String name,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post('/committees/$committeeId/bapteme/campaign', data: {'yearId': yearId, 'name': name}, options: Options(headers: {'Idempotency-Key': idempotencyKey}));
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> createCommitteeBaptemeInvite({
    required int committeeId,
    required int campaignId,
    required String blueDisplayName,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post('/committees/$committeeId/bapteme/invites', data: {'campaignId': campaignId, 'blueDisplayName': blueDisplayName}, options: Options(headers: {'Idempotency-Key': idempotencyKey}));
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> committeeBaptemeInvites({required int committeeId, required int campaignId}) async =>
      Map<String, dynamic>.from((await _client.dio.get('/committees/$committeeId/bapteme/invites', queryParameters: {'campaignId': campaignId})).data as Map);

  Future<Map<String, dynamic>> createCommitteeBaptemeSlot({
    required int committeeId,
    required Map<String, dynamic> body,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post('/committees/$committeeId/bapteme/slots', data: body, options: Options(headers: {'Idempotency-Key': idempotencyKey}));
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> committeeBaptemeSlots({required int committeeId, required int campaignId}) async =>
      Map<String, dynamic>.from((await _client.dio.get('/committees/$committeeId/bapteme/slots', queryParameters: {'campaignId': campaignId})).data as Map);

  Future<Map<String, dynamic>> createCommitteeBaptemeAssignment({
    required int committeeId,
    required int inviteId,
    required int slotId,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post('/committees/$committeeId/bapteme/assign', data: {'inviteId': inviteId, 'slotId': slotId}, options: Options(headers: {'Idempotency-Key': idempotencyKey}));
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> createCommitteeBaptemeIncident({
    required int committeeId,
    required int campaignId,
    int? inviteId,
    required String type,
    required String note,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post('/committees/$committeeId/bapteme/incidents', data: {'campaignId': campaignId, 'inviteId': inviteId, 'type': type, 'note': note}..removeWhere((k, v) => v == null), options: Options(headers: {'Idempotency-Key': idempotencyKey}));
    return Map<String, dynamic>.from(res.data as Map);
  }

  String committeeBaptemeInvitesExportUrl({required int committeeId, required int campaignId}) =>
      '${_client.dio.options.baseUrl}/committees/$committeeId/bapteme/export_invites.csv?campaignId=$campaignId';

  String committeeBaptemeSlotsExportUrl({required int committeeId, required int campaignId}) =>
      '${_client.dio.options.baseUrl}/committees/$committeeId/bapteme/export_slots.csv?campaignId=$campaignId';

  Future<List<dynamic>> menu(int eventId) async {
    final result = await menuWithCacheStatus(eventId);
    return result.items;
  }

  Future<EventMapFetchResult> getEventMapWithCacheStatus(int eventId) async {
    final cacheKey = 'event_map_$eventId';
    try {
      final res = await _client.dio.get('/events/$eventId/map');
      final payload = Map<String, dynamic>.from(res.data as Map);
      await _cache.setJson(cacheKey, payload, ttl: const Duration(days: 1));
      return EventMapFetchResult(payload: payload, fromCache: false);
    } catch (_) {
      final cached = await _cache.getJson(cacheKey);
      if (cached != null) {
        return EventMapFetchResult(payload: cached, fromCache: true);
      }
      throw const OfflineNoCacheException('event_map');
    }
  }

  Future<CalendarEventsFetchResult> getCalendarEventsWithCacheStatus({
    required DateTime from,
    required DateTime to,
  }) async {
    final keyFrom = from.toIso8601String();
    final keyTo = to.toIso8601String();
    final cacheKey = 'calendar_events_${keyFrom}_$keyTo';
    try {
      final res = await _client.dio.get('/calendar/events', queryParameters: {
        'from': keyFrom,
        'to': keyTo,
        'scope': 'public',
      });
      final raw = (Map<String, dynamic>.from(res.data as Map)['items'] as List<dynamic>? ?? const []);
      final items = raw.map((e) => Map<String, dynamic>.from(e as Map)).toList();
      await _cache.setJson(cacheKey, {'items': items}, ttl: const Duration(days: 1));
      return CalendarEventsFetchResult(items: items, fromCache: false);
    } catch (_) {
      final cached = await _cache.getJson(cacheKey);
      final items = cached?['items'];
      if (items is List) {
        return CalendarEventsFetchResult(
          items: items.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList(),
          fromCache: true,
        );
      }
      throw const OfflineNoCacheException('calendar_events');
    }
  }

  String getEventIcsUrl(int eventId) => '${_client.dio.options.baseUrl}/calendar/events/$eventId.ics';

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
  Future<Map<String, dynamic>> eventWifiClaim({
    required int eventId,
    required String token,
  }) async {
    final res = await _client.dio.get('/events/$eventId/wifi/claim', queryParameters: {'token': token});
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> getEvent(int eventId) async {
    final res = await _client.dio.get('/events/$eventId');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> listOrgas({
    String? q,
    String? type,
    String? city,
    String? sort,
    String? joinMode,
    String? cursor,
    int limit = 20,
  }) async {
    final res = await _client.dio.get(
      '/orgas',
      queryParameters: {
        if (q != null && q.trim().isNotEmpty) 'q': q.trim(),
        if (type != null && type.trim().isNotEmpty) 'type': type.trim(),
        if (city != null && city.trim().isNotEmpty) 'city': city.trim(),
        if (sort != null && sort.trim().isNotEmpty) 'sort': sort.trim(),
        if (joinMode != null && joinMode.trim().isNotEmpty) 'join_mode': joinMode.trim(),
        if (cursor != null && cursor.trim().isNotEmpty) 'cursor': cursor.trim(),
        'limit': limit,
      },
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<List<Map<String, dynamic>>> myOrgas() async {
    final res = await _client.dio.get('/me/orgas');
    final raw = (res.data as List?) ?? const [];
    return raw.map((e) => Map<String, dynamic>.from(e as Map)).toList();
  }

  Future<Map<String, dynamic>> joinOrgaByCode({required String code, required String idempotencyKey}) async {
    final res = await _client.dio.post(
      '/orgas/join_by_code',
      data: {'code': code},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> createEventV1({
    required Map<String, dynamic> payload,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/events',
      data: payload,
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> publishEventV1({required int eventId, required String idempotencyKey}) async {
    final res = await _client.dio.post(
      '/events/$eventId/publish',
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> getEventShareV1(int eventId) async {
    final res = await _client.dio.get('/events/$eventId/share');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> createStaffInviteCodeV1({
    required int eventId,
    required String idempotencyKey,
    String role = 'ENTRY',
    int expiresInHours = 12,
    String? label,
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/staff_invite_code',
      data: {'role': role, 'expiresInHours': expiresInHours, if (label != null && label.isNotEmpty) 'label': label},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> revokeStaffInviteCodeV1({
    required int eventId,
    required String code,
    required String reason,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/staff_invites/$code/revoke',
      data: {'reason': reason},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }


  Future<Map<String, dynamic>> rotateStaffInviteV1({
    required int eventId,
    required String role,
    required String idempotencyKey,
    int? expiresInMinutes,
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/staff_invites/rotate',
      data: {'role': role, if (expiresInMinutes != null) 'expiresInMinutes': expiresInMinutes},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> getCurrentStaffInvitesV1(int eventId) async {
    final res = await _client.dio.get('/events/$eventId/staff_invites/current');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> joinStaffByInviteV1({
    required int eventId,
    required String code,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/staff/join_by_invite',
      data: {'code': code},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }


  Future<Map<String, dynamic>> joinStaffByBackupCodeV1({
    required int eventId,
    required String code,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/events/$eventId/staff/join_by_backup_code',
      data: {'code': code},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> getEventSharePackV1(int eventId) async {
    final res = await _client.dio.get('/events/$eventId/share_pack');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> createShortlink({
    required String kind,
    int? eventId,
    int? orgaId,
    String? openType,
    int? openId,
    String? openCode,
    int? expiresInSeconds,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/shortlinks',
      data: {
        'kind': kind,
        if (eventId != null) 'event_id': eventId,
        if (orgaId != null) 'orga_id': orgaId,
        if (openType != null) 'open_type': openType,
        if (openId != null) 'open_id': openId,
        if (openCode != null) 'open_code': openCode,
        if (expiresInSeconds != null) 'expiresInSeconds': expiresInSeconds,
      },
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> resolveOpenLink({required String type, String? code, int? id, int? eventId}) async {
    final res = await _client.dio.get('/open', queryParameters: {'type': type, if (code != null) 'code': code, if (id != null) 'id': id, if (eventId != null) 'eventId': eventId});
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> previewManualCode(String code) async {
    final res = await _client.dio.get('/codes/preview', queryParameters: {'code': code});
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> consumeManualCode({required String code, required String idempotencyKey}) async {
    final res = await _client.dio.post(
      '/codes/consume',
      data: {'code': code},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }


  Future<MyEventsFetchResult> myEvents() async {
    const cacheKey = 'my_events_v1';
    try {
      final res = await _client.dio.get('/me/events');
      final payload = Map<String, dynamic>.from(res.data as Map);
      final nowIso = DateTime.now().toIso8601String();
      await _cache.setJson(cacheKey, {'payload': payload, 'lastSyncAt': nowIso}, ttl: const Duration(hours: 24));
      return MyEventsFetchResult(
        buckets: _decodeMyEventBuckets(payload),
        fromCache: false,
        lastSyncAt: DateTime.tryParse(nowIso),
      );
    } catch (_) {
      final cached = await _cache.getJson(cacheKey);
      if (cached != null) {
        final payload = Map<String, dynamic>.from((cached['payload'] as Map?) ?? const <String, dynamic>{});
        final lastSyncAt = DateTime.tryParse((cached['lastSyncAt'] ?? '').toString());
        return MyEventsFetchResult(
          buckets: _decodeMyEventBuckets(payload),
          fromCache: true,
          lastSyncAt: lastSyncAt,
        );
      }
      throw const OfflineNoCacheException('my_events');
    }
  }

  Future<OrgaEventsResult> listOrgaPrivateEvents(int orgId, {String? cursor}) async {
    final cacheKey = _orgaEventsCache.privateKey(orgId);
    try {
      final res = await _client.dio.get('/orgas/$orgId/events/private', queryParameters: {if (cursor != null) 'cursor': cursor});
      final payload = Map<String, dynamic>.from(res.data as Map);
      await _orgaEventsCache.savePrivate(orgId, payload);
      final nowIso = DateTime.now().toUtc().toIso8601String();
      await _cache.setJson(cacheKey, {'payload': payload, 'lastSyncAt': nowIso}, ttl: const Duration(hours: 24));
      return OrgaEventsResult(
        buckets: _decodeMyEventBuckets(payload),
        nextCursor: payload['nextCursor']?.toString(),
        isCached: false,
        lastSyncAt: DateTime.tryParse(nowIso),
      );
    } catch (_) {
      final cached = await _cache.getJson(cacheKey);
      if (cached != null) {
        final payload = Map<String, dynamic>.from((cached['payload'] as Map?) ?? const <String, dynamic>{});
        return OrgaEventsResult(
          buckets: _decodeMyEventBuckets(payload),
          nextCursor: payload['nextCursor']?.toString(),
          isCached: true,
          lastSyncAt: DateTime.tryParse((cached['lastSyncAt'] ?? '').toString()),
        );
      }
      throw const OfflineNoCacheException('orga_private_events');
    }
  }

  Future<Map<String, List<MyEventSummary>>> orgaPrivateEvents(int orgId, {String? cursor}) async {
    final result = await listOrgaPrivateEvents(orgId, cursor: cursor);
    return result.buckets;
  }

  Future<ManageSnapshot> eventManageSnapshot(int eventId) async {
    final res = await _client.dio.get('/events/$eventId/manage_snapshot');
    return ManageSnapshot.fromJson(Map<String, dynamic>.from(res.data as Map));
  }

  Map<String, List<MyEventSummary>> _decodeMyEventBuckets(Map<String, dynamic> payload) {
    const keys = <String>['LIVE', 'TODAY', 'UPCOMING', 'PAST'];
    final out = <String, List<MyEventSummary>>{};
    for (final key in keys) {
      final raw = (payload[key] as List?) ?? const [];
      out[key] = raw.whereType<Map>().map((e) => MyEventSummary.fromJson(Map<String, dynamic>.from(e))).toList();
    }
    return out;
  }

  Future<OrgaEventsResult> listOrgaPublicEvents(int orgId) async {
    final cacheKey = _orgaEventsCache.publicKey(orgId);
    try {
      final res = await _client.dio.get('/orgas/$orgId/events');
      final payload = Map<String, dynamic>.from(res.data as Map);
      await _orgaEventsCache.savePublic(orgId, payload);
      final buckets = _decodeOrgaPublicBuckets(payload);
      final nowIso = DateTime.now().toUtc().toIso8601String();
      await _cache.setJson(cacheKey, {'payload': {'items': payload['items'] ?? const []}, 'lastSyncAt': nowIso}, ttl: const Duration(hours: 24));
      return OrgaEventsResult(buckets: buckets, nextCursor: null, isCached: false, lastSyncAt: DateTime.tryParse(nowIso));
    } catch (_) {
      final cached = await _cache.getJson(cacheKey);
      if (cached != null) {
        final payload = Map<String, dynamic>.from((cached['payload'] as Map?) ?? const <String, dynamic>{});
        return OrgaEventsResult(
          buckets: _decodeOrgaPublicBuckets(payload),
          nextCursor: null,
          isCached: true,
          lastSyncAt: DateTime.tryParse((cached['lastSyncAt'] ?? '').toString()),
        );
      }
      throw const OfflineNoCacheException('orga_public_events');
    }
  }


  Map<String, List<MyEventSummary>> _decodeOrgaPublicBuckets(Map<String, dynamic> payload) {
    final out = <String, List<MyEventSummary>>{'LIVE': [], 'TODAY': [], 'UPCOMING': [], 'PAST': []};
    final items = (payload['items'] as List?) ?? const [];
    for (final raw in items.whereType<Map>()) {
      final row = Map<String, dynamic>.from(raw);
      final bucket = (row['bucket'] ?? 'UPCOMING').toString().toUpperCase();
      out.putIfAbsent(bucket, () => []);
      out[bucket]!.add(MyEventSummary.fromJson(row));
    }
    return out;
  }

  Future<Map<String, dynamic>> getOrga(int orgId) async {
    final res = await _client.dio.get('/orgas/$orgId');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> getOrgaShare(int orgId) async {
    final res = await _client.dio.get('/orgas/$orgId/share');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> getOrgaInvite(int orgId) async {
    final res = await _client.dio.get('/orgas/$orgId/invite');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> orgaCreateInvite({required int orgId, required String inviteType, int? expiresInHours, required String idempotencyKey}) async {
    final res = await _client.dio.post(
      '/orgas/$orgId/invites',
      data: {'inviteType': inviteType, if (expiresInHours != null) 'expiresInHours': expiresInHours},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> orgaListInvites({required int orgId}) async {
    final res = await _client.dio.get('/orgas/$orgId/invites');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> orgaRevokeInvite({required int orgId, required int inviteId, required String reason, required String idempotencyKey}) async {
    final res = await _client.dio.post(
      '/orgas/$orgId/invites/$inviteId/revoke',
      data: {'reason': reason},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> orgaJoinByInvite({required String code, required String idempotencyKey}) async {
    final res = await _client.dio.post('/orgas/join_by_invite', data: {'code': code}, options: Options(headers: {'Idempotency-Key': idempotencyKey}));
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> orgaInvitePreview({required String code}) async {
    final res = await _client.dio.get('/orgas/invites/$code/preview');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> listOrgaPosts(int orgId) async {
    final res = await _client.dio.get('/orgas/$orgId/posts');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> orgaJoin({required int orgId, required String idempotencyKey}) async {
    final res = await _client.dio.post('/orgas/$orgId/join', options: Options(headers: {'Idempotency-Key': idempotencyKey}));
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> orgaLeave({required int orgId, required String idempotencyKey}) async {
    final res = await _client.dio.post('/orgas/$orgId/leave', options: Options(headers: {'Idempotency-Key': idempotencyKey}));
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> orgaMyMembership({required int orgId}) async {
    final res = await _client.dio.get('/orgas/$orgId/memberships/me');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> orgaMembers({required int orgId}) async {
    final res = await _client.dio.get('/orgas/$orgId/memberships');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> updateOrga({
    required int orgId,
    required Map<String, dynamic> payload,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.put(
      '/orgas/$orgId',
      data: payload,
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> orgaSetMembershipRole({
    required int orgId,
    required String userId,
    required String role,
    required String reason,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/orgas/$orgId/memberships/$userId/set_role',
      data: {'role': role, 'reason': reason},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> orgaRemoveMembership({
    required int orgId,
    required String userId,
    required String reason,
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.post(
      '/orgas/$orgId/memberships/$userId/remove',
      data: {'reason': reason},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> orgaApproveMember({required int orgId, required String userId, required String idempotencyKey, String? reason}) async {
    final res = await _client.dio.post('/orgas/$orgId/memberships/$userId/approve', data: {if (reason != null && reason.isNotEmpty) 'reason': reason}, options: Options(headers: {'Idempotency-Key': idempotencyKey}));
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> orgaRejectMember({required int orgId, required String userId, required String reason, required String idempotencyKey}) async {
    final res = await _client.dio.post('/orgas/$orgId/memberships/$userId/reject', data: {'reason': reason}, options: Options(headers: {'Idempotency-Key': idempotencyKey}));
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> followOrga({required int orgId, required String idempotencyKey}) => orgaJoin(orgId: orgId, idempotencyKey: idempotencyKey);

  Future<Map<String, dynamic>> unfollowOrga({required int orgId, required String idempotencyKey}) => orgaLeave(orgId: orgId, idempotencyKey: idempotencyKey);

  Future<Map<String, dynamic>> createOrgaPost({required int orgId, required String text, required String idempotencyKey}) async {
    final res = await _client.dio.post('/orgas/$orgId/posts', data: {'text': text}, options: Options(headers: {'Idempotency-Key': idempotencyKey}));
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> pinOrgaPost({required int orgId, required int postId, required String idempotencyKey}) async {
    final res = await _client.dio.post('/orgas/$orgId/posts/$postId/pin', options: Options(headers: {'Idempotency-Key': idempotencyKey}));
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> deleteOrgaPost({required int orgId, required int postId, required String idempotencyKey}) async {
    final res = await _client.dio.post('/orgas/$orgId/posts/$postId/delete', options: Options(headers: {'Idempotency-Key': idempotencyKey}));
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> myProfileV2() async {
    final res = await _client.dio.get('/me/profile');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> updateMyProfileV2({
    required String displayName,
    String? photoUrl,
    String? bio,
    String? instagramHandle,
    String visibility = 'PUBLIC',
    required String idempotencyKey,
  }) async {
    final res = await _client.dio.put(
      '/me/profile',
      data: {
        'display_name': displayName,
        'photo_url': photoUrl,
        'bio': bio,
        'instagram_handle': instagramHandle,
        'visibility': visibility,
      },
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

}
