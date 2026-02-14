import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/core/network/providers.dart';

class EntryService {
  EntryService(this._dio);

  final Dio _dio;

  Future<Map<String, dynamic>> scanEntry({
    required int eventId,
    required String token,
    required String scanId,
  }) async {
    final res = await _dio.post(
      '/entry/scan',
      data: {
        'event_id': eventId,
        'token': token,
        'scan_id': scanId,
      },
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> getEntryStats(int eventId) async {
    final res = await _dio.get('/entry/stats', queryParameters: {'event_id': eventId});
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<List<Map<String, dynamic>>> getEntryLogs({
    required int eventId,
    int limit = 20,
  }) async {
    final res = await _dio.get(
      '/entry/logs',
      queryParameters: {'event_id': eventId, 'limit': limit},
    );
    final payload = Map<String, dynamic>.from(res.data as Map);
    final items = (payload['items'] as List<dynamic>? ?? const []);
    return items
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
  }
}

final entryServiceProvider = Provider<EntryService>((ref) {
  final client = ref.watch(apiClientProvider);
  return EntryService(client.dio);
});
