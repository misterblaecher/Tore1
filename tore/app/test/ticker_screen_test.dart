import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:tore/core/app_context/app_context.dart';
import 'package:tore/core/network/network_state_provider.dart';
import 'package:tore/features/events/presentation/event_config_providers.dart';
import 'package:tore/features/navigation/presentation/ticker_screen.dart';
import 'package:tore/shared/models/event_config.dart';

EventConfig _config({required bool tickerEnabled}) => EventConfig.fromJson({
      'event_id': 42,
      'ticker_enabled': tickerEnabled,
    });

Future<void> _pumpTicker(
  WidgetTester tester,
  Future<EventConfig> Function() config,
) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        networkStatusProvider.overrideWithValue(NetworkState.offline),
        appContextProvider.overrideWith((ref) {
          final controller = AppContextController();
          controller.enterEvent(eventId: 42, eventName: 'Ticker test');
          return controller;
        }),
        eventConfigProvider(42).overrideWith((ref) => config()),
      ],
      child: const MaterialApp(home: TickerScreen()),
    ),
  );
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('TickerScreen shows loading while config is loading',
      (tester) async {
    final completer = Completer<EventConfig>();

    await _pumpTicker(tester, () => completer.future);
    await tester.pump();

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.text('Module indisponible'), findsNothing);
  });

  testWidgets('TickerScreen shows module unavailable when ticker is disabled',
      (tester) async {
    await _pumpTicker(tester, () async => _config(tickerEnabled: false));
    await tester.pumpAndSettle();

    expect(find.text('Module indisponible'), findsOneWidget);
    expect(find.text('Ce module est désactivé pour cet event.'), findsOneWidget);
  });

  testWidgets('TickerScreen renders ticker when ticker is enabled',
      (tester) async {
    await _pumpTicker(tester, () async => _config(tickerEnabled: true));
    await tester.pumpAndSettle();

    expect(find.text('Ticker'), findsOneWidget);
    expect(find.text('Aucune activité.'), findsOneWidget);
    expect(find.text('Module indisponible'), findsNothing);
  });

  testWidgets('TickerScreen shows a clean config error without cache',
      (tester) async {
    await _pumpTicker(
      tester,
      () => Future<EventConfig>.error(StateError('config unavailable')),
    );
    await tester.pumpAndSettle();

    expect(
      find.text('Impossible de charger la configuration du ticker.'),
      findsOneWidget,
    );
    expect(find.text('Réessayer'), findsOneWidget);
    expect(find.text('Module indisponible'), findsNothing);
  });
}
