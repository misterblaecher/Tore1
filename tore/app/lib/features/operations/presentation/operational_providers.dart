import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/auth_session_provider.dart';
import '../../../core/network/providers.dart';
import '../../../shared/cache/cache_providers.dart';
import '../data/operational_repository.dart';
import '../domain/operational_models.dart';

final operationalRepositoryProvider = Provider<OperationalRepository>((ref) {
  return OperationalRepository(
      ref.watch(apiClientProvider), ref.watch(cacheStoreProvider));
});

typedef EventRuntimeStateUpdate = Future<Map<String, dynamic>> Function({
  required int eventId,
  required String state,
  required String reason,
  required String idempotencyKey,
});

final eventRuntimeStateUpdateProvider = Provider<EventRuntimeStateUpdate>((ref) {
  return ({
    required int eventId,
    required String state,
    required String reason,
    required String idempotencyKey,
  }) =>
      ref.read(operationalRepositoryProvider).updateEventRuntimeState(
            eventId: eventId,
            state: state,
            reason: reason,
            idempotencyKey: idempotencyKey,
          );
});

final operationalCapabilitiesProvider =
    FutureProvider<OperationalCapabilities>((ref) async {
  final session = ref.watch(authSessionProvider);
  if (!session.isAuthed || session.user == null) {
    return const OperationalCapabilities(userId: '');
  }
  return ref.watch(operationalRepositoryProvider).getCapabilities();
});

class OperationalSelectionController
    extends StateNotifier<OperationalSelection> {
  OperationalSelectionController(this.ref, this.userId)
      : super(const OperationalSelection.user());

  final Ref ref;
  final String? userId;
  bool _restored = false;

  Future<void> restore(OperationalCapabilities capabilities) async {
    if (_restored || userId == null || userId!.isEmpty) return;
    _restored = true;
    final cached = await ref
        .read(cacheStoreProvider)
        .getJson(ref.read(cacheStoreProvider).operationsContextKey(userId!));
    final modeName = cached?['mode']?.toString();
    final scopeId = (cached?['scope_id'] as num?)?.toInt();
    if (scopeId == null) return;
    final mode = modeName == 'orga'
        ? OperationalMode.orga
        : modeName == 'bar'
            ? OperationalMode.bar
            : OperationalMode.user;
    final candidates = mode == OperationalMode.orga
        ? capabilities.events
        : mode == OperationalMode.bar
            ? capabilities.bars
            : const <ScopedCapability>[];
    final matching = candidates.where((item) =>
        (mode == OperationalMode.orga ? item.eventId : item.barId) == scopeId);
    if (matching.isNotEmpty &&
        OperationalGuard.canEnter(
            mode: mode, scopeId: scopeId, capabilities: capabilities)) {
      state = OperationalSelection.scoped(
          mode: mode, scopeId: scopeId, capability: matching.first);
    }
  }

  Future<void> selectUser() async {
    state = const OperationalSelection.user();
    await _clearStored();
  }

  Future<bool> selectScoped(OperationalMode mode, ScopedCapability cap,
      OperationalCapabilities capabilities) async {
    final scopeId = mode == OperationalMode.orga ? cap.eventId : cap.barId;
    if (scopeId == null ||
        !OperationalGuard.canEnter(
            mode: mode, scopeId: scopeId, capabilities: capabilities)) {
      await selectUser();
      return false;
    }
    state = OperationalSelection.scoped(
        mode: mode, scopeId: scopeId, capability: cap);
    if (userId != null && userId!.isNotEmpty) {
      final cache = ref.read(cacheStoreProvider);
      await cache.setJson(
          cache.operationsContextKey(userId!),
          {
            'mode': mode.name,
            'scope_id': scopeId,
          },
          ttl: const Duration(days: 30));
    }
    return true;
  }

  Future<void> revalidate(OperationalCapabilities capabilities) async {
    final scopeId = state.scopeId;
    if (state.mode == OperationalMode.user || scopeId == null) return;
    if (!OperationalGuard.canEnter(
        mode: state.mode, scopeId: scopeId, capabilities: capabilities)) {
      await selectUser();
      return;
    }
    final candidates = state.mode == OperationalMode.orga
        ? capabilities.events
        : capabilities.bars;
    final cap = candidates.firstWhere((item) =>
        (state.mode == OperationalMode.orga ? item.eventId : item.barId) ==
        scopeId);
    state = OperationalSelection.scoped(
        mode: state.mode, scopeId: scopeId, capability: cap);
  }

  Future<void> _clearStored() async {
    if (userId == null || userId!.isEmpty) return;
    final cache = ref.read(cacheStoreProvider);
    await cache.clearKey(cache.operationsContextKey(userId!));
  }
}

