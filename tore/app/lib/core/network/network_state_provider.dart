import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/health/data/health_repository.dart';
import '../../features/health/presentation/health_providers.dart';

enum NetworkState { online, degraded, offline }

class NetworkSnapshot {
  const NetworkSnapshot({
    required this.state,
    this.lastSuccessAt,
    this.lastErrorAt,
    this.reason,
    this.consecutiveFailures = 0,
  });

  final NetworkState state;
  final DateTime? lastSuccessAt;
  final DateTime? lastErrorAt;
  final String? reason;
  final int consecutiveFailures;

  NetworkSnapshot copyWith({
    NetworkState? state,
    DateTime? lastSuccessAt,
    DateTime? lastErrorAt,
    String? reason,
    int? consecutiveFailures,
  }) {
    return NetworkSnapshot(
      state: state ?? this.state,
      lastSuccessAt: lastSuccessAt ?? this.lastSuccessAt,
      lastErrorAt: lastErrorAt ?? this.lastErrorAt,
      reason: reason ?? this.reason,
      consecutiveFailures: consecutiveFailures ?? this.consecutiveFailures,
    );
  }
}

class NetworkStateController extends StateNotifier<NetworkSnapshot> {
  NetworkStateController(this.ref)
      : super(const NetworkSnapshot(state: NetworkState.online)) {
    unawaited(refresh());
    _pollTimer = Timer.periodic(
        const Duration(seconds: 60), (_) => unawaited(refresh()));
  }

  final Ref ref;
  Timer? _pollTimer;

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> refresh() async {
    final started = DateTime.now();
    try {
      final result = await ref.read(healthRepositoryProvider).pingWithPolicy(
          maxRetries: 1, receiveTimeout: const Duration(seconds: 30));
      final latency = DateTime.now().difference(started);
      if (result.reachability == HealthReachability.offlineConfirmed) {
        _registerFailure('socket_offline');
        return;
      }
      if (!result.isOnline) {
        _registerFailure('health_unconfirmed');
        return;
      }
      if (result.reachability == HealthReachability.slow ||
          latency > const Duration(seconds: 3)) {
        state = state.copyWith(
          state: NetworkState.degraded,
          lastSuccessAt: DateTime.now(),
          reason: result.reachability == HealthReachability.slow
              ? 'api_slow'
              : 'high_latency',
          consecutiveFailures: 0,
        );
        return;
      }
      state = state.copyWith(
        state: NetworkState.online,
        lastSuccessAt: DateTime.now(),
        reason: null,
        consecutiveFailures: 0,
      );
    } catch (_) {
      if (kDebugMode) {
        debugPrint('[network] health refresh failed');
      }
      _registerFailure('health_error');
    }
  }

  void _registerFailure(String reason) {
    final now = DateTime.now();
    final failures = state.consecutiveFailures + 1;
    final recentWindow = state.lastErrorAt != null &&
        now.difference(state.lastErrorAt!).inSeconds <= 30;

    final nextState = failures >= 5
        ? NetworkState.offline
        : (failures >= 2 && recentWindow)
            ? NetworkState.degraded
            : state.state;

    state = state.copyWith(
      state: nextState,
      lastErrorAt: now,
      reason: reason,
      consecutiveFailures: failures,
    );
  }
}

final networkStateProvider =
    StateNotifierProvider<NetworkStateController, NetworkSnapshot>((ref) {
  return NetworkStateController(ref);
});

final networkStatusProvider = Provider<NetworkState>((ref) {
  return ref.watch(networkStateProvider).state;
});
