import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../state.dart';

final orgaDetailProvider =
    FutureProvider.family<Map<String, dynamic>, int>((ref, orgId) async {
  final api = ref.read(apiProvider);
  return api.getOrga(orgId);
});

final orgaInvitesProvider =
    FutureProvider.family<Map<String, dynamic>, int>((ref, orgId) async {
  final api = ref.read(apiProvider);
  return api.orgaListInvites(orgId: orgId);
});

final orgaMembershipsProvider =
    FutureProvider.family<Map<String, dynamic>, int>((ref, orgId) async {
  final api = ref.read(apiProvider);
  return api.orgaMembers(orgId: orgId);
});
