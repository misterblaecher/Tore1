import 'package:dio/dio.dart';

import '../../api.dart';
import '../../shared/cache/cache_store.dart';
import '../../shared/cache/offline_no_cache_exception.dart';
import 'broadcast_models.dart';

class BroadcastResult {
  const BroadcastResult(
      {required this.items, required this.fromCache, this.lastSyncAt});

  final List<BroadcastItem> items;
  final bool fromCache;
  final DateTime? lastSyncAt;
}

class BroadcastRepository {
  BroadcastRepository(this._api, this._cache);

  final Api _api;
  final CacheStore _cache;

  Future<BroadcastResult> fetch(int eventId, {int limit = 50}) async {
    final key = 'event_broadcasts_$eventId';
    try {
      final json = await _api.broadcasts(eventId, limit: limit);
      final items = ((json['items'] as List<dynamic>? ?? const [])
              .cast<Map<String, dynamic>>())
          .map(BroadcastItem.fromJson)
          .toList();
      await _cache.setJson(
          key,
          {
            'items': (json['items'] as List<dynamic>? ?? const []),
            'last_sync': DateTime.now().toIso8601String(),
          },
          ttl: const Duration(hours: 12));
      return BroadcastResult(
          items: items, fromCache: false, lastSyncAt: DateTime.now());
    } on DioException {
      final cached = await _cache.getJson(key);
      final itemsRaw = (cached?['items'] as List<dynamic>? ?? const []);
      if (itemsRaw.isEmpty) throw const OfflineNoCacheException('broadcasts');
      final lastSyncRaw = cached?['last_sync']?.toString();
      return BroadcastResult(
        items: itemsRaw
            .cast<Map<String, dynamic>>()
            .map(BroadcastItem.fromJson)
            .toList(),
        fromCache: true,
        lastSyncAt: lastSyncRaw == null ? null : DateTime.tryParse(lastSyncRaw),
      );
    }
  }
}
