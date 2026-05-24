import 'dart:async';

import 'package:dio/dio.dart';

/// Very small, safe retry interceptor.
///
/// - Retries once on transient network errors (timeouts, connection issues)
/// - Retries once on 5xx / 502-504
class RetryInterceptor extends Interceptor {
  RetryInterceptor({required this.dio, this.maxRetries = 1});

  final Dio dio;
  final int maxRetries;

  @override
  Future<void> onError(
      DioException err, ErrorInterceptorHandler handler) async {
    final req = err.requestOptions;

    if (req.extra['skipRetry'] == true) {
      return handler.next(err);
    }

    final current = (req.extra['retry_count'] as int?) ?? 0;
    if (current >= maxRetries) {
      return handler.next(err);
    }

    final shouldRetry = _shouldRetry(err);
    if (!shouldRetry) {
      return handler.next(err);
    }

    req.extra['retry_count'] = current + 1;

    // Small backoff: 250ms, 500ms...
    final delayMs = 250 * (current + 1);
    await Future<void>.delayed(Duration(milliseconds: delayMs));

    try {
      final response = await dio.fetch(req);
      return handler.resolve(response);
    } catch (e) {
      // If retry also fails, propagate original error
      return handler.next(err);
    }
  }

  bool _shouldRetry(DioException err) {
    // Transient connectivity/timeouts
    if (err.type == DioExceptionType.connectionTimeout ||
        err.type == DioExceptionType.receiveTimeout ||
        err.type == DioExceptionType.sendTimeout ||
        err.type == DioExceptionType.connectionError) {
      return true;
    }

    // Server errors
    final code = err.response?.statusCode;
    if (code != null && code >= 500) {
      return true;
    }

    return false;
  }
}
