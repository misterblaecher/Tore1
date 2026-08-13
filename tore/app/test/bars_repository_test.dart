import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tore/features/bars/data/bars_repository.dart';
import 'package:tore/shared/cache/cache_store.dart';

class _QueueAdapter implements HttpClientAdapter {
  _QueueAdapter(this.responses);
  final List<Object> responses;

  @override
  Future<ResponseBody> fetch(RequestOptions options,
      Stream<List<int>>? requestStream, Future<void>? cancelFuture) async {
    final next = responses.removeAt(0);
    if (next is DioException) throw next;
    return ResponseBody.fromString(jsonEncode(next), 200, headers: {
      Headers.contentTypeHeader: ['application/json']
    });
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('bar detail falls back to the versioned cache', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost'));
    dio.httpClientAdapter = _QueueAdapter([
      {
        'id': 4,
        'name': 'Bar public',
        'city': 'Liège',
        'bannerUrl': 'https://cdn.tore.be/bar.jpg'
      },
      DioException(
        requestOptions: RequestOptions(path: '/bars/4/public'),
        type: DioExceptionType.connectionError,
      ),
    ]);
    final repository = BarsRepository(dio, cacheStore: CacheStore());

    final online = await repository.fetchBar(4);
    final cached = await repository.fetchBar(4);

    expect(online.name, 'Bar public');
    expect(cached.bannerUrl, 'https://cdn.tore.be/bar.jpg');
  });
}
