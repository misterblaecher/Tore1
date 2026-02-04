import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'api.dart';
import 'core/auth/auth_repository.dart';
import 'core/auth/auth_models.dart';
import 'core/network/providers.dart';

final apiProvider = Provider<Api>((ref) {
  final client = ref.watch(apiClientProvider);
  return Api.fromClient(client);
});

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return AuthRepository(apiClient);
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
