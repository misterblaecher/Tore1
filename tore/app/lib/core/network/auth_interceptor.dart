import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import '../../config/app_config.dart';
import 'token_storage.dart';

class AuthInterceptor extends Interceptor {
  final TokenStorage tokenStorage;

  AuthInterceptor(this.tokenStorage);

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) async {
    if (options.extra['skipAuth'] == true) {
      handler.next(options);
      return;
    }

    final token = await tokenStorage.readToken();
    if (token != null && token.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $token';
      if (AppConfig.enableAuthLogs) {
        debugPrint('➡️ AUTH HEADER SET');
      }
    } else {
      if (AppConfig.enableAuthLogs) {
        debugPrint('⚠️ AUTH HEADER MISSING');
      }
    }
    handler.next(options);
  }

  @override
  void onResponse(Response response, ResponseInterceptorHandler handler) async {
    handler.next(response);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    final shouldSkipAuth = err.requestOptions.extra['skipAuth'] == true;
    final isUnauthorized = err.response?.statusCode == 401;
    if (!shouldSkipAuth && isUnauthorized) {
      await tokenStorage.clearAuthToken();
    }
    handler.next(err);
  }
}
