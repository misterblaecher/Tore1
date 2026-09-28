import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:tore/core/perf/perf_tracer.dart';
import 'package:tore/core/network/network_state_provider.dart';
import 'package:tore/features/entry/data/entry_service.dart';
import 'package:tore/features/entry/data/entry_offline_queue.dart';
import 'package:tore/features/entry/presentation/entry_mode_screen.dart';
import 'package:tore/features/health/presentation/health_providers.dart';

import 'support/test_network_fakes.dart';

class FakeEntryService extends EntryService {
  FakeEntryService() : super(Dio(), PerfTracer());

  @override
  Future<Map<String, dynamic>> getEntryCount(int eventId) async =>
      {'entryCount': 12};

  @override
  Future<Map<String, dynamic>> getEntryStats(int eventId) async =>
      {'accepted_last_10_min': 3};

  @override
  Future<String> exportCsv(int eventId) async => 'ok';
}

class FailingEntryService extends FakeEntryService {
  @override
  Future<Map<String, dynamic>> getEntryCount(int eventId) async {
    throw DioException(requestOptions: RequestOptions(path: '/entry/count'));
  }

  @override
  Future<Map<String, dynamic>> getEntryStats(int eventId) async {
    throw DioException(requestOptions: RequestOptions(path: '/entry/stats'));
  }
}

void main() {
  testWidgets('Entry mode opened offline shows server verification pending',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(ProviderScope(
      overrides: [
        networkStatusProvider.overrideWithValue(NetworkState.offline),
        entryServiceProvider.overrideWithValue(FakeEntryService()),
        healthRepositoryProvider.overrideWithValue(FakeHealthRepository()),
      ],
      child: const MaterialApp(home: EntryModeScreen(eventId: 1)),
    ));
    await tester.pumpAndSettle();
    expect(find.text('SCAN'), findsOneWidget);
    expect(find.text('QR en attente de vérification serveur'), findsOneWidget);
    expect(find.text('Compteurs indisponibles hors ligne'), findsOneWidget);
  });

  testWidgets('failed QR remains visible with a staff retry action',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    await EntryOfflineQueueStore().save([
      EntryQueueItem(
        id: 'failed-1',
        eventId: 1,
        rawQr: 'private-qr',
        scannedAt: DateTime.now(),
        idempotencyKey: 'same-key',
        status: 'failed',
        lastError: 'invalid_qr',
      )
    ]);
    await tester.pumpWidget(ProviderScope(
      overrides: [
        networkStatusProvider.overrideWithValue(NetworkState.offline),
        entryServiceProvider.overrideWithValue(FakeEntryService()),
        healthRepositoryProvider.overrideWithValue(FakeHealthRepository()),
      ],
      child: const MaterialApp(home: EntryModeScreen(eventId: 1)),
    ));
    await tester.pumpAndSettle();
    expect(find.text('invalid_qr'), findsOneWidget);
    expect(find.text('Réessayer'), findsOneWidget);
    expect(find.textContaining('private-qr'), findsNothing);
  });

  testWidgets('EntryModeScreen shows scanner and manual mode controls',
      (tester) async {
    SharedPreferences.setMockInitialValues({});

    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          entryServiceProvider.overrideWithValue(FakeEntryService()),
          healthRepositoryProvider.overrideWithValue(FakeHealthRepository()),
        ],
        child: const MaterialApp(home: EntryModeScreen(eventId: 1)),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Mode manuel'), findsOneWidget);
    expect(find.text('SCAN'), findsOneWidget);

    await tester.tap(find.text('Mode manuel'));
    await tester.pumpAndSettle();

    expect(find.text('+1'), findsOneWidget);
    expect(find.text('+5'), findsOneWidget);
    expect(find.text('+10'), findsOneWidget);
    expect(find.text('-1'), findsOneWidget);
  });

  testWidgets(
      'EntryModeScreen keeps the last counters and reports refresh errors',
      (tester) async {
    SharedPreferences.setMockInitialValues({});

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          entryServiceProvider.overrideWithValue(FailingEntryService()),
          healthRepositoryProvider.overrideWithValue(FakeHealthRepository()),
        ],
        child: const MaterialApp(home: EntryModeScreen(eventId: 1)),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('Compteurs temporairement indisponibles'),
        findsOneWidget);
    expect(find.text('0'), findsOneWidget);
  });
}
