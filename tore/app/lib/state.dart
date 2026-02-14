import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/foundation.dart';
import 'package:dio/dio.dart';
import 'api.dart';
import 'core/auth/auth_repository.dart';
import 'core/auth/auth_models.dart';
import 'core/network/api_exception.dart';
import 'core/network/providers.dart';
import 'features/health/presentation/health_providers.dart';
import 'shared/cache/cache_providers.dart';

enum AppBootStatus { needsWelcome, ready }

enum BootStatus {
  bootLoading,
  bootOnline,
  bootOfflineReadOnly,
  bootErrorRetry,
}

class AppBootState {
  final BootStatus bootStatus;
  final AppBootStatus status;
  final String? errorMessage;

  const AppBootState({
    required this.bootStatus,
    required this.status,
    this.errorMessage,
  });

  bool get isReadOnly => bootStatus == BootStatus.bootOfflineReadOnly;

  factory AppBootState.loading() => const AppBootState(
        bootStatus: BootStatus.bootLoading,
        status: AppBootStatus.ready,
      );
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

class AppBootController extends StateNotifier<AppBootState> {
  AppBootController(this.ref) : super(AppBootState.loading()) {
    bootstrap();
  }

  final Ref ref;

  Future<void> bootstrap() async {
    state = AppBootState.loading();
    try {
      final health = ref.read(healthRepositoryProvider);
      final online = await health.ping();
      if (!online) {
        if (kDebugMode) debugPrint('[boot] offline detected -> read-only mode');
        state = const AppBootState(
          bootStatus: BootStatus.bootOfflineReadOnly,
          status: AppBootStatus.ready,
        );
        return;
      }

      final auth = ref.read(authRepositoryProvider);
      final token = await auth.api.tokenStorage.readToken();
      if (token == null || token.isEmpty) {
        if (kDebugMode) debugPrint('[boot] online / no token -> welcome');
        state = const AppBootState(
          bootStatus: BootStatus.bootOnline,
          status: AppBootStatus.needsWelcome,
        );
        return;
      }

      await auth.ensureGuestSession();
      if (kDebugMode) debugPrint('[boot] online / session ready');
      state = const AppBootState(
        bootStatus: BootStatus.bootOnline,
        status: AppBootStatus.ready,
      );
    } catch (e) {
      if (_isNetworkError(e)) {
        if (kDebugMode) debugPrint('[boot] network issue -> read-only mode');
        state = const AppBootState(
          bootStatus: BootStatus.bootOfflineReadOnly,
          status: AppBootStatus.ready,
        );
        return;
      }
      if (kDebugMode) debugPrint('[boot] non-network boot error: $e');
      state = AppBootState(
        bootStatus: BootStatus.bootErrorRetry,
        status: AppBootStatus.ready,
        errorMessage: e.toString(),
      );
    }
  }

  void continueReadOnly() {
    state = const AppBootState(
      bootStatus: BootStatus.bootOfflineReadOnly,
      status: AppBootStatus.ready,
    );
  }

  bool _isNetworkError(Object error) {
    if (error is DioException) return true;
    if (error is ApiException) return error.statusCode == null || (error.statusCode ?? 0) >= 500;
    return false;
  }
}

final appBootProvider = StateNotifierProvider<AppBootController, AppBootState>((ref) {
  return AppBootController(ref);
});

final isReadOnlyProvider = Provider<bool>((ref) {
  return ref.watch(appBootProvider).isReadOnly;
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
