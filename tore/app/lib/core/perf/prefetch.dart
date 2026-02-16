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

void prefetchEventEssentials(Ref ref, int eventId, {Map<String, bool>? modulesOn}) {
  final gate = ref.read(prefetchGateProvider);
  if (!gate.canRun(eventId, DateTime.now())) return;

  scheduleMicrotask(() {
    unawaited(ref.read(apiProvider).eventContext(eventId));
    unawaited(ref.read(tickerControllerProvider(eventId).notifier).refresh());

    final menuEnabled = modulesOn?['menu'] == true;
    if (menuEnabled) {
      unawaited(ref.refresh(marketMenuProvider(eventId).future));
    }

    unawaited(ref.refresh(eventConfigProvider(eventId).future));
  });
}
