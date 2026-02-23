import 'package:flutter/material.dart';

import '../models/rebuild_types.dart';
import '../ui/adapters/v3_adapter_screens.dart';
import 'app_routes.dart';

Map<String, WidgetBuilder> buildAdapterRoutes({
  required ConnectivityState network,
  required int eventId,
  required int orderId,
  required EventState eventState,
}) {
  return {
    AppRoutes.menu: (_) => RebuildMenuAdapterScreen(
          network: network,
          eventId: eventId,
          eventState: eventState,
        ),
    AppRoutes.orders: (_) => RebuildOrdersAdapterScreen(
          network: network,
          orderId: orderId,
          eventState: eventState,
        ),
    AppRoutes.barOrders: (_) => RebuildBarOrdersAdapterScreen(
          network: network,
          orderId: orderId,
          eventState: eventState,
        ),
  };
}
