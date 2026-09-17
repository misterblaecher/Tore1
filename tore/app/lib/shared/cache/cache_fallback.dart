import 'package:dio/dio.dart';

/// Cached reads may bridge an outage, but never override an access decision,
/// a removed resource, a cancelled request, or an invalid API response.
bool canUseCacheAfter(Object error) {
  if (error is! DioException) return false;
  final status = error.response?.statusCode;
  if (status != null) return status >= 500 && status <= 599;
  return error.type == DioExceptionType.connectionError ||
      error.type == DioExceptionType.connectionTimeout ||
      error.type == DioExceptionType.receiveTimeout ||
      error.type == DioExceptionType.sendTimeout;
}
