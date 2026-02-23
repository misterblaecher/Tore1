import 'dart:async';

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

class _CompletingErrorHandler extends ErrorInterceptorHandler {
  _CompletingErrorHandler() : _completer = Completer<void>();

  final Completer<void> _completer;

  Future<void> get completed => _completer.future;

  @override
  void next(DioException error) {
    if (!_completer.isCompleted) {
      _completer.complete();
    }
  }
}

void main() {
  test('clears token on 401 response error', () async {
    final storage = _FakeTokenStorage();
    final interceptor = AuthInterceptor(storage);

    final requestOptions = RequestOptions(path: '/auth/me');
    final response = Response(requestOptions: requestOptions, statusCode: 401, data: {'detail': 'Invalid token'});
    final error = DioException(requestOptions: requestOptions, response: response);
    final handler = _CompletingErrorHandler();

    interceptor.onError(error, handler);
    await handler.completed;

    expect(storage.cleared, isTrue);
  });

  test('does not clear token for skipAuth requests', () async {
    final storage = _FakeTokenStorage();
    final interceptor = AuthInterceptor(storage);

    final requestOptions = RequestOptions(path: '/healthz', extra: {'skipAuth': true});
    final response = Response(requestOptions: requestOptions, statusCode: 401, data: {'detail': 'Invalid token'});
    final error = DioException(requestOptions: requestOptions, response: response);
    final handler = _CompletingErrorHandler();

    interceptor.onError(error, handler);
    await handler.completed;

    expect(storage.cleared, isFalse);
  });
}
