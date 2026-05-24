import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/providers.dart';
import '../../../shared/models/event_staff.dart';
import '../data/staff_service.dart';

final staffServiceProvider = Provider<StaffService>((ref) {
  final client = ref.watch(apiClientProvider);
  return StaffService(client.dio);
});

final eventStaffProvider =
    FutureProvider.family<List<EventStaffMember>, int>((ref, eventId) async {
  final service = ref.watch(staffServiceProvider);
  return service.listStaff(eventId: eventId);
});

enum StaffSessionRole { entry, bar, manager }

class StaffSession {
  const StaffSession({
    required this.eventId,
    required this.role,
    this.tokenId,
    this.expiresAt,
  });

  final int eventId;
  final StaffSessionRole role;
  final String? tokenId;
  final DateTime? expiresAt;
}

class StaffSessionNotifier extends StateNotifier<StaffSession?> {
  StaffSessionNotifier() : super(null);

  void establish({
    required int eventId,
    required StaffSessionRole role,
    String? tokenId,
    DateTime? expiresAt,
  }) {
    state = StaffSession(
      eventId: eventId,
      role: role,
      tokenId: tokenId,
      expiresAt: expiresAt,
    );
  }

  void clear() => state = null;
}

final staffSessionProvider =
    StateNotifierProvider<StaffSessionNotifier, StaffSession?>((ref) {
  return StaffSessionNotifier();
});
