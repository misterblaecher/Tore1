import 'package:dio/dio.dart';

import '../../../shared/models/event_staff.dart';
import '../../../shared/models/staff_invite.dart';

class StaffService {
  StaffService(this._dio);

  final Dio _dio;

  Future<StaffInvite> createInvite({
    required int eventId,
    String role = 'entry',
    int maxUses = 1,
    int expiresInHours = 24,
  }) async {
    final res = await _dio.post(
      '/events/$eventId/staff/invite',
      data: {
        'role': role,
        'max_uses': maxUses,
        'expires_in_hours': expiresInHours,
      },
    );
    return StaffInvite.fromJson(Map<String, dynamic>.from(res.data as Map));
  }

  Future<StaffAcceptResult> acceptInvite({
    required int eventId,
    required String token,
  }) async {
    final res = await _dio.post(
      '/events/$eventId/staff/accept',
      data: {'token': token},
    );
    return StaffAcceptResult.fromJson(
        Map<String, dynamic>.from(res.data as Map));
  }

  Future<List<EventStaffMember>> listStaff({
    required int eventId,
  }) async {
    final res = await _dio.get('/events/$eventId/staff');
    final list = (res.data as List)
        .map((item) =>
            EventStaffMember.fromJson(Map<String, dynamic>.from(item as Map)))
        .toList();
    return list;
  }

  Future<void> revokeStaff({
    required int eventId,
    required String userId,
  }) async {
    await _dio.patch('/events/$eventId/staff/$userId/revoke');
  }
}
