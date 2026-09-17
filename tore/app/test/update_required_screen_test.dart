import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tore/features/system/presentation/update_required_screen.dart';

void main() {
  testWidgets('shows mandatory update details without rebuild dependencies',
      (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: UpdateRequiredScreen(
          message: 'Version minimale : 2.0.0. Build minimum : 20.',
          currentVersion: '1.5.0',
          currentBuild: 12,
        ),
      ),
    );

    expect(find.text('Mise à jour requise'), findsOneWidget);
    expect(find.textContaining('Version minimale : 2.0.0'), findsOneWidget);
    expect(find.textContaining('Version actuelle : 1.5.0 (12)'), findsOneWidget);
    expect(find.textContaining('Les accès sont bloqués'), findsOneWidget);
  });
}
