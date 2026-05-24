import 'package:flutter_test/flutter_test.dart';
import 'package:tore/rebuild/config/app_environment.dart';
import 'package:tore/rebuild/config/link_builder.dart';

void main() {
  test('LinkBuilder uses env-aware https bases', () {
    expect(LinkBuilder(AppEnvironment.dev).event('evt1'),
        'https://dev.tore.app/event/evt1');
    expect(LinkBuilder(AppEnvironment.stage).event('evt1'),
        'https://stage.tore.app/event/evt1');
    expect(LinkBuilder(AppEnvironment.prod).event('evt1'),
        'https://tore.app/event/evt1');
  });

  test('LinkBuilder builds tore:// variants', () {
    final builder = LinkBuilder(AppEnvironment.prod);

    expect(builder.appQr('payload-123'), 'tore://qr/payload-123');
    expect(builder.appBar('bar_9'), 'tore://bar/bar_9');
    expect(builder.appMenu('event', 'evt1'), 'tore://menu/event/evt1');
  });
}
