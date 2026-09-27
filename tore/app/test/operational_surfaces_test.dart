import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tore/core/auth/auth_session_provider.dart';
import 'package:tore/core/network/network_state_provider.dart';
import 'package:tore/features/entry/presentation/entry_mode_screen.dart';
import 'package:tore/features/operations/data/operational_repository.dart';
import 'package:tore/features/operations/domain/operational_models.dart';
import 'package:tore/features/operations/presentation/bar_operational_hub_screen.dart';
import 'package:tore/features/operations/presentation/event_operational_hub_screen.dart';
import 'package:tore/features/operations/presentation/invitation_center_screen.dart';
import 'package:tore/features/operations/presentation/operational_mode_switcher.dart';
import 'package:tore/features/operations/presentation/operational_providers.dart';
import 'package:tore/features/reports/data/event_report_service.dart';
import 'package:tore/features/reports/presentation/report_providers.dart';
import 'package:tore/shared/models/event_report.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  ScopedCapability eventCap(int id, {String role = 'ENTRY'}) =>
      ScopedCapability(
        id: 'event:$id:staff',
        type: 'EVENT',
        scope: 'event:$id',
        eventId: id,
        role: role,
        actions: role == 'MANAGER'
            ? const {
                'event.view_ops',
                'event.manage_entry',
                'event.manage_staff'
              }
            : const {'event.view_ops', 'event.manage_entry'},
        source: 'EVENT_STAFF',
        event: {'id': id, 'name': 'Event $id'},
      );

  ScopedCapability barCap(int id) => ScopedCapability(
        id: 'bar:$id:access',
        type: 'BAR',
        scope: 'bar:$id',
        barId: id,
        role: 'BARTENDER',
        actions: const {'bar.view_ops', 'bar.manage_orders'},
        source: 'PARTNER_ACCESS',
        bar: {'id': id, 'name': 'Bar $id'},
      );

  testWidgets('mode selector only renders authorized operational modes',
      (tester) async {
    await tester.pumpWidget(ProviderScope(
      key: UniqueKey(),
      overrides: [
        operationalCapabilitiesProvider.overrideWith((ref) async =>
            OperationalCapabilities(
                userId: 'u', events: [eventCap(1)], bars: [barCap(2)])),
      ],
      child: const MaterialApp(home: Scaffold(body: OperationalModeSwitcher())),
    ));
    await tester.pumpAndSettle();
    expect(find.text('USER'), findsOneWidget);
    expect(find.text('ORGA'), findsOneWidget);
    expect(find.text('BAR'), findsOneWidget);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
    await tester.pumpWidget(ProviderScope(
      key: UniqueKey(),
      overrides: [
        operationalCapabilitiesProvider.overrideWith(
            (ref) async => const OperationalCapabilities(userId: 'u')),
      ],
      child: const MaterialApp(home: Scaffold(body: OperationalModeSwitcher())),
    ));
    await tester.pumpAndSettle();
    expect(find.text('USER'), findsOneWidget);
    expect(find.text('ORGA'), findsNothing);
    expect(find.text('BAR'), findsNothing);
  });

  testWidgets('multiple events require an explicit context selection',
      (tester) async {
    final caps = OperationalCapabilities(
        userId: 'u', events: [eventCap(1), eventCap(2)]);
    await tester.pumpWidget(ProviderScope(
      overrides: [
        operationalCapabilitiesProvider.overrideWith((ref) async => caps),
      ],
      child: const MaterialApp(home: Scaffold(body: OperationalModeSwitcher())),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.text('ORGA'));
    await tester.pumpAndSettle();
    expect(find.text('Choisir un contexte actif'), findsOneWidget);
    await tester.tap(find.text('Event 2'));
    await tester.pumpAndSettle();
    final context = ProviderScope.containerOf(
        tester.element(find.byType(OperationalModeSwitcher)));
    expect(context.read(operationalSelectionProvider).scopeId, 2);
  });

  testWidgets('multiple bars require an explicit context selection',
      (tester) async {
    final caps =
        OperationalCapabilities(userId: 'u', bars: [barCap(3), barCap(4)]);
    await tester.pumpWidget(ProviderScope(
      overrides: [
        operationalCapabilitiesProvider.overrideWith((ref) async => caps),
      ],
      child: const MaterialApp(home: Scaffold(body: OperationalModeSwitcher())),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.text('BAR'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Bar 4'));
    await tester.pumpAndSettle();
    final context = ProviderScope.containerOf(
        tester.element(find.byType(OperationalModeSwitcher)));
    expect(context.read(operationalSelectionProvider).scopeId, 4);
  });

  testWidgets('ORGA hub opens Entry offline', (tester) async {
    final cap = eventCap(10);
    await tester.pumpWidget(ProviderScope(
      overrides: [
        networkStatusProvider.overrideWithValue(NetworkState.offline),
        eventOperationalHubProvider
            .overrideWith((ref, id) async => OperationalLoadResult({
                  'event': {'id': id, 'name': 'Event 10', 'state': 'LIVE'},
                  'entry_count': 42,
                })),
      ],
      child: MaterialApp(
          home: Scaffold(body: EventOperationalHubScreen(capability: cap))),
    ));
    await tester.pumpAndSettle();
    expect(find.text('État : LIVE'), findsOneWidget);
    expect(find.text('Entrées : 42'), findsOneWidget);
    expect(find.text('Contrôle des entrées · hors ligne'), findsOneWidget);
    expect(tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
        isNotNull);
    await tester.ensureVisible(find.text('Contrôle des entrées · hors ligne'));
    await tester.tap(find.text('Contrôle des entrées · hors ligne'));
    await tester.pumpAndSettle();
    expect(find.byType(EntryModeScreen), findsOneWidget);
    expect(find.text('Bilan soirée'), findsNothing);
  });

  testWidgets('ORGA manager sees cached bilan and opens its detail',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(800, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final cap = eventCap(10, role: 'MANAGER');
    await tester.pumpWidget(ProviderScope(
      overrides: [
        networkStatusProvider.overrideWithValue(NetworkState.offline),
        eventOperationalHubProvider
            .overrideWith((ref, id) async => OperationalLoadResult({
                  'event': {'state': 'LIVE'},
                  'entry_count': 42,
                })),
        eventOperationalStaffProvider.overrideWith((ref, id) async =>
            const OperationalLoadResult({'items': [], 'invitations': []})),
        eventReportProvider
            .overrideWith((ref, id) async => EventReportFetchResult(
                  fromCache: true,
                  report: EventReport.fromJson({
                    'event_id': id,
                    'sales': {'gross_revenue_cents': 12000},
                    'costs': {'total_cost_cents': 3000},
                    'profit': {'gross_profit_cents': 9000},
                  }),
                )),
      ],
      child: MaterialApp(
          home: Scaffold(body: EventOperationalHubScreen(capability: cap))),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Entrées : 42'), findsOneWidget);
    expect(find.text('Recettes estimées'), findsOneWidget);
    expect(find.text('120.00 €'), findsOneWidget);
    expect(find.text('Bilan en cache · lecture seule'), findsOneWidget);
    await tester.ensureVisible(find.text('Ouvrir le bilan soirée'));
    await tester.tap(find.text('Ouvrir le bilan soirée'));
    await tester.pumpAndSettle();
    expect(find.text('Bilan soirée'), findsOneWidget);
    expect(find.text('Mode hors ligne (lecture seule)'), findsOneWidget);
    expect(find.text('Ajouter'), findsOneWidget);
    expect(
        tester
            .widget<ElevatedButton>(
                find.widgetWithText(ElevatedButton, 'Ajouter'))
            .onPressed,
        isNull);
  });

  testWidgets('BAR hub displays scoped live order and allowed transition',
      (tester) async {
    final cap = barCap(20);
    await tester.pumpWidget(ProviderScope(
      overrides: [
        networkStatusProvider.overrideWithValue(NetworkState.online),
        barOperationalHubProvider
            .overrideWith((ref, id) async => OperationalLoadResult({
                  'bar': {'id': id, 'partner_status': 'ACTIVE'}
                })),
        barOperationalOrdersProvider
            .overrideWith((ref, id) async => OperationalLoadResult({
                  'items': [
                    {'id': 7, 'status': 'NEW', 'total_tickets': 2}
                  ]
                })),
      ],
      child: MaterialApp(
          home: Scaffold(body: BarOperationalHubScreen(capability: cap))),
    ));
    await tester.pumpAndSettle();
    expect(find.text('État partenaire : ACTIVE'), findsOneWidget);
    expect(find.text('Commande #7 · NEW'), findsOneWidget);
    expect(find.text('ACCEPT'), findsOneWidget);
    expect(find.byTooltip('Annuler'), findsOneWidget);
  });

  testWidgets('BAR menu shows prices and disables stock changes from cache',
      (tester) async {
    final cap = ScopedCapability(
      id: 'bar:20:manager',
      type: 'BAR',
      scope: 'bar:20',
      barId: 20,
      role: 'MANAGER',
      actions: const {'bar.view_ops', 'bar.manage_menu'},
      source: 'PARTNER_ACCESS',
      bar: const {'name': 'Bar 20'},
    );
    await tester.pumpWidget(ProviderScope(
      overrides: [
        networkStatusProvider.overrideWithValue(NetworkState.offline),
        barOperationalHubProvider
            .overrideWith((ref, id) async => OperationalLoadResult({
                  'bar': {'partner_status': 'ACTIVE'}
                })),
        barOperationalOrdersProvider.overrideWith(
            (ref, id) async => OperationalLoadResult({'items': []})),
        barOperationalMenuProvider
            .overrideWith((ref, id) async => OperationalLoadResult({
                  'items': [
                    {
                      'id': 4,
                      'name': 'Cola',
                      'category': 'Soft',
                      'price_cents': 350,
                      'available': false,
                      'stock_status': 'OUT',
                      'version': 2
                    }
                  ]
                }, isFromCache: true)),
      ],
      child: MaterialApp(
          home: Scaffold(body: BarOperationalHubScreen(capability: cap))),
    ));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Cola'));
    expect(find.textContaining('3.50 €'), findsOneWidget);
    expect(find.text('Menu local · lecture seule'), findsOneWidget);
    expect(
        tester
            .widget<PopupMenuButton<String>>(
                find.byType(PopupMenuButton<String>))
            .enabled,
        isFalse);
  });

  testWidgets('invitation route accepts a prefilled opaque token',
      (tester) async {
    await tester.pumpWidget(ProviderScope(
      overrides: [
        operationalInvitationsProvider.overrideWith((ref) async => const []),
      ],
      child: const MaterialApp(
          home: InvitationCenterScreen(initialToken: 'opaque-token-123')),
    ));
    await tester.pumpAndSettle();
    expect(find.text('opaque-token-123'), findsOneWidget);
    expect(find.text('Accepter'), findsOneWidget);
  });

  test('revocation or expiry refresh closes the selected context', () async {
    final container = ProviderContainer(overrides: [
      authSessionProvider.overrideWith(
          (ref) => AuthSessionNotifier(ref, autoBootstrap: false)),
    ]);
    addTearDown(container.dispose);
    final current = OperationalCapabilities(userId: 'u', events: [eventCap(1)]);
    final controller = container.read(operationalSelectionProvider.notifier);
    expect(
        await controller.selectScoped(
            OperationalMode.orga, eventCap(1), current),
        isTrue);
    expect(container.read(operationalSelectionProvider).mode,
        OperationalMode.orga);
    await controller.revalidate(const OperationalCapabilities(userId: 'u'));
    expect(container.read(operationalSelectionProvider).mode,
        OperationalMode.user);
    // Let the auth bootstrap started by the provider finish before teardown.
    await Future<void>.delayed(const Duration(milliseconds: 50));
  });
}
