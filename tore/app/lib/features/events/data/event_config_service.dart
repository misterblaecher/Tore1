import 'package:dio/dio.dart';

import '../../../shared/cache/cache_store.dart';
import '../../../shared/cache/offline_no_cache_exception.dart';
import '../../../shared/models/event_config.dart';

class EventConfigService {
  EventConfigService(this._dio, this._cache);

  final Dio _dio;
  final CacheStore _cache;

  Future<EventConfig> fetchEventConfig(int eventId) async {
    final cacheKey = 'event_config_$eventId';
    try {
      final res = await _dio.get(
        '/events/$eventId/config',
        options: Options(
          connectTimeout: const Duration(seconds: 5),
          receiveTimeout: const Duration(seconds: 5),
          sendTimeout: const Duration(seconds: 5),
        ),
      );
      final json = Map<String, dynamic>.from(res.data as Map);
      await _cache.setJson(cacheKey, json, ttl: const Duration(minutes: 10));
      return EventConfig.fromJson(json);
    } catch (_) {
      final cached = await _cache.getJson(cacheKey);
      if (cached != null) {
        return EventConfig.fromJson(cached);
      }
      throw const OfflineNoCacheException('event_config');
    }
  }

  Future<EventConfig> patchEventConfig(int eventId, Map<String, dynamic> payload) async {
    final res = await _dio.patch('/events/$eventId/config', data: payload);
    return EventConfig.fromJson(Map<String, dynamic>.from(res.data as Map));
  }
}
