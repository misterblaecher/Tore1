import 'package:dio/dio.dart';

import '../../../core/network/api_client.dart';
import '../../../shared/cache/cache_store.dart';
import '../domain/operational_models.dart';

class OperationalLoadResult {
  const OperationalLoadResult(this.data,
      {this.isFromCache = false, this.cachedAt});

  final Map<String, dynamic> data;
  final bool isFromCache;
  final DateTime? cachedAt;
}

class OperationalRepository {
  OperationalRepository(this.api, this.cache);

  final ApiClient api;
  final CacheStore cache;

  Future<OperationalCapabilities> getCapabilities() async {
    final response = await api.dio.get('/me/capabilities');
    return OperationalCapabilities.fromJson(
        (response.data as Map).cast<String, dynamic>());
  }

  Future<OperationalLoadResult> eventHub(String userId, int eventId) =>
      _getCached(userId, 'event', eventId, 'hub', '/ops/events/$eventId');

  Future<OperationalLoadResult> eventStaff(String userId, int eventId) =>
      _getCached(
          userId, 'event', eventId, 'staff', '/ops/events/$eventId/staff');

  Future<OperationalLoadResult> barHub(String userId, int barId) =>
      _getCached(userId, 'bar', barId, 'hub', '/ops/bars/$barId');

  Future<OperationalLoadResult> barOrders(String userId, int barId) =>
      _getCached(userId, 'bar', barId, 'orders', '/ops/bars/$barId/orders');

  Future<OperationalLoadResult> barMenu(String userId, int barId) =>
      _getCached(userId, 'bar', barId, 'menu', '/ops/bars/$barId/menu');

  Future<Map<String, dynamic>> updateBarMenuAvailability({
    required int barId,
    required int itemId,
    required bool available,
    required String stockStatus,
    required int expectedVersion,
    required String idempotencyKey,
  }) async {
    final response = await api.dio.put(
      '/ops/bars/$barId/menu/items/$itemId/availability',
      data: {
        'available': available,
        'stock_status': stockStatus,
        'expected_version': expectedVersion,
      },
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return (response.data as Map).cast<String, dynamic>();
  }

  Future<List<Map<String, dynamic>>> myInvitations() async {
    final response = await api.dio.get('/me/event-staff-invitations');
    final data = (response.data as Map).cast<String, dynamic>();
    return (data['items'] as List? ?? const [])
        .whereType<Map>()
        .map((item) => item.cast<String, dynamic>())
        .toList(growable: false);
  }

  Future<Map<String, dynamic>> acceptInvitation(
      String token, String idempotencyKey) async {
    final response = await api.dio.post(
      '/me/event-staff-invitations/accept',
      data: {'token': token.trim()},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return (response.data as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> createInvitation({
    required int eventId,
    required String targetUserId,
    required String role,
    required int expiresInHours,
    required String idempotencyKey,
  }) async {
    final response = await api.dio.post(
      '/ops/events/$eventId/staff-invitations',
      data: {
        'target_user_id': targetUserId.trim(),
        'role': role,
        'expires_in_hours': expiresInHours,
      },
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return (response.data as Map).cast<String, dynamic>();
  }

  Future<void> revokeStaff(
      int eventId, String targetUserId, String reason) async {
    await api.dio.post('/ops/events/$eventId/staff/$targetUserId/revoke',
        data: {'reason': reason});
  }

  Future<void> revokeInvitation(
      int eventId, int invitationId, String reason) async {
    await api.dio.post(
        '/ops/events/$eventId/staff-invitations/$invitationId/revoke',
        data: {'reason': reason});
  }

  Future<Map<String, dynamic>> transitionOrder({
    required int barId,
    required int orderId,
    required String action,
    String? reason,
    required String idempotencyKey,
  }) async {
    final response = await api.dio.post(
      '/ops/bars/$barId/orders/$orderId/transition',
      data: {'action': action, if (reason != null) 'reason': reason},
      options: Options(headers: {'Idempotency-Key': idempotencyKey}),
    );
    return (response.data as Map).cast<String, dynamic>();
  }

  Future<OperationalLoadResult> _getCached(String userId, String type,
      int scopeId, String resource, String path) async {
    final key = cache.operationsKey(userId, type, scopeId, resource);
    try {
      final response = await api.dio.get(path);
      final data = (response.data as Map).cast<String, dynamic>();
      final at = DateTime.now();
      await cache.setJson(
          key, {'data': data, 'cached_at': at.toIso8601String()},
          ttl: const Duration(minutes: 5));
      return OperationalLoadResult(data, cachedAt: at);
    } on DioException catch (error) {
      if (error.response?.statusCode == 401 ||
          error.response?.statusCode == 403) {
        await cache.clearKey(key);
        rethrow;
      }
      final cached = await cache.getJson(key);
      if (cached?['data'] is Map) {
        return OperationalLoadResult(
          (cached!['data'] as Map).cast<String, dynamic>(),
          isFromCache: true,
          cachedAt: DateTime.tryParse(cached['cached_at']?.toString() ?? ''),
        );
      }
      rethrow;
    }
  }
}
