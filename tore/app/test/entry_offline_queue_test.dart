import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:tore/core/perf/perf_tracer.dart';
import 'package:tore/features/entry/data/entry_offline_queue.dart';
import 'package:tore/features/entry/data/entry_service.dart';

class FakeEntryService extends EntryService {
  FakeEntryService() : super(Dio(), PerfTracer());

  final calls = <String>[];
  Object? failure;

  @override
  Future<Map<String, dynamic>> checkin({
    required int eventId,
    required String rawQr,
    required String deviceId,
    required String idempotencyKey,
    DateTime? scannedAt,
  }) async {
    calls.add(idempotencyKey);
    if (failure != null) throw failure!;
    return {'status': 'accepted'};
  }

  @override
  Future<Map<String, dynamic>> manualIncrement({
    required int eventId,
    required int delta,
    required String reason,
    String? note,
    required String idempotencyKey,
  }) async {
    calls.add(idempotencyKey);
    if (failure != null) throw failure!;
    return {'count': delta};
  }
}

EntryQueueItem item(String id, {String type = 'CHECKIN'}) => EntryQueueItem(
      id: id,
      eventId: 1,
      type: type,
      rawQr: type == 'CHECKIN' ? 'qr-$id' : null,
      scannedAt: DateTime.now(),
      idempotencyKey: 'key-$id',
      reason: type == 'MANUAL' ? 'file rush' : null,
    );

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('enqueue persists and de-duplicates by idempotency key', () async {
    final service = FakeEntryService();
    final queue = EntryOfflineQueue(
        store: EntryOfflineQueueStore(), service: service);

    await queue.enqueue(item('a'));
    await queue.enqueue(item('a'));
    await queue.enqueue(item('other').copyWith());

    expect((await queue.load()).map((e) => e.id), ['a', 'other']);
  });

  test('replay is FIFO and keeps the same idempotency keys', () async {
    final service = FakeEntryService();
    final queue = EntryOfflineQueue(
        store: EntryOfflineQueueStore(), service: service);
    await queue.enqueue(item('a'));
    await queue.enqueue(item('b', type: 'MANUAL'));

    final result = await queue.replay();

    expect(service.calls, ['key-a', 'key-b']);
    expect(result.sent, 2);
    expect((await queue.load()).every((e) => e.status == 'sent'), isTrue);
  });

  test('permanent failure remains visible while later items can replay', () async {
    final service = FakeEntryService();
    final queue = EntryOfflineQueue(
        store: EntryOfflineQueueStore(), service: service);
    await queue.enqueue(item('a'));
    await queue.enqueue(item('b'));

    service.failure = DioException(
        requestOptions: RequestOptions(path: '/entry'),
        response: Response(statusCode: 422, requestOptions: RequestOptions(path: '/entry')));
    final failed = await queue.replay();
    expect(failed.failed, 2);
    expect((await queue.load()).every((e) => e.status == 'failed'), isTrue);
  });

  test('transport failure preserves pending item for reconnect', () async {
    final service = FakeEntryService();
    final queue = EntryOfflineQueue(
        store: EntryOfflineQueueStore(), service: service);
    await queue.enqueue(item('a'));
    service.failure = DioException(requestOptions: RequestOptions(path: '/entry'));

    final result = await queue.replay();

    expect(result.pending, 1);
    expect((await queue.load()).single.status, 'pending');
  });
}
