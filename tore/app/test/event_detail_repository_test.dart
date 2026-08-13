import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tore/features/events/data/event_detail_repository.dart';
import 'package:tore/shared/cache/cache_store.dart';

class _RecordingAdapter implements HttpClientAdapter {
  RequestOptions? lastRequest;

  @override
  Future<ResponseBody> fetch(RequestOptions options,
      Stream<List<int>>? requestStream, Future<void>? cancelFuture) async {
    lastRequest = options;
    return ResponseBody.fromString(
      '{"event":{"id":12,"name":"Bal"},"modulesOn":{},"eventState":"LIVE"}',
      200,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('join sends a stable idempotency key in the HTTP header', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost'));
    final adapter = _RecordingAdapter();
    dio.httpClientAdapter = adapter;
    final repository = EventDetailRepository(dio, CacheStore());

    await repository.joinEvent(
      eventId: 12,
      idempotencyKey: 'join-intent-12',
    );

    expect(adapter.lastRequest?.path, '/events/12/join_public');
    expect(adapter.lastRequest?.headers['Idempotency-Key'], 'join-intent-12');
  });
}
