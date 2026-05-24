import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api.dart';
import '../../../core/network/network_state_provider.dart';
import '../../../features/events/presentation/event_config_providers.dart';
import '../../../features/menu_market/presentation/menu_screen.dart' as v3_menu;
import '../../../features/orders/presentation/order_status_live_screen.dart'
    as v3_orders;
import '../../../shared/models/event_config.dart';
import '../../../state.dart';
import '../../models/rebuild_types.dart';
import '../../ui/widgets/primitives.dart';

class RebuildMenuAdapterScreen extends StatelessWidget {
  const RebuildMenuAdapterScreen({
    super.key,
    required this.network,
    required this.eventId,
    required this.eventState,
  });

  final ConnectivityState network;
  final int eventId;
  final EventState eventState;

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        _EnsureRootProviderScope(
            network: network, child: v3_menu.MenuScreen(eventId: eventId)),
        Positioned(
            top: 0, left: 0, right: 0, child: NetworkBanner(state: network)),
        if (eventState != EventState.live)
          const Positioned.fill(
            child: AbsorbPointer(
              child: ColoredBox(
                color: Color(0x77050506),
                child: Center(
                  child: Card(
                    child: Padding(
                      padding: EdgeInsets.all(16),
                      child: BlockedStateView(
                        title: 'Actions temporairement bloquées',
                        message:
                            'Menu consultable, confirmations désactivées pendant cet état événement.',
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}

class RebuildOrdersAdapterScreen extends StatelessWidget {
  const RebuildOrdersAdapterScreen({
    super.key,
    required this.network,
    required this.orderId,
    required this.eventState,
  });

  final ConnectivityState network;
  final int orderId;
  final EventState eventState;

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        _EnsureRootProviderScope(
            network: network,
            child: v3_orders.OrderStatusLiveScreen(orderId: orderId)),
        Positioned(
            top: 0, left: 0, right: 0, child: NetworkBanner(state: network)),
        if (eventState != EventState.live)
          const Positioned.fill(
            child: AbsorbPointer(
              child: ColoredBox(
                color: Color(0x66050506),
                child: Center(
                  child: Card(
                    child: Padding(
                      padding: EdgeInsets.all(16),
                      child: BlockedStateView(
                        title: 'Ordres en lecture seule',
                        message:
                            'Les transitions de commande sont bloquées pour cet état événement.',
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}

class RebuildBarOrdersAdapterScreen extends StatelessWidget {
  const RebuildBarOrdersAdapterScreen({
    super.key,
    required this.network,
    required this.orderId,
    required this.eventState,
  });

  final ConnectivityState network;
  final int orderId;
  final EventState eventState;

  @override
  Widget build(BuildContext context) {
    return RebuildOrdersAdapterScreen(
      network: network,
      orderId: orderId,
      eventState: eventState,
    );
  }
}

class _EnsureRootProviderScope extends StatelessWidget {
  const _EnsureRootProviderScope({required this.network, required this.child});

  final ConnectivityState network;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final hasScope = _hasRootProviderScope(context);
    if (hasScope) return child;
    return ProviderScope(
      overrides: [
        apiProvider.overrideWithValue(_StandaloneAdapterApi()),
        meProvider.overrideWith(
            (_) async => throw StateError('No root auth session')),
        userIdProvider.overrideWithValue(null),
        isReadOnlyProvider
            .overrideWithValue(network != ConnectivityState.online),
        networkStatusProvider.overrideWithValue(_toNetworkState(network)),
        eventConfigProvider
            .overrideWith((_, eventId) async => EventConfig.fallback(eventId)),
      ],
      child: child,
    );
  }

  bool _hasRootProviderScope(BuildContext context) {
    try {
      ProviderScope.containerOf(context, listen: false);
      return true;
    } on StateError {
      return false;
    }
  }
}

NetworkState _toNetworkState(ConnectivityState state) {
  switch (state) {
    case ConnectivityState.online:
      return NetworkState.online;
    case ConnectivityState.degraded:
      return NetworkState.degraded;
    case ConnectivityState.offline:
      return NetworkState.offline;
  }
}

class _StandaloneAdapterApi extends Api {
  _StandaloneAdapterApi() : super('http://localhost');

  @override
  Future<Map<String, dynamic>> event(int eventId) async => {
        'id': eventId,
        'name': 'Event #$eventId',
        'state': 'LIVE',
      };

  @override
  Future<MenuFetchResult> menuWithCacheStatus(int eventId) async =>
      const MenuFetchResult(items: <Map<String, dynamic>>[], fromCache: true);

  @override
  Future<Map<String, dynamic>> getOrder(int orderId) async => {
        'id': orderId,
        'status': 'NEW',
        'total_cents': 0,
      };
}
