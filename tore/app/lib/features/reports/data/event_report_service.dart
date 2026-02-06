import 'package:dio/dio.dart';

import '../../../shared/cache/cache_store.dart';
import '../../../shared/cache/offline_no_cache_exception.dart';
import '../../../shared/models/event_report.dart';

class EventReportFetchResult {
  final EventReport report;
  final bool fromCache;

  const EventReportFetchResult({
    required this.report,
    required this.fromCache,
  });
}

class EventReportService {
  EventReportService(this._dio, this._cache);

  final Dio _dio;
  final CacheStore _cache;

  Future<EventReportFetchResult> fetchReport(int eventId) async {
    final cacheKey = 'event_report_$eventId';
    try {
      final res = await _dio.get(
        '/events/$eventId/report',
        options: Options(
          connectTimeout: const Duration(seconds: 5),
          receiveTimeout: const Duration(seconds: 5),
          sendTimeout: const Duration(seconds: 5),
        ),
      );
      final json = Map<String, dynamic>.from(res.data as Map);
      await _cache.setJson(cacheKey, json, ttl: const Duration(minutes: 5));
      return EventReportFetchResult(
        report: EventReport.fromJson(json),
        fromCache: false,
      );
    } catch (_) {
      final cached = await _cache.getJson(cacheKey);
      if (cached != null) {
        return EventReportFetchResult(
          report: EventReport.fromJson(cached),
          fromCache: true,
        );
      }
      throw const OfflineNoCacheException('event_report');
    }
  }
}
