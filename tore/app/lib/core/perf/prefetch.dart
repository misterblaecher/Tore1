import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../state.dart';
import '../../features/events/presentation/event_config_providers.dart';
import '../../features/market/market_providers.dart';
import '../../features/ticker/ticker_providers.dart';

class PrefetchGate {
  PrefetchGate({this.cooldown = const Duration(seconds: 30)});

  final Duration cooldown;
  final Map<int, DateTime> _lastRun = <int, DateTime>{};

  bool canRun(int eventId, DateTime now) {
    final last = _lastRun[eventId];
    if (last != null && now.difference(last) < cooldown) return false;
    _lastRun[eventId] = now;
    return true;
  }
}

final prefetchGateProvider = Provider<PrefetchGate>((ref) => PrefetchGate());

void prefetchEventEssentials({
  required T Function<T>(ProviderListenable<T> provider) read,
  required T Function<T>(Refreshable<T> provider) refresh,
  required int eventId,
  Map<String, bool>? modulesOn,
}) {
  final gate = read(prefetchGateProvider);
  if (!gate.canRun(eventId, DateTime.now())) return;

  scheduleMicrotask(() {
    unawaited(read(apiProvider).eventContext(eventId));
    unawaited(read(tickerControllerProvider(eventId).notifier).refresh());

    final menuEnabled = modulesOn?['menu'] == true;
    if (menuEnabled) {
      unawaited(refresh(marketMenuProvider(eventId).future));
    }

    unawaited(refresh(eventConfigProvider(eventId).future));
  });
}
