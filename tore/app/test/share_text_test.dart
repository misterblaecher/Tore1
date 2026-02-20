import 'package:flutter_test/flutter_test.dart';
import 'package:tore/shared/utils/share_text.dart';

void main() {
  test('pickShareUrl prefers shortUrl', () {
    expect(
      pickShareUrl(shortUrl: 'https://app.tore.be/s/abc', webUrl: 'https://app.tore.be/open?type=event&id=1'),
      'https://app.tore.be/s/abc',
    );
  });

  test('shareText formats fallback code when present', () {
    final text = shareText(url: 'https://app.tore.be/s/abc', fallbackSuffix: 'A1B2');
    expect(text, contains('https://app.tore.be/s/abc'));
    expect(text, contains('Entrer un code'));
    expect(text, contains('A1B2'));
  });

  test('fallback when shortlink creation fails keeps open url', () {
    final text = shareText(url: pickShareUrl(shortUrl: '', webUrl: 'https://app.tore.be/open?type=event&id=7'));
    expect(text, 'Ouvre TORÈ : https://app.tore.be/open?type=event&id=7');
  });
}
