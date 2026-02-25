import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tore/api.dart';
import 'package:tore/core/auth/auth_models.dart';
import 'package:tore/core/network/network_state_provider.dart';
import 'package:tore/features/events/presentation/event_config_providers.dart';
import 'package:tore/rebuild/models/rebuild_types.dart';
import 'package:tore/rebuild/ui/adapters/v3_adapter_screens.dart';
import 'package:tore/shared/models/event_config.dart';
import 'package:tore/state.dart';

class _FakeApi extends Api {
  _FakeApi() : super('http://localhost');

  @override
  Future<Map<String, dynamic>> event(int eventId) async {
    return {'id': eventId, 'state': 'LIVE'};
  }

  @override
  Future<MenuFetchResult> menuWithCacheStatus(int eventId) async {
    return const MenuFetchResult(items: <Map<String, dynamic>>[], fromCache: true);
  }

  @override
  Future<Map<String, dynamic>> getOrder(int orderId) async {
    return {'id': orderId, 'status': 'NEW', 'total_cents': 0};
  }
}

Widget _wrapWithRootProviderScope(Widget child) {
  return ProviderScope(
    overrides: [
      apiProvider.overrideWithValue(_FakeApi()),
      isReadOnlyProvider.overrideWithValue(false),
      networkStatusProvider.overrideWithValue(NetworkState.online),
      meProvider.overrideWith((ref) async => const AppUser(
            id: 'test-user',
            displayName: 'Test User',
            avatarUrl: null,
            addressText: null,
            showAddress: false,
            showAvatar: true,
            showIdentityToStaff: false,
            visibility: 'public',
            showIdentityInBar: false,
          )),
      userIdProvider.overrideWithValue(null),
      eventConfigProvider.overrideWith((ref, eventId) async => EventConfig.fallback(eventId)),
    ],
    child: MaterialApp(home: child),
  );
}

void main() {
  testWidgets('adapter screen does not add nested ProviderScope when one already exists', (tester) async {
    await tester.pumpWidget(
      _wrapWithRootProviderScope(
        const RebuildMenuAdapterScreen(
          network: ConnectivityState.online,
          eventId: 42,
          eventState: EventState.live,
        ),
      ),
    );
    await tester.pump();

    expect(find.byType(ProviderScope), findsOneWidget);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
  });

  testWidgets('adapter screen creates ProviderScope only when missing', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: RebuildMenuAdapterScreen(
          network: ConnectivityState.online,
          eventId: 42,
          eventState: EventState.live,
        ),
      ),
    );
    await tester.pump();

    expect(find.byType(ProviderScope), findsOneWidget);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
  });

  testWidgets('adapter screens render independently from app boot gating', (tester) async {
    await tester.pumpWidget(
      _wrapWithRootProviderScope(
        const RebuildMenuAdapterScreen(
          network: ConnectivityState.online,
          eventId: 42,
          eventState: EventState.live,
        ),
      ),
    );
    await tester.pump();
    expect(find.byType(RebuildMenuAdapterScreen), findsOneWidget);

    await tester.pumpWidget(
      _wrapWithRootProviderScope(
        const RebuildOrdersAdapterScreen(
          network: ConnectivityState.online,
          orderId: 77,
          eventState: EventState.live,
        ),
      ),
    );
    await tester.pump();
    expect(find.byType(RebuildOrdersAdapterScreen), findsOneWidget);

    await tester.pumpWidget(
      _wrapWithRootProviderScope(
        const RebuildBarOrdersAdapterScreen(
          network: ConnectivityState.online,
          orderId: 77,
          eventState: EventState.live,
        ),
      ),
    );
    await tester.pump();
    expect(find.byType(RebuildBarOrdersAdapterScreen), findsOneWidget);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
  });
}
