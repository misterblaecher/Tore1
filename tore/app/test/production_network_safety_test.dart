import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tore/core/network/retry_interceptor.dart';
import 'package:tore/features/bars/data/bars_repository.dart';
import 'package:tore/features/discovery/data/discovery_repository.dart';
import 'package:tore/features/discovery/domain/discovery_models.dart';
import 'package:tore/features/events/data/event_detail_repository.dart';
import 'package:tore/shared/cache/cache_store.dart';
import 'package:tore/shared/cache/offline_no_cache_exception.dart';

class _Adapter implements HttpClientAdapter {
  int calls = 0;
  int? status;
  Object payload = {};
  final keys = <Object?>[];

  @override
  Future<ResponseBody> fetch(RequestOptions options,
      Stream<List<int>>? requestStream, Future<void>? cancelFuture) async {
    calls++;
    keys.add(options.headers['Idempotency-Key']);
    if (status == null) {
      throw DioException(requestOptions: options, type: DioExceptionType.receiveTimeout);
    }
    return ResponseBody.fromString(jsonEncode(payload), status!, headers: {
      Headers.contentTypeHeader: ['application/json'],
    });
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  for (final method in ['POST', 'PATCH', 'PUT', 'DELETE']) {
    test('$method is not automatically replayed without idempotency', () async {
      final dio = Dio(BaseOptions(baseUrl: 'https://api.tore.test'));
      final adapter = _Adapter();
      dio.httpClientAdapter = adapter;
      dio.interceptors.add(RetryInterceptor(dio: dio));
      await expectLater(dio.request('/write', options: Options(method: method)), throwsA(isA<DioException>()));
      expect(adapter.calls, 1);
    });
  }

  test('a retry preserves the order idempotency key', () async {
    final dio = Dio(BaseOptions(baseUrl: 'https://api.tore.test'));
    final adapter = _Adapter();
    dio.httpClientAdapter = adapter;
    dio.interceptors.add(RetryInterceptor(dio: dio));
    await expectLater(dio.post('/orders', options: Options(headers: {'Idempotency-Key': 'same-order'})), throwsA(isA<DioException>()));
    expect(adapter.calls, 2);
    expect(adapter.keys, ['same-order', 'same-order']);
  });

  test('GET remains retryable on an outage', () async {
    final dio = Dio(BaseOptions(baseUrl: 'https://api.tore.test'));
    final adapter = _Adapter();
    dio.httpClientAdapter = adapter;
    dio.interceptors.add(RetryInterceptor(dio: dio));
    await expectLater(dio.get('/events'), throwsA(isA<DioException>()));
    expect(adapter.calls, 2);
  });

  for (final status in [401, 403, 404, 410]) {
    test('event detail evicts public cache after HTTP $status', () async {
      final dio = Dio(BaseOptions(baseUrl: 'https://api.tore.test'));
      final adapter = _Adapter()..status = 200..payload = {'id': 12, 'name': 'Soirée'};
      dio.httpClientAdapter = adapter;
      final repository = EventDetailRepository(dio, CacheStore());
      await repository.fetchEvent(12);
      adapter.status = status;
      await expectLater(repository.fetchEvent(12), throwsA(isA<DioException>()));
      adapter.status = null;
      await expectLater(repository.fetchEvent(12), throwsA(isA<OfflineNoCacheException>()));
    });
  }

  test('discovery and bars propagate access refusals', () async {
    final dio = Dio(BaseOptions(baseUrl: 'https://api.tore.test'));
    final adapter = _Adapter()..status = 200..payload = [];
    dio.httpClientAdapter = adapter;
    final discovery = DiscoveryRepository(dio, CacheStore());
    final bars = BarsRepository(dio);
    await discovery.fetchEvents(const DiscoveryQuery());
    await bars.fetchBars();
    adapter.status = 403;
    await expectLater(discovery.fetchEvents(const DiscoveryQuery()), throwsA(isA<DioException>()));
    await expectLater(bars.fetchBars(), throwsA(isA<DioException>()));
  });
}
