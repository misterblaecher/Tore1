import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

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
    // Prefetch is best effort; owning providers retain their error state for
    // the screen's retry UI. Background failures must not escape to the zone.
    if (modulesOn?['ticker'] == true) {
      unawaited(_prefetch(() => read(tickerControllerProvider(eventId).notifier).refresh()));
    }

    final menuEnabled = modulesOn?['menu'] == true;
    if (menuEnabled) {
      unawaited(_prefetch(() => refresh(marketMenuProvider(eventId).future)));
    }

    unawaited(_prefetch(() => refresh(eventConfigProvider(eventId).future)));
  });
}

Future<void> _prefetch(Future<Object?> Function() load) async {
  try {
    await load();
  } catch (_) {
    // The provider exposes the failure when the user opens its screen.
  }
}
