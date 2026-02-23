import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tore/rebuild/models/rebuild_types.dart';
import 'package:tore/rebuild/routing/adapter_routes.dart';
import 'package:tore/rebuild/routing/app_routes.dart';
import 'package:tore/rebuild/ui/adapters/v3_adapter_screens.dart';

void main() {
  testWidgets('AppRoutes.menu resolves to V3 adapter screen', (tester) async {
    final routes = buildAdapterRoutes(
      network: ConnectivityState.online,
      eventId: 42,
      orderId: 77,
      eventState: EventState.live,
    );

    await tester.pumpWidget(MaterialApp(routes: routes, initialRoute: AppRoutes.menu));
    await tester.pump();

    expect(find.byType(RebuildMenuAdapterScreen), findsOneWidget);
  });
}
