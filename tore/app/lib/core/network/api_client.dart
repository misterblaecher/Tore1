import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import '../../config/app_config.dart';
import 'api_endpoints.dart';
import 'api_exception.dart';
import 'auth_interceptor.dart';
import 'retry_interceptor.dart';
import 'token_storage.dart';

class ApiClient {
  static ApiClient? _instance;

  final Dio dio;
  final TokenStorage tokenStorage;
  bool hasSuccessfulRequest = false;

  ApiClient._internal(this.dio, this.tokenStorage);

  factory ApiClient.create({String? baseUrl}) {
    if (_instance != null) return _instance!;

    final tokenStorage = TokenStorage();

    final dio = Dio(
      BaseOptions(
        baseUrl: baseUrl ?? ApiEndpoints.baseUrl,
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 20),
        sendTimeout: const Duration(seconds: 20),
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
      ),
    );

    // Order matters: auth header -> retry -> logs -> error mapping.
    dio.interceptors.add(AuthInterceptor(tokenStorage));
    dio.interceptors.add(
      InterceptorsWrapper(
        onError: (e, handler) async {
          final canRetry = e.response?.statusCode == 401 && e.requestOptions.extra['retried401'] != true;
          if (!canRetry) {
            handler.next(e);
            return;
          }

          final refreshed = await _instance?.tryRefreshSession() ?? false;
          if (!refreshed) {
            handler.next(e);
            return;
          }

          final retryReq = e.requestOptions;
          retryReq.extra['retried401'] = true;
          final newAccess = await tokenStorage.readToken();
          if (newAccess != null && newAccess.isNotEmpty) {
            retryReq.headers['Authorization'] = 'Bearer $newAccess';
          }
          final response = await dio.fetch(retryReq);
          handler.resolve(response);
        },
      ),
    );
    dio.interceptors.add(RetryInterceptor(dio: dio, maxRetries: 1));

    dio.interceptors.add(
      InterceptorsWrapper(
        onResponse: (response, handler) {
          final code = response.statusCode ?? 0;
          if (code >= 200 && code < 400) {
            _instance?.hasSuccessfulRequest = true;
          }
          handler.next(response);
        },
      ),
    );

    // Logs only in debug (and can be disabled with --dart-define=HTTP_LOGS=false)
    if (AppConfig.enableHttpLogs) {
      dio.interceptors.add(
        LogInterceptor(
          requestHeader: true,
          requestBody: true,
          responseBody: true,
        ),
      );
    }

    dio.interceptors.add(
      InterceptorsWrapper(
        onError: (DioException e, handler) {
          handler.reject(
            DioException(
              requestOptions: e.requestOptions,
              response: e.response,
              error: ApiException(
                e.message ?? 'Erreur API',
                statusCode: e.response?.statusCode,
                details: e.response?.data,
              ),
            ),
          );
        },
      ),
    );

    _instance = ApiClient._internal(dio, tokenStorage);
    if (kDebugMode) {
      debugPrint('🔥 ApiClient CREATED (singleton)');
    }
    return _instance!;
  }

  Future<bool> tryRefreshSession() async {
    final refreshToken = await tokenStorage.readRefreshToken();
    if (refreshToken == null || refreshToken.isEmpty) return false;

    try {
      final refreshClient = Dio(BaseOptions(baseUrl: dio.options.baseUrl));
      final res = await refreshClient.post(
        ApiEndpoints.authRefresh,
        data: {'refreshToken': refreshToken},
      );
      final data = (res.data as Map).cast<String, dynamic>();
      final access = (data['access_token'] ?? '').toString();
      final refresh = (data['refresh_token'] ?? '').toString();
      if (access.isEmpty || refresh.isEmpty) return false;
      await tokenStorage.writeTokens(accessToken: access, refreshToken: refresh);
      return true;
    } catch (_) {
      await tokenStorage.clear();
      return false;
    }
  }

  /// Appelé au démarrage : garantit qu'un token existe
  Future<void> ensureGuestToken() async {
    final existing = await tokenStorage.readToken();
    if (existing != null && existing.isNotEmpty) {
      if (kDebugMode) debugPrint('🔐 Existing token found');
      return;
    }

    if (kDebugMode) debugPrint('🆕 No token, creating guest token');

    final response = await dio.post(ApiEndpoints.authGuest, data: {});
    final data = response.data as Map<String, dynamic>;

    final token = data['token'] as String?;
    if (token == null || token.isEmpty) {
      throw Exception('No token returned by /auth/guest');
    }

    await tokenStorage.writeToken(token);
    if (kDebugMode) debugPrint('✅ Guest token saved');
  }
}
