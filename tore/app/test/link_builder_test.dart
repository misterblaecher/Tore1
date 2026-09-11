import 'package:flutter_test/flutter_test.dart';
import 'package:tore/config/app_config.dart';
import 'package:tore/core/routing/app_deep_link_router.dart';
import 'package:tore/core/routing/link_builder.dart';

void main() {
  test('builds links accepted by the canonical deep-link parser', () {
    final builder = AppLinkBuilder.fromConfig(
      AppConfig.resolve(
        flavor: 'prod',
        primaryBaseUrl: 'https://api.tore.test',
      ),
    );
    const router = AppDeepLinkRouter();

    expect(builder.event(42), 'https://tore.app/event/42');
    expect(router.parse(builder.event(42))?.kind, AppDeepLinkKind.event);
    expect(router.parse(builder.event(42))?.id, 42);

    expect(builder.appBar(7), 'tore://bar/7');
    expect(router.parse(builder.appBar(7))?.kind, AppDeepLinkKind.bar);
    expect(router.parse(builder.appBar(7))?.id, 7);

    final qr = builder.qr('JOIN:abc/123');
    expect(router.parse(qr)?.kind, AppDeepLinkKind.qr);
    expect(router.parse(qr)?.payload, 'JOIN:abc/123');
  });

  test('environment fallback keeps convergence hosts explicit', () {
    final dev = AppLinkBuilder.fromConfig(
      AppConfig.resolve(flavor: 'dev', primaryBaseUrl: 'http://localhost:8000'),
    );
    final stage = AppLinkBuilder.fromConfig(
      AppConfig.resolve(
        flavor: 'stage',
        environment: 'stage',
        primaryBaseUrl: 'https://api.stage.tore.test',
      ),
    );

    expect(dev.publicBaseUrl, 'https://dev.tore.app');
    expect(stage.publicBaseUrl, 'https://stage.tore.app');
  });
}
