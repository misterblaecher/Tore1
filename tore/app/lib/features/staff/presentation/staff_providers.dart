import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/providers.dart';
import '../../../shared/models/event_staff.dart';
import '../data/staff_service.dart';

final staffServiceProvider = Provider<StaffService>((ref) {
  final client = ref.watch(apiClientProvider);
  return StaffService(client.dio);
});

final eventStaffProvider = FutureProvider.family<List<EventStaffMember>, int>((ref, eventId) async {
  final service = ref.watch(staffServiceProvider);
  return service.listStaff(eventId: eventId);
});
