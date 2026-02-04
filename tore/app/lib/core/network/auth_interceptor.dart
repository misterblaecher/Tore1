import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import '../../config.dart';
import 'token_storage.dart';

class AuthInterceptor extends Interceptor {
  final TokenStorage tokenStorage;

  AuthInterceptor(this.tokenStorage);

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) async {
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
}
