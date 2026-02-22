import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tore/core/auth/auth_repository.dart';
import 'package:tore/core/network/api_client.dart';

void main() {
  test('requestEmailOtp maps 429 payload to EmailRateLimitException', () async {
    final client = ApiClient.create(baseUrl: 'https://example.test');
    client.dio.interceptors.insert(
      0,
      InterceptorsWrapper(
        onRequest: (options, handler) {
          handler.reject(
            DioException(
              requestOptions: options,
              response: Response(
                requestOptions: options,
                statusCode: 429,
                headers: Headers.fromMap({'retry-after': ['21']}),
                data: {
                  'detail': 'Too many requests',
                  'retry_after_seconds': 21,
                  'scope': 'auth_email_request_otp_email',
                },
              ),
            ),
          );
        },
      ),
    );

    final repository = AuthRepository(client);

    try {
      await repository.requestEmailOtp('user@example.com');
      fail('Expected EmailRateLimitException');
    } on EmailRateLimitException catch (e) {
      expect(e.retryAfterSeconds, 21);
    }
  });
}
