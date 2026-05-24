import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../../../core/network/api_client.dart';

enum HealthReachability { online, slow, offlineConfirmed, offlineUnconfirmed }

class HealthCheckResult {
  const HealthCheckResult({
    required this.reachability,
    required this.endpoint,
    required this.attempts,
    required this.latency,
    this.statusCode,
    this.error,
  });

  final HealthReachability reachability;
  final String endpoint;
  final int attempts;
  final Duration latency;
  final int? statusCode;
  final Object? error;

  bool get isOnline =>
      reachability == HealthReachability.online ||
      reachability == HealthReachability.slow;
}

class HealthRepository {
  final ApiClient api;

  HealthRepository(this.api);

  Future<bool> ping() async {
    final result = await pingWithPolicy();
    return result.isOnline;
  }

  Future<HealthCheckResult> pingWithPolicy({
    int maxRetries = 2,
    Duration connectTimeout = const Duration(seconds: 30),
    Duration receiveTimeout = const Duration(seconds: 45),
  }) async {
    const backoffs = [
      Duration(milliseconds: 500),
      Duration(milliseconds: 1500)
    ];
    final endpoints = ['/healthz', '/api/healthz'];

    Object? lastError;
    int? lastStatus;

    for (var attempt = 0; attempt <= maxRetries; attempt++) {
      String endpoint = endpoints.first;
      var switchedEndpoint = false;

      while (true) {
        final started = DateTime.now();
        try {
          final response = await api.dio.get(
            endpoint,
            options: Options(
              extra: const {'skipAuth': true, 'skipRetry': true},
              connectTimeout: connectTimeout,
              receiveTimeout: receiveTimeout,
              sendTimeout: connectTimeout,
              validateStatus: (code) => code != null && code < 500,
            ),
          );

          final latency = DateTime.now().difference(started);
          final code = response.statusCode ?? 0;
          if (kDebugMode) {
            debugPrint(
                '[health] attempt=${attempt + 1} endpoint=$endpoint status=$code latencyMs=${latency.inMilliseconds}');
          }

          if (code == 404 && !switchedEndpoint) {
            endpoint = endpoint == '/healthz' ? '/api/healthz' : '/healthz';
            switchedEndpoint = true;
            continue;
          }

          if ((code >= 200 && code < 300) || code == 401 || code == 403) {
            return HealthCheckResult(
              reachability: latency > const Duration(seconds: 3)
                  ? HealthReachability.slow
                  : HealthReachability.online,
              endpoint: endpoint,
              attempts: attempt + 1,
              latency: latency,
              statusCode: code,
            );
          }

          lastStatus = code;
          break;
        } on DioException catch (e) {
          final latency = DateTime.now().difference(started);
          lastError = e;
          if (kDebugMode) {
            debugPrint(
              '[health] attempt=${attempt + 1} endpoint=$endpoint dio=${e.type.name} latencyMs=${latency.inMilliseconds}',
            );
          }

          final isSocketError = e.error is SocketException;
          if (isSocketError) {
            return HealthCheckResult(
              reachability: HealthReachability.offlineConfirmed,
              endpoint: endpoint,
              attempts: attempt + 1,
              latency: latency,
              statusCode: e.response?.statusCode,
              error: e,
            );
          }

          break;
        }
      }

      if (attempt < maxRetries) {
        final backoffIndex = attempt.clamp(0, backoffs.length - 1).toInt();
        await Future.delayed(backoffs[backoffIndex]);
      }
    }

    return HealthCheckResult(
      reachability: HealthReachability.offlineUnconfirmed,
      endpoint: '/healthz',
      attempts: maxRetries + 1,
      latency: Duration.zero,
      statusCode: lastStatus,
      error: lastError,
    );
  }
}
