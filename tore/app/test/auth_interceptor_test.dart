import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:tore/core/network/auth_interceptor.dart';
import 'package:tore/core/network/token_storage.dart';

class _FakeTokenStorage extends TokenStorage {
  bool cleared = false;

  @override
  Future<void> clearAuthToken() async {
    cleared = true;
  }
}

class _NoopErrorHandler extends ErrorInterceptorHandler {
  @override
  void next(DioException error) {}
}

void main() {
  test('clears token on 401 response error', () async {
    final storage = _FakeTokenStorage();
    final interceptor = AuthInterceptor(storage);

    final requestOptions = RequestOptions(path: '/auth/me');
    final response = Response(requestOptions: requestOptions, statusCode: 401, data: {'detail': 'Invalid token'});
    final error = DioException(requestOptions: requestOptions, response: response);

    interceptor.onError(error, _NoopErrorHandler());
    await Future<void>.delayed(const Duration(milliseconds: 10));

    expect(storage.cleared, isTrue);
  });

  test('does not clear token for skipAuth requests', () async {
    final storage = _FakeTokenStorage();
    final interceptor = AuthInterceptor(storage);

    final requestOptions = RequestOptions(path: '/healthz', extra: {'skipAuth': true});
    final response = Response(requestOptions: requestOptions, statusCode: 401, data: {'detail': 'Invalid token'});
    final error = DioException(requestOptions: requestOptions, response: response);

    interceptor.onError(error, _NoopErrorHandler());
    await Future<void>.delayed(const Duration(milliseconds: 10));

    expect(storage.cleared, isFalse);
  });
}
