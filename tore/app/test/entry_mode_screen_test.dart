import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:tore/features/entry/data/entry_service.dart';
import 'package:tore/features/entry/presentation/entry_mode_screen.dart';

class FakeEntryService extends EntryService {
  FakeEntryService() : super(Dio());

  @override
  Future<Map<String, dynamic>> getEntryStats(int eventId) async {
    return {'total': 0, 'last_hour': 0};
  }

  @override
  Future<List<Map<String, dynamic>>> getEntryLogs({required int eventId, int limit = 20}) async {
    return [];
  }
}

void main() {
  testWidgets('EntryModeScreen shows counters and actions', (tester) async {
    SharedPreferences.setMockInitialValues({});

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          entryServiceProvider.overrideWithValue(FakeEntryService()),
        ],
        child: const MaterialApp(
          home: EntryModeScreen(eventId: 1),
        ),
      ),
    );

    await tester.pumpAndSettle();

    expect(find.text('Total entrées'), findsOneWidget);
    expect(find.text('Scanner'), findsOneWidget);
    expect(find.text('+1 manuel'), findsOneWidget);
    expect(find.text('-1 correction'), findsOneWidget);
  });
}
