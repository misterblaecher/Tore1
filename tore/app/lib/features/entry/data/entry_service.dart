import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/core/network/providers.dart';
import 'package:tore/core/perf/perf_tracer.dart';

class EntryService {
  EntryService(this._dio, this._tracer);

  final Dio _dio;
  final PerfTracer _tracer;

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

  Future<Map<String, dynamic>> checkin({
    required int eventId,
    required String rawQr,
    required String deviceId,
    required String idempotencyKey,
    DateTime? scannedAt,
  }) async {
    return _tracer.timeAsync(PerfMetricKey.entryCheckin, () async {
      final res = await _dio.post(
        '/events/$eventId/entry/checkin',
        data: {
          'ticket_qr_raw': rawQr,
          'scanned_at': (scannedAt ?? DateTime.now()).toIso8601String(),
          'device_id': deviceId,
        },
        options: Options(headers: {'Idempotency-Key': idempotencyKey}),
      );
      return Map<String, dynamic>.from(res.data as Map);
    });
  }

  Future<Map<String, dynamic>> getEntryCount(int eventId) async {
    final res = await _dio.get('/events/$eventId/entry/count');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<Map<String, dynamic>> manualIncrement({
    required int eventId,
    required int delta,
    required String reason,
    String? note,
    required String idempotencyKey,
  }) async {
    final res = await _dio.post(
      '/events/$eventId/entry/manual_increment',
      data: {
        'delta': delta,
        'reason': reason,
        if (note != null && note.trim().isNotEmpty) 'note': note.trim(),
      },
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<String> exportCsv(int eventId) async {
    final res = await _dio.get<String>(
      '/events/$eventId/entry/export.csv',
      options: Options(responseType: ResponseType.plain),
    );
    return res.data ?? '';
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
    return items.map((item) => Map<String, dynamic>.from(item as Map)).toList();
  }
}

final entryServiceProvider = Provider<EntryService>((ref) {
  final client = ref.watch(apiClientProvider);
  return EntryService(client.dio, ref.watch(perfTracerProvider));
});
