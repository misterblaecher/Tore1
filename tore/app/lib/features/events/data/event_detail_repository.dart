import 'package:dio/dio.dart';

import '../../../shared/cache/cache_store.dart';
import '../../../shared/cache/cache_fallback.dart';
import '../../../shared/cache/offline_no_cache_exception.dart';
import '../domain/event_public_view.dart';

class EventDetailResult {
  const EventDetailResult({
    required this.event,
    required this.fromCache,
    required this.lastSyncAt,
  });

  final EventPublicView event;
  final bool fromCache;
  final DateTime lastSyncAt;
}

class EventDetailRepository {
  EventDetailRepository(this._dio, this._cache);

  final Dio _dio;
  final CacheStore _cache;

  Future<EventDetailResult> fetchEvent(int eventId) async {
    final cacheKey = 'event_detail_v3_$eventId';
    try {
      final response = await _dio.get('/events/$eventId/public');
      final payload = Map<String, dynamic>.from(response.data as Map);
      final syncedAt = DateTime.now().toUtc();
      await _cache.setJson(
        cacheKey,
        {'payload': payload, 'lastSyncAt': syncedAt.toIso8601String()},
        ttl: const Duration(hours: 24),
      );
      return EventDetailResult(
        event: EventPublicView.fromJson(payload),
        fromCache: false,
        lastSyncAt: syncedAt,
      );
    } catch (error) {
      if (!canUseCacheAfter(error)) {
        if (error is DioException &&
            [401, 403, 404, 410].contains(error.response?.statusCode)) {
          await _cache.clearKey(cacheKey);
        }
        rethrow;
      }
      final cached = await _cache.getJson(cacheKey);
      final payload = cached?['payload'];
      if (payload is Map) {
        return EventDetailResult(
          event: EventPublicView.fromJson(Map<String, dynamic>.from(payload)),
          fromCache: true,
          lastSyncAt:
              DateTime.tryParse((cached?['lastSyncAt'] ?? '').toString()) ??
                  DateTime.fromMillisecondsSinceEpoch(0, isUtc: true),
        );
      }
      throw const OfflineNoCacheException('event_detail');
    }
  }

  Future<Map<String, dynamic>> joinEvent({
    required int eventId,
    required String idempotencyKey,
    String? acceptedCharterVersion,
  }) async {
    final response = await _dio.post(
      '/events/$eventId/join_public',
      data: {
        if (acceptedCharterVersion != null)
          'accepted_charter_version': acceptedCharterVersion,
      },
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> fetchCharter(int eventId) async {
    final response = await _dio.get('/events/$eventId/charter');
    return Map<String, dynamic>.from(response.data as Map);
  }
}
