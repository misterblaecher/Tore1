import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tore/core/config/remote_config.dart';
import 'package:tore/tore_mvp_app.dart';

void main() {
  testWidgets('mandatory minimum version blocks canonical runtime',
      (tester) async {
    final config = RemoteConfigPayload.fromJson(
      {
        'min_supported_version': '9.0.0',
        'min_supported_build': 999,
      },
      environmentName: 'dev',
      source: 'test',
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          remoteConfigProvider.overrideWith((ref) async => config),
        ],
        child: const ToreMvpApp(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Mise à jour requise'), findsOneWidget);
    expect(find.textContaining('Version minimale : 9.0.0'), findsOneWidget);
    expect(find.textContaining('Build minimum : 999'), findsOneWidget);
  });

  test('remote freeze snapshot exposes write lock and operator message', () {
    final config = RemoteConfigPayload.fromJson(
      {
        'disable_writes_global': true,
        'disable_writes_message': 'Maintenance TORÈ',
      },
      environmentName: 'dev',
      source: 'test',
    );
    final container = ProviderContainer(
      overrides: [
        remoteConfigSnapshotProvider.overrideWith((ref) => config),
      ],
    );
    addTearDown(container.dispose);

    expect(container.read(remoteWritesDisabledProvider), isTrue);
    expect(container.read(remoteWriteMessageProvider), 'Maintenance TORÈ');
  });
}
