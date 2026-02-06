import 'package:dio/dio.dart';

import '../../../shared/cache/cache_store.dart';
import '../../../shared/cache/offline_no_cache_exception.dart';
import '../../../shared/models/created_event.dart';
import '../../../shared/models/event.dart';
import '../../../shared/models/qr_pack.dart';

class EventsRepository {
  final Dio _dio;
  final CacheStore _cache;

  EventsRepository(this._dio, this._cache);

  Future<List<Event>> fetchEvents(int barId) async {
    final res = await _dio.get('/bars/$barId/events');
    final data = (res.data as List).cast<dynamic>();
    return data
        .map((e) => Event.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  Future<CreatedEvent> createEvent({
    required String name,
    required DateTime startsAt,
    required DateTime endsAt,
    int? barId,
    String? city,
  }) async {
    final res = await _dio.post(
      '/events',
      data: {
        'name': name,
        'starts_at': startsAt.toIso8601String(),
        'ends_at': endsAt.toIso8601String(),
        if (barId != null) 'bar_id': barId,
        if (city != null && city.isNotEmpty) 'city': city,
      },
    );
    return CreatedEvent.fromJson(Map<String, dynamic>.from(res.data as Map));
  }

  Future<QrPack> fetchQrPack(int eventId) async {
    final cacheKey = 'qr_pack_$eventId';
    try {
      final res = await _dio.get(
        '/events/$eventId/qr-pack',
        options: Options(
          connectTimeout: const Duration(seconds: 5),
          receiveTimeout: const Duration(seconds: 5),
          sendTimeout: const Duration(seconds: 5),
        ),
      );
      final json = Map<String, dynamic>.from(res.data as Map);
      await _cache.setJson(cacheKey, json, ttl: const Duration(minutes: 10));
      return QrPack.fromJson(json);
    } catch (_) {
      final cached = await _cache.getJson(cacheKey);
      if (cached != null) {
        return QrPack.fromJson(cached);
      }
      throw const OfflineNoCacheException('qr_pack');
    }
  }
}
