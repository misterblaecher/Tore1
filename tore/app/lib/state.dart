import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'api.dart';
import 'core/auth/auth_repository.dart';
import 'core/auth/auth_models.dart';
import 'core/network/providers.dart';
import 'shared/cache/cache_providers.dart';

enum AppBootStatus { needsWelcome, ready }

class AppBootState {
  final AppBootStatus status;
  const AppBootState(this.status);
}

final apiProvider = Provider<Api>((ref) {
  final client = ref.watch(apiClientProvider);
  final cache = ref.watch(cacheStoreProvider);
  return Api.fromClient(client, cacheStore: cache);
});

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return AuthRepository(apiClient);
});

final appBootProvider = FutureProvider<AppBootState>((ref) async {
  final auth = ref.read(authRepositoryProvider);
  final token = await auth.api.tokenStorage.readToken();
  if (token == null || token.isEmpty) {
    return const AppBootState(AppBootStatus.needsWelcome);
  }
  await auth.ensureGuestSession();
  return const AppBootState(AppBootStatus.ready);
});

/// ✅ Le user "connecté" (guest) récupéré depuis /auth/me
final meProvider = FutureProvider<AppUser>((ref) async {
  final auth = ref.read(authRepositoryProvider);
  // Ça garantit token valide + retourne un user
  return auth.ensureGuestSession();
});

/// ✅ Juste l'id (string) dérivé de meProvider
final userIdProvider = Provider<String?>((ref) {
  final me = ref.watch(meProvider).maybeWhen(
        data: (u) => u,
        orElse: () => null,
      );
  return me?.id;
});