final operationalSelectionProvider =
    StateNotifierProvider<OperationalSelectionController, OperationalSelection>(
        (ref) {
  final userId = ref.watch(authSessionProvider).user?.id;
  return OperationalSelectionController(ref, userId);
});

final operationalInvitationsProvider =
    FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final session = ref.watch(authSessionProvider);
  if (!session.isAuthed) return const [];
  return ref.watch(operationalRepositoryProvider).myInvitations();
});

final eventOperationalHubProvider = FutureProvider.autoDispose
    .family<OperationalLoadResult, int>((ref, eventId) async {
  final userId = ref.watch(authSessionProvider).user?.id;
  if (userId == null) throw StateError('registered_session_required');
  try {
    return await ref
        .watch(operationalRepositoryProvider)
        .eventHub(userId, eventId);
  } on DioException catch (error) {
    await _resetForbidden(ref, error);
    rethrow;
  }
});

final eventOperationalStaffProvider = FutureProvider.autoDispose
    .family<OperationalLoadResult, int>((ref, eventId) async {
  final userId = ref.watch(authSessionProvider).user?.id;
  if (userId == null) throw StateError('registered_session_required');
  try {
    return await ref
        .watch(operationalRepositoryProvider)
        .eventStaff(userId, eventId);
  } on DioException catch (error) {
    await _resetForbidden(ref, error);
    rethrow;
  }
});

final barOperationalHubProvider = FutureProvider.autoDispose
    .family<OperationalLoadResult, int>((ref, barId) async {
  final userId = ref.watch(authSessionProvider).user?.id;
  if (userId == null) throw StateError('registered_session_required');
  try {
    return await ref.watch(operationalRepositoryProvider).barHub(userId, barId);
  } on DioException catch (error) {
    await _resetForbidden(ref, error);
    rethrow;
  }
});

final barOperationalOrdersProvider = FutureProvider.autoDispose
    .family<OperationalLoadResult, int>((ref, barId) async {
  final userId = ref.watch(authSessionProvider).user?.id;
  if (userId == null) throw StateError('registered_session_required');
  try {
    return await ref
        .watch(operationalRepositoryProvider)
        .barOrders(userId, barId);
  } on DioException catch (error) {
    await _resetForbidden(ref, error);
    rethrow;
  }
});

final barOperationalMenuProvider = FutureProvider.autoDispose
    .family<OperationalLoadResult, int>((ref, barId) async {
  final userId = ref.watch(authSessionProvider).user?.id;
  if (userId == null) throw StateError('registered_session_required');
  try {
    return await ref
        .watch(operationalRepositoryProvider)
        .barMenu(userId, barId);
  } on DioException catch (error) {
    await _resetForbidden(ref, error);
    rethrow;
  }
});

Future<void> _resetForbidden(Ref ref, DioException error) async {
  final status = error.response?.statusCode;
  if (status != 401 && status != 403) return;
  await ref.read(operationalSelectionProvider.notifier).selectUser();
  ref.invalidate(operationalCapabilitiesProvider);
}
