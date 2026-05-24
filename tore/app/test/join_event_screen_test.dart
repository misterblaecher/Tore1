import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tore/api.dart';
import 'package:tore/features/events/presentation/event_public_screen.dart';
import 'package:tore/features/health/presentation/health_providers.dart';
import 'package:tore/features/qr/presentation/join_event_screen.dart';
import 'package:tore/state.dart';

import 'support/test_network_fakes.dart';

class _FakeApi extends Api {
  _FakeApi() : super('http://localhost:8000');

  @override
  Future<Map<String, dynamic>> event(int eventId) async => {
        'id': eventId,
        'name': 'Event #$eventId',
        'charter_enabled': false,
      };
}

void main() {
  test('maps unknown backend reason to UI unknown state', () {
    expect(mapJoinErrorReasonToUiState('invalid_code'), 'invalid');
    expect(mapJoinErrorReasonToUiState('expired'), 'expired');
    expect(mapJoinErrorReasonToUiState('some_new_reason'), 'unknown');
  });

  testWidgets('prefills join code from deep link routing', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          healthRepositoryProvider.overrideWithValue(FakeHealthRepository())
        ],
        child: const MaterialApp(
          home: JoinEventScreen(prefillCode: 'join66'),
        ),
      ),
    );

    await tester.pump(const Duration(milliseconds: 250));
    final fieldFinder = find.byType(TextFormField).first;
    final fieldWidget = tester.widget<TextFormField>(fieldFinder);
    final controller = fieldWidget.controller;
    if (controller != null) {
      expect(controller.text, equals('JOIN66'));
    } else {
      expect(fieldWidget.initialValue, equals('JOIN66'));
    }
  });

  testWidgets('autoJoinPublic redirects to EventPublicScreen', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiProvider.overrideWithValue(_FakeApi()),
          healthRepositoryProvider.overrideWithValue(FakeHealthRepository()),
        ],
        child: const MaterialApp(
          home: JoinEventScreen(prefillEventId: 42, autoJoinPublic: true),
        ),
      ),
    );

    await tester.pump();
    await tester.pump(const Duration(milliseconds: 250));
    expect(find.byType(EventPublicScreen), findsOneWidget);
  });
}
