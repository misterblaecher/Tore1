import 'package:flutter_test/flutter_test.dart';
import 'package:tore/shared/utils/share_intent.dart';

void main() {
  test('ShareIntentBuilder prefers shortUrl', () {
    final builder = ShareIntentBuilder(const ShareIntentInput(
        shortUrl: 'https://s.tore/abc',
        openUrl: 'https://app.tore.be/open?type=event&id=1'));
    expect(builder.primaryShareUrl, 'https://s.tore/abc');
  });

  test('ShareIntentBuilder falls back to openUrl', () {
    final builder = ShareIntentBuilder(const ShareIntentInput(
        openUrl: 'https://app.tore.be/open?type=event&id=1'));
    expect(builder.primaryShareUrl, 'https://app.tore.be/open?type=event&id=1');
  });

  test('copyCodeOrHint returns standard hint when no code', () async {
    final builder = ShareIntentBuilder(const ShareIntentInput(copyValue: null));
    expect(await builder.copyCodeOrHint(), kShareFallbackHintPrivate);
  });
}
