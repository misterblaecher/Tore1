import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/foundation.dart';
import 'package:dio/dio.dart';
import 'dart:io';
import 'api.dart';
import 'core/auth/auth_repository.dart';
import 'core/auth/auth_models.dart';
import 'core/auth/auth_session_provider.dart';
import 'core/network/api_exception.dart';
import 'core/network/providers.dart';
import 'features/health/presentation/health_providers.dart';
import 'shared/cache/cache_providers.dart';
import 'features/health/data/health_repository.dart';

enum AppBootStatus { ready }

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
      final result = await health.pingWithPolicy();
      final apiClient = ref.read(apiClientProvider);

      if (!result.isOnline) {
        final canForceReadOnly = result.reachability == HealthReachability.offlineConfirmed && !apiClient.hasSuccessfulRequest;
        if (kDebugMode) {
          debugPrint(
            '[boot] health-check failed reachability=${result.reachability.name} attempts=${result.attempts} status=${result.statusCode}',
          );
        }

        if (canForceReadOnly) {
          if (kDebugMode) debugPrint('[boot] offline confirmed -> read-only mode');
          state = const AppBootState(
            bootStatus: BootStatus.bootOfflineReadOnly,
            status: AppBootStatus.ready,
          );
          return;
        }

        state = AppBootState(
          bootStatus: BootStatus.bootOnline,
          status: AppBootStatus.ready,
          errorMessage: 'Connexion… (réessai)',
        );
        return;
      }

      if (kDebugMode) {
        debugPrint(
          '[boot] online / app ready endpoint=${result.endpoint} status=${result.statusCode} latencyMs=${result.latency.inMilliseconds}',
        );
      }
      state = const AppBootState(
        bootStatus: BootStatus.bootOnline,
        status: AppBootStatus.ready,
      );
    } catch (e) {
      if (_isNetworkError(e)) {
        final apiClient = ref.read(apiClientProvider);
        final isSocket = e is DioException && e.error is SocketException;
        if (isSocket && !apiClient.hasSuccessfulRequest) {
          if (kDebugMode) debugPrint('[boot] socket offline confirmed -> read-only mode');
          state = const AppBootState(
            bootStatus: BootStatus.bootOfflineReadOnly,
            status: AppBootStatus.ready,
          );
          return;
        }

        if (kDebugMode) debugPrint('[boot] network issue but unconfirmed offline -> continue normal mode');
        state = AppBootState(
          bootStatus: BootStatus.bootOnline,
          status: AppBootStatus.ready,
          errorMessage: 'Connexion… (réessai)',
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
    if (error is DioException) {
      return error.error is! FormatException;
    }
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

final meProvider = FutureProvider<AppUser>((ref) async {
  final session = ref.watch(authSessionProvider);
  if (session.status == AuthStatus.unauthenticated) {
    throw const ApiException('Connexion requise', statusCode: 401);
  }
  if (session.isGuest) {
    final guestId = await ref.read(authRepositoryProvider).api.tokenStorage.readGuestDeviceId();
    return AppUser(
      id: guestId ?? 'guest',
      displayName: 'Invité',
      avatarUrl: null,
      addressText: null,
      showAddress: false,
      showAvatar: true,
      showIdentityToStaff: false,
      visibility: 'public',
      showIdentityInBar: false,
    );
  }
  final auth = ref.read(authRepositoryProvider);
  return auth.getMe();
});

/// ✅ Juste l'id (string) dérivé de meProvider
final userIdProvider = Provider<String?>((ref) {
  final me = ref.watch(meProvider).maybeWhen(
        data: (u) => u,
        orElse: () => null,
      );
  return me?.id;
});
