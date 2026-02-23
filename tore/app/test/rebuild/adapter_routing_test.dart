import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tore/rebuild/models/rebuild_types.dart';
import 'package:tore/rebuild/ui/adapters/v3_adapter_screens.dart';

void main() {
  testWidgets('adapter screens render independently from app boot gating', (tester) async {
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
    expect(find.byType(RebuildMenuAdapterScreen), findsOneWidget);

    await tester.pumpWidget(
      const MaterialApp(
        home: RebuildOrdersAdapterScreen(
          network: ConnectivityState.online,
          orderId: 77,
          eventState: EventState.live,
        ),
      ),
    );
    await tester.pump();
    expect(find.byType(RebuildOrdersAdapterScreen), findsOneWidget);

    await tester.pumpWidget(
      const MaterialApp(
        home: RebuildBarOrdersAdapterScreen(
          network: ConnectivityState.online,
          orderId: 77,
          eventState: EventState.live,
        ),
      ),
    );
    await tester.pump();
    expect(find.byType(RebuildBarOrdersAdapterScreen), findsOneWidget);
  });
}
