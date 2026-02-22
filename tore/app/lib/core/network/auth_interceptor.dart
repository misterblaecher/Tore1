import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import '../auth/auth_state_signal.dart';
import '../../config/app_config.dart';
import 'token_storage.dart';

class AuthInterceptor extends Interceptor {
  final TokenStorage tokenStorage;
  bool _clearingInvalidToken = false;

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
    await _handleUnauthorized(response.requestOptions, response.statusCode);
    handler.next(response);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    await _handleUnauthorized(err.requestOptions, err.response?.statusCode);
    handler.next(err);
  }

  Future<void> _handleUnauthorized(RequestOptions requestOptions, int? statusCode) async {
    if (requestOptions.extra['skipAuth'] == true) return;
    if (statusCode != 401 && statusCode != 403) return;
    if (_clearingInvalidToken) return;

    final currentToken = await tokenStorage.readToken();
    if (currentToken == null || currentToken.isEmpty) {
      if (AppConfig.enableAuthLogs) {
        debugPrint('[auth] ignoring $statusCode (no token in storage)');
      }
      return;
    }

    final guestMode = await tokenStorage.readGuestModeEnabled();
    if (guestMode) {
      if (AppConfig.enableAuthLogs) {
        debugPrint('[auth] ignoring $statusCode while guest mode is enabled');
      }
      return;
    }

    _clearingInvalidToken = true;
    try {
      await tokenStorage.clearAuthToken();
      debugPrint('[auth] token invalid -> cleared ($statusCode)');
      AuthStateSignal.instance.notifyUnauthenticated();
    } finally {
      _clearingInvalidToken = false;
    }
  }
}
