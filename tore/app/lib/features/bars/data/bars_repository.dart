import 'package:dio/dio.dart';

import '../../../shared/cache/cache_store.dart';
import '../../../shared/cache/offline_no_cache_exception.dart';
import '../../../shared/models/bar.dart';
import '../../../shared/models/event_summary.dart';

class BarsRepository {
  final Dio _dio;
  final CacheStore _cache;

  BarsRepository(this._dio, {CacheStore? cacheStore}) : _cache = cacheStore ?? CacheStore();

  Future<List<Bar>> fetchBars() async {
    const cacheKey = 'bars_list';
    try {
      final res = await _dio.get('/bars');
      final data = (res.data as List).cast<dynamic>();
      await _cache.setJson(cacheKey, <String, dynamic>{'items': data}, ttl: const Duration(minutes: 10));
      return data.map((e) => Bar.fromJson(Map<String, dynamic>.from(e as Map))).toList();
    } catch (_) {
      final cached = await _cache.getJson(cacheKey);
      final items = cached?['items'];
      if (items is List<dynamic>) {
        return items.map((e) => Bar.fromJson(Map<String, dynamic>.from(e as Map))).toList();
      }
      rethrow;
    }
  }

  Future<List<EventSummary>> getBarEvents(int barId) async {
    final cacheKey = 'bar_events_$barId';
    try {
      final res = await _dio.get('/bars/$barId/events');
      final items = (res.data as List<dynamic>).cast<dynamic>();
      await _cache.setJson(cacheKey, <String, dynamic>{'items': items}, ttl: const Duration(minutes: 10));
      return items
          .map((row) => EventSummary.fromJson(Map<String, dynamic>.from(row as Map)))
          .toList();
    } catch (_) {
      final cached = await _cache.getJson(cacheKey);
      final items = cached?['items'];
      if (items is List<dynamic>) {
        return items
            .map((row) => EventSummary.fromJson(Map<String, dynamic>.from(row as Map)))
            .toList();
      }
      throw const OfflineNoCacheException('bar_events');
    }
  }
}
