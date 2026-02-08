import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/core/network/providers.dart';

class EntryService {
  EntryService(this._dio);

  final Dio _dio;

  Future<Map<String, dynamic>> postEntryScan({
    required int eventId,
    required int delta,
    required String source,
    required String deviceId,
    required String idempotencyKey,
    String? rawQr,
  }) async {
    final res = await _dio.post(
      '/events/$eventId/entry/scans',
      data: {
        'delta': delta,
        'source': source,
        'device_id': deviceId,
        'idempotency_key': idempotencyKey,
        if (rawQr != null && rawQr.isNotEmpty) 'raw_qr': rawQr,
      },
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> getEntryStats(int eventId) async {
    final res = await _dio.get('/events/$eventId/entry/stats');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<List<Map<String, dynamic>>> getEntryLogs({
    required int eventId,
    int limit = 20,
  }) async {
    final res = await _dio.get(
      '/events/$eventId/entry/logs',
      queryParameters: {'limit': limit},
    );
    return (res.data as List<dynamic>)
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
  }
}

final entryServiceProvider = Provider<EntryService>((ref) {
  final client = ref.watch(apiClientProvider);
  return EntryService(client.dio);
});
