import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/auth_session_provider.dart';
import '../../../core/network/providers.dart';
import '../../../shared/cache/cache_providers.dart';
import '../data/profile_repository.dart';
import '../domain/profile_models.dart';

final profileRepositoryProvider = Provider<ProfileRepository>((ref) {
  return ProfileRepository(
    ref.watch(apiClientProvider),
    ref.watch(cacheStoreProvider),
  );
});

final ownerProfileProvider = FutureProvider<ProfileLoadResult>((ref) async {
  final session = ref.watch(authSessionProvider);
  final userId = session.user?.id;
  if (!session.isAuthed || userId == null || userId.isEmpty) {
    throw StateError('registered_session_required');
  }
  return ref.watch(profileRepositoryProvider).getOwnerProfile(userId);
});

final affiliationsProvider = FutureProvider<List<Affiliation>>((ref) async {
  final session = ref.watch(authSessionProvider);
  final userId = session.user?.id;
  if (!session.isAuthed || userId == null || userId.isEmpty) return const [];
  return ref.watch(profileRepositoryProvider).getAffiliations(userId);
});

final effectiveCapabilitiesProvider =
    FutureProvider<EffectiveCapabilities>((ref) async {
  final session = ref.watch(authSessionProvider);
  final userId = session.user?.id;
  if (!session.isAuthed || userId == null || userId.isEmpty) {
    return const EffectiveCapabilities();
  }
  return ref.watch(profileRepositoryProvider).getCapabilities(userId);
});
