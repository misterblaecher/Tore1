import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tore/features/discovery/data/discovery_repository.dart';
import 'package:tore/features/discovery/domain/discovery_models.dart';
import 'package:tore/shared/cache/cache_store.dart';

class _QueueAdapter implements HttpClientAdapter {
  _QueueAdapter(this.responses);

  final List<Object> responses;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final response = responses.removeAt(0);
    if (response is DioException) throw response;
    return ResponseBody.fromString(
      response as String,
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

  test('discovery returns a dated cache after a network failure', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost'));
    dio.httpClientAdapter = _QueueAdapter([
      '[{"id":7,"name":"Bal réel","starts_at":"2030-05-10T20:00:00Z","ends_at":"2030-05-11T01:00:00Z","status":"UPCOMING","eventState":"LIVE","entry_price_cents":0}]',
      DioException(
        requestOptions: RequestOptions(path: '/events'),
        type: DioExceptionType.connectionError,
      ),
    ]);
    final repository = DiscoveryRepository(dio, CacheStore());

    final online = await repository.fetchEvents(const DiscoveryQuery());
    final cached = await repository.fetchEvents(const DiscoveryQuery());

    expect(online.fromCache, isFalse);
    expect(cached.fromCache, isTrue);
    expect(cached.events.single.name, 'Bal réel');
    expect(cached.lastSyncAt.millisecondsSinceEpoch, greaterThan(0));
  });
}
