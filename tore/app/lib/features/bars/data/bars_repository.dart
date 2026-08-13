import 'package:dio/dio.dart';

import '../../../shared/cache/cache_store.dart';
import '../../../shared/cache/offline_no_cache_exception.dart';
import '../../../shared/models/bar.dart';
import '../../../shared/models/event_summary.dart';

class BarsResult<T> {
  const BarsResult({
    required this.items,
    required this.fromCache,
    required this.lastSyncAt,
  });

  final List<T> items;
  final bool fromCache;
  final DateTime lastSyncAt;
}

class BarsRepository {
  final Dio _dio;
  final CacheStore _cache;

  BarsRepository(this._dio, {CacheStore? cacheStore})
      : _cache = cacheStore ?? CacheStore();

  Future<BarsResult<Bar>> fetchBars() async {
    const cacheKey = 'bars_v2_list';
    try {
      final res = await _dio.get('/bars');
      final data = (res.data as List).cast<dynamic>();
      final syncedAt = DateTime.now().toUtc();
      await _cache.setJson(
          cacheKey,
          <String, dynamic>{
            'items': data,
            'lastSyncAt': syncedAt.toIso8601String(),
          },
          ttl: const Duration(hours: 24));
      return BarsResult(
        items: data
            .map((e) => Bar.fromJson(Map<String, dynamic>.from(e as Map)))
            .toList(),
        fromCache: false,
        lastSyncAt: syncedAt,
      );
    } catch (_) {
      final cached = await _cache.getJson(cacheKey);
      final items = cached?['items'];
      if (items is List<dynamic>) {
        return BarsResult(
          items: items
              .map((e) => Bar.fromJson(Map<String, dynamic>.from(e as Map)))
              .toList(),
          fromCache: true,
          lastSyncAt:
              DateTime.tryParse((cached?['lastSyncAt'] ?? '').toString()) ??
                  DateTime.fromMillisecondsSinceEpoch(0, isUtc: true),
        );
      }
      throw const OfflineNoCacheException('bars');
    }
  }

  Future<Bar> fetchBar(int barId) async {
    final cacheKey = 'bar_v2_detail_$barId';
    try {
      final res = await _dio.get('/bars/$barId/public');
      final payload = Map<String, dynamic>.from(res.data as Map);
      await _cache.setJson(cacheKey, payload, ttl: const Duration(hours: 24));
      return Bar.fromJson(payload);
    } catch (_) {
      final cached = await _cache.getJson(cacheKey);
      if (cached != null) return Bar.fromJson(cached);
      throw const OfflineNoCacheException('bar_detail');
    }
  }

  Future<BarsResult<EventSummary>> getBarEvents(int barId) async {
    final cacheKey = 'bar_v2_events_$barId';
    try {
      final res = await _dio.get('/bars/$barId/events');
      final items = (res.data as List<dynamic>).cast<dynamic>();
      final syncedAt = DateTime.now().toUtc();
      await _cache.setJson(
          cacheKey,
          <String, dynamic>{
            'items': items,
            'lastSyncAt': syncedAt.toIso8601String(),
          },
          ttl: const Duration(hours: 24));
      return BarsResult(
        items: items
            .map((row) =>
                EventSummary.fromJson(Map<String, dynamic>.from(row as Map)))
            .toList(),
        fromCache: false,
        lastSyncAt: syncedAt,
      );
    } catch (_) {
      final cached = await _cache.getJson(cacheKey);
      final items = cached?['items'];
      if (items is List<dynamic>) {
        return BarsResult(
          items: items
              .map((row) =>
                  EventSummary.fromJson(Map<String, dynamic>.from(row as Map)))
              .toList(),
          fromCache: true,
          lastSyncAt:
              DateTime.tryParse((cached?['lastSyncAt'] ?? '').toString()) ??
                  DateTime.fromMillisecondsSinceEpoch(0, isUtc: true),
        );
      }
      throw const OfflineNoCacheException('bar_events');
    }
  }
}
