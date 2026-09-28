import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:tore/core/perf/perf_tracer.dart';
import 'package:tore/core/qr/qr_parser.dart';
import 'package:tore/core/qr/qr_validator.dart';
import 'package:tore/features/entry/data/entry_offline_queue.dart';
import 'package:tore/features/entry/data/entry_service.dart';

class FakeEntryService extends EntryService {
  FakeEntryService() : super(Dio(), PerfTracer());

  final calls = <String>[];
  Object? failure;
  Completer<void>? checkinGate;

  @override
  Future<Map<String, dynamic>> checkin({
    required int eventId,
    required String rawQr,
    required String deviceId,
    required String idempotencyKey,
    DateTime? scannedAt,
  }) async {
    calls.add(idempotencyKey);
    await checkinGate?.future;
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

class FakeQrValidator extends QrValidator {
  QrValidationResult result =
      const QrValidationResult(status: QrValidationStatus.ok);
  bool? lastRequireServerVerification;

  @override
  Future<QrValidationResult> validate(
    QrPayload payload, {
    bool tryBackend = true,
    bool requireServerVerification = false,
  }) async {
    lastRequireServerVerification = requireServerVerification;
    return result;
  }
}

EntryOfflineQueue queueFor(FakeEntryService service,
        {FakeQrValidator? validator}) =>
    EntryOfflineQueue(
        store: EntryOfflineQueueStore(),
        service: service,
        parser: QrParser(),
        validator: validator ?? FakeQrValidator());

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
    final queue = queueFor(service);

    await queue.enqueue(item('a'));
    await queue.enqueue(item('a'));
    await queue.enqueue(item('other').copyWith());

    expect((await queue.load()).map((e) => e.id), ['a', 'other']);
  });

  test('replay is FIFO and keeps the same idempotency keys', () async {
    final service = FakeEntryService();
    final queue = queueFor(service);
    await queue.enqueue(item('a'));
    await queue.enqueue(item('b', type: 'MANUAL'));

    final result = await queue.replay();

    expect(service.calls, ['key-a', 'key-b']);
    expect(result.sent, 2);
    expect(await queue.load(), isEmpty);
  });

  test('permanent failure remains visible while later items can replay',
      () async {
    final service = FakeEntryService();
    final queue = queueFor(service);
    await queue.enqueue(item('a'));
    await queue.enqueue(item('b'));

    service.failure = DioException(
        requestOptions: RequestOptions(path: '/entry'),
        response: Response(
            statusCode: 422, requestOptions: RequestOptions(path: '/entry')));
    final failed = await queue.replay();
    expect(failed.failed, 2);
    expect((await queue.load()).every((e) => e.status == 'failed'), isTrue);
  });

  test('transport failure preserves pending item for reconnect', () async {
    final service = FakeEntryService();
    final queue = queueFor(service);
    await queue.enqueue(item('a'));
    service.failure =
        DioException(requestOptions: RequestOptions(path: '/entry'));

    final result = await queue.replay();

    expect(result.pending, 1);
    expect((await queue.load()).single.status, 'pending');
  });

  test('same QR is not queued twice with different idempotency keys', () async {
    final queue = queueFor(FakeEntryService());
    expect(await queue.enqueue(item('a')), isTrue);
    final second = EntryQueueItem(
        id: 'b',
        eventId: 1,
        rawQr: 'qr-a',
        scannedAt: DateTime.now(),
        idempotencyKey: 'key-b');
    expect(await queue.enqueue(second), isFalse);
    expect(await queue.hasQr(1, 'qr-a'), isTrue);
    expect((await queue.load()).length, 1);
  });

  test('pending verification blocks replay until reconnect', () async {
    final validator = FakeQrValidator()
      ..result = const QrValidationResult(status: QrValidationStatus.pending);
    final service = FakeEntryService();
    final queue = queueFor(service, validator: validator);
    await queue.enqueue(item('a'));
    expect((await queue.replay()).pending, 1);
    expect(service.calls, isEmpty);
    expect(validator.lastRequireServerVerification, isTrue);

    validator.result = const QrValidationResult(status: QrValidationStatus.ok);
    expect((await queue.replay()).sent, 1);
    expect(service.calls, ['key-a']);
    expect(await queue.load(), isEmpty);
  });

  test('server rejection stays visible for staff without writing Entry',
      () async {
    final validator = FakeQrValidator()
      ..result = const QrValidationResult(
          status: QrValidationStatus.invalid, reason: 'invalid_qr');
    final service = FakeEntryService();
    final queue = queueFor(service, validator: validator);
    await queue.enqueue(item('a'));
    expect((await queue.replay()).failed, 1);
    expect(service.calls, isEmpty);
    expect((await queue.load()).single.lastError, 'invalid_qr');
  });

  test('persistent QR data is minimal and sent legacy items are removed',
      () async {
    final store = EntryOfflineQueueStore();
    final queue = queueFor(FakeEntryService());
    await queue.enqueue(item('a'));
    final prefs = await SharedPreferences.getInstance();
    final encoded = prefs.getString('entry_offline_queue_v1')!;
    expect(encoded, contains('"rawQr":"qr-a"'));
    expect(encoded, isNot(contains('"note"')));
    expect(encoded, isNot(contains('"reason"')));
    await store.save([item('a').copyWith(status: 'sent')]);
    expect(await store.load(), isEmpty);
    expect(prefs.getString('entry_offline_queue_v1'), '[]');
  });

  test('scan queued during replay is preserved', () async {
    final service = FakeEntryService()..checkinGate = Completer<void>();
    final queue = queueFor(service);
    await queue.enqueue(item('a'));
    final replay = queue.replay();
    while (service.calls.isEmpty) {
      await Future<void>.delayed(const Duration(milliseconds: 1));
    }
    expect(await queue.enqueue(item('b')), isTrue);
    service.checkinGate!.complete();
    expect((await replay).sent, 1);
    expect((await queue.load()).single.id, 'b');
  });

  test('expired failed items and their raw QR are purged', () async {
    final store = EntryOfflineQueueStore();
    await store.save([
      EntryQueueItem(
        id: 'old',
        eventId: 1,
        rawQr: 'sensitive-old-qr',
        scannedAt: DateTime.now().subtract(const Duration(days: 15)),
        idempotencyKey: 'old-key',
        status: 'failed',
      )
    ]);
    expect(await store.load(), isEmpty);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('entry_offline_queue_v1'), '[]');
  });
}
