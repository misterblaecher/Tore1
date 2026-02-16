import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tore/features/qr/presentation/join_event_screen.dart';

void main() {
  testWidgets('prefills join code from deep link routing', (tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          home: JoinEventScreen(prefillCode: 'join66'),
        ),
      ),
    );

    await tester.pumpAndSettle();
    expect(find.text('JOIN66'), findsOneWidget);
  });
}
