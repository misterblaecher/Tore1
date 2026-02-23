import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:tore/api.dart';
import 'package:tore/core/auth/auth_models.dart';
import 'package:tore/features/events/presentation/event_config_providers.dart';
import 'package:tore/rebuild/models/rebuild_types.dart';
import 'package:tore/rebuild/ui/adapters/v3_adapter_screens.dart';
import 'package:tore/shared/models/event_config.dart';
import 'package:tore/state.dart';

class _FakeAdapterApi extends Api {
  _FakeAdapterApi() : super('http://localhost:8000');

  @override
  Future<Map<String, dynamic>> event(int eventId) async => {
        'id': eventId,
        'name': 'Event #$eventId',
        'state': 'LIVE',
      };

  @override
  Future<MenuFetchResult> menuWithCacheStatus(int eventId) async => const MenuFetchResult(
        items: [
          {'id': 1, 'name': 'Water', 'ticket_cost': 1}
        ],
        fromCache: false,
      );

  @override
  Future<Map<String, dynamic>> ticketBalance({required int eventId, required String userId}) async => {
        'balance': 5,
      };

  @override
  Future<Map<String, dynamic>> getOrder(int orderId) async => {
        'id': orderId,
        'status': 'READY',
        'total_cents': 1200,
      };
}

void main() {
  testWidgets('adapter screens render independently from app boot gating', (tester) async {
    final user = AppUser(
      id: 'u-1',
      displayName: 'Adapter Test',
      avatarUrl: null,
      addressText: null,
      showAddress: false,
      showAvatar: true,
      showIdentityToStaff: false,
      bio: '',
      visibility: 'public',
      showIdentityInBar: false,
      accountMode: AccountMode.user,
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiProvider.overrideWithValue(_FakeAdapterApi()),
          meProvider.overrideWith((ref) async => user),
          eventConfigProvider(42).overrideWith((ref) async => EventConfig.fallback(42)),
        ],
        child: const MaterialApp(
          home: RebuildMenuAdapterScreen(
            network: ConnectivityState.online,
            eventId: 42,
            eventState: EventState.live,
          ),
        ),
      ),
    );
    await tester.pump();
    expect(find.byType(RebuildMenuAdapterScreen), findsOneWidget);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiProvider.overrideWithValue(_FakeAdapterApi()),
          meProvider.overrideWith((ref) async => user),
          eventConfigProvider(42).overrideWith((ref) async => EventConfig.fallback(42)),
        ],
        child: const MaterialApp(
          home: RebuildOrdersAdapterScreen(
            network: ConnectivityState.online,
            orderId: 77,
            eventState: EventState.live,
          ),
        ),
      ),
    );
    await tester.pump();
    expect(find.byType(RebuildOrdersAdapterScreen), findsOneWidget);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiProvider.overrideWithValue(_FakeAdapterApi()),
          meProvider.overrideWith((ref) async => user),
          eventConfigProvider(42).overrideWith((ref) async => EventConfig.fallback(42)),
        ],
        child: const MaterialApp(
          home: RebuildBarOrdersAdapterScreen(
            network: ConnectivityState.online,
            orderId: 77,
            eventState: EventState.live,
          ),
        ),
      ),
    );
    await tester.pump();
    expect(find.byType(RebuildBarOrdersAdapterScreen), findsOneWidget);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
  });
}
