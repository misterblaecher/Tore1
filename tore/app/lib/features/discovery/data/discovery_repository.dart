import 'dart:convert';

import 'package:dio/dio.dart';

import '../../../shared/cache/cache_store.dart';
import '../../../shared/cache/cache_fallback.dart';
import '../../../shared/cache/offline_no_cache_exception.dart';
import '../domain/discovery_models.dart';

class DiscoveryRepository {
  DiscoveryRepository(this._dio, this._cache);

  final Dio _dio;
  final CacheStore _cache;

  Future<DiscoveryResult> fetchEvents(DiscoveryQuery query) async {
    final cacheKey = _cacheKey(query);
    try {
      final response = await _dio.get(
        '/events',
        queryParameters: query.toQueryParameters(),
      );
      final items = (response.data as List<dynamic>)
          .whereType<Map>()
          .map((item) => Map<String, dynamic>.from(item))
          .toList(growable: false);
      final syncedAt = DateTime.now().toUtc();
      await _cache.setJson(
        cacheKey,
        {
          'items': items,
          'lastSyncAt': syncedAt.toIso8601String(),
        },
        ttl: const Duration(hours: 24),
      );
      return DiscoveryResult(
        events: items.map(DiscoveryEvent.fromJson).toList(growable: false),
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
      final items = cached?['items'];
      if (items is List<dynamic>) {
        final lastSyncAt =
            DateTime.tryParse((cached?['lastSyncAt'] ?? '').toString()) ??
                DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);
        return DiscoveryResult(
          events: items
              .whereType<Map>()
              .map((item) =>
                  DiscoveryEvent.fromJson(Map<String, dynamic>.from(item)))
              .toList(growable: false),
          fromCache: true,
          lastSyncAt: lastSyncAt,
        );
      }
      throw const OfflineNoCacheException('discovery_events');
    }
  }

  String _cacheKey(DiscoveryQuery query) {
    final canonical = jsonEncode(query.toQueryParameters());
    return 'discovery_events_v2_${base64Url.encode(utf8.encode(canonical))}';
  }
}
