import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:tore/core/perf/perf_tracer.dart';
import 'package:tore/features/entry/data/entry_service.dart';
import 'package:tore/features/entry/presentation/entry_mode_screen.dart';
import 'package:tore/features/health/presentation/health_providers.dart';

import 'support/test_network_fakes.dart';

class FakeEntryService extends EntryService {
  FakeEntryService() : super(Dio(), PerfTracer());

  @override
  Future<Map<String, dynamic>> getEntryCount(int eventId) async => {'entryCount': 12};

  @override
  Future<Map<String, dynamic>> getEntryStats(int eventId) async => {'accepted_last_10_min': 3};

  @override
  Future<String> exportCsv(int eventId) async => 'ok';
}

void main() {
  testWidgets('EntryModeScreen shows scanner and manual mode controls', (tester) async {
    SharedPreferences.setMockInitialValues({});

    await tester.binding.setSurfaceSize(const Size(414, 896));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          entryServiceProvider.overrideWithValue(FakeEntryService()),
          healthRepositoryProvider.overrideWithValue(FakeHealthRepository()),
        ],
        child: MediaQuery(
          data: const MediaQueryData(
            size: Size(414, 896),
            devicePixelRatio: 1,
            textScaler: TextScaler.linear(1),
          ),
          child: const MaterialApp(home: EntryModeScreen(eventId: 1)),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));

    expect(find.text('Mode manuel'), findsOneWidget);
    expect(find.text('SCAN'), findsOneWidget);

    await tester.tap(find.text('Mode manuel'));
    await tester.pump();

    expect(find.text('+1'), findsOneWidget);
    expect(find.text('+5'), findsOneWidget);
    expect(find.text('+10'), findsOneWidget);
    expect(find.text('-1'), findsOneWidget);
  });
}
