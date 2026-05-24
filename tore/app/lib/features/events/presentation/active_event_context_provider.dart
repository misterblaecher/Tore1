import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_context/app_context.dart';
import '../../../core/network/network_state_provider.dart';
import '../../../core/perf/prefetch.dart';
import '../../../state.dart';

class ActiveEventContext {
  const ActiveEventContext({
    required this.eventId,
    required this.eventName,
    required this.eventState,
    required this.modulesOn,
    required this.permissions,
    this.lastUpdatedAt,
  });

  final int eventId;
  final String eventName;
  final String eventState;
  final Map<String, bool> modulesOn;
  final EventPermissions permissions;
  final DateTime? lastUpdatedAt;

  ActiveEventContext copyWith({
    String? eventName,
    String? eventState,
    Map<String, bool>? modulesOn,
    EventPermissions? permissions,
    DateTime? lastUpdatedAt,
  }) {
    return ActiveEventContext(
      eventId: eventId,
      eventName: eventName ?? this.eventName,
      eventState: eventState ?? this.eventState,
      modulesOn: modulesOn ?? this.modulesOn,
      permissions: permissions ?? this.permissions,
      lastUpdatedAt: lastUpdatedAt ?? this.lastUpdatedAt,
    );
  }
}

class EventPermissions {
  const EventPermissions(
      {required this.canCreateBets, required this.canResolveBets});
  final bool canCreateBets;
  final bool canResolveBets;
}

class ActiveEventContextController
    extends StateNotifier<AsyncValue<ActiveEventContext?>> {
  ActiveEventContextController(this.ref) : super(const AsyncData(null)) {
    ref.listen<AppContextState>(appContextProvider, (_, next) {
      _handleAppContext(next);
    });
    _handleAppContext(ref.read(appContextProvider));
  }

  final Ref ref;
  Timer? _pollTimer;
  int? _eventId;

  void _handleAppContext(AppContextState ctx) {
    final nextEventId = ctx.activeEventId;
    if (nextEventId == null) {
      _eventId = null;
      _pollTimer?.cancel();
      state = const AsyncData(null);
      return;
    }

    if (_eventId != nextEventId) {
      _eventId = nextEventId;
      state = AsyncData(
        ActiveEventContext(
          eventId: nextEventId,
          eventName: ctx.activeEventName ?? 'Event #$nextEventId',
          eventState: 'LIVE',
          modulesOn: Map<String, bool>.from(ctx.activeEventModules ?? const {}),
          permissions: const EventPermissions(
              canCreateBets: false, canResolveBets: false),
        ),
      );
      unawaited(refresh(force: true));
    }
    _scheduleNextPoll();
  }

  Future<void> refresh({bool force = false}) async {
    final eventId = _eventId;
    if (eventId == null) {
      state = const AsyncData(null);
      return;
    }

    final network = ref.read(networkStatusProvider);
    if (!force && network == NetworkState.offline) {
      _scheduleNextPoll();
      return;
    }

    try {
      final payload = await ref.read(apiProvider).eventContext(eventId);
      final event =
          Map<String, dynamic>.from((payload['event'] as Map?) ?? const {});
      final modules = Map<String, bool>.from(
        ((payload['modulesOn'] as Map?) ?? const {})
            .map((key, value) => MapEntry(key.toString(), value == true)),
      );
      final permissionsJson = Map<String, dynamic>.from(
          (payload['permissions'] as Map?) ?? const {});
      ref.read(appContextProvider.notifier).setActiveEventModules(modules);
      final current = state.valueOrNull;
      state = AsyncData(
        ActiveEventContext(
          eventId: eventId,
          eventName: (event['name'] ?? current?.eventName ?? 'Event #$eventId')
              .toString(),
          eventState: (payload['eventState'] ??
                  payload['event_state'] ??
                  current?.eventState ??
                  'LIVE')
              .toString()
              .toUpperCase(),
          modulesOn: modules,
          permissions: EventPermissions(
            canCreateBets: permissionsJson['canCreateBets'] == true,
            canResolveBets: permissionsJson['canResolveBets'] == true,
          ),
          lastUpdatedAt: _readDateTime(
              payload['lastUpdatedAt'] ?? payload['lastStateUpdatedAt']),
        ),
      );
      prefetchEventEssentials(
          read: ref.read,
          refresh: ref.refresh,
          eventId: eventId,
          modulesOn: modules);
    } catch (error, stackTrace) {
      final current = state.valueOrNull;
      if (current == null) {
        state = AsyncError(error, stackTrace);
      }
    } finally {
      _scheduleNextPoll();
    }
  }

  Duration _nextInterval() {
    final network = ref.read(networkStatusProvider);
    if (network == NetworkState.offline) return const Duration(seconds: 5);
    if (network == NetworkState.degraded) return const Duration(seconds: 2);
    return const Duration(seconds: 1);
  }

  void _scheduleNextPoll() {
    _pollTimer?.cancel();
    if (_eventId == null) return;
    _pollTimer = Timer(_nextInterval(), () => unawaited(refresh()));
  }

  DateTime? _readDateTime(Object? value) {
    final raw = value?.toString();
    if (raw == null || raw.isEmpty) return null;
    return DateTime.tryParse(raw);
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }
}

final activeEventContextProvider = StateNotifierProvider<
    ActiveEventContextController, AsyncValue<ActiveEventContext?>>((ref) {
  return ActiveEventContextController(ref);
});
