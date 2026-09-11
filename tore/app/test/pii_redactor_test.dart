import 'package:flutter_test/flutter_test.dart';
import 'package:tore/core/logging/pii_redactor.dart';

void main() {
  test('scrubs secrets and direct identifiers recursively', () {
    final scrubbed = scrubLogFields({
      'authorization': 'Bearer super-secret-token',
      'email': 'alice@example.com',
      'userId': 'user-123456789',
      'nested': {
        'password': 'secret',
        'message': 'contact alice@example.com or +32 470 12 34 56',
      },
    });

    expect(scrubbed['authorization'], '[redacted]');
    expect(scrubbed['email'], '[redacted]');
    expect(scrubbed['userId'], 'use***789');
    expect((scrubbed['nested'] as Map)['password'], '[redacted]');
    expect((scrubbed['nested'] as Map)['message'],
        contains('[redacted-email]'));
    expect((scrubbed['nested'] as Map)['message'],
        contains('[redacted-phone]'));
  });

  test('scrubs sensitive URL query parameters and JWT-like text', () {
    final url = scrubUrlQueryParams(
        'https://app.tore.be/open?type=event&token=abc123&id=42');
    expect(url, contains('token=%5Bredacted%5D'));
    expect(url, contains('id=42'));

    final text = redactFreeText(
        'Bearer abc.def token eyJabc.def.ghi mail test@tore.be');
    expect(text, isNot(contains('abc.def')));
    expect(text, contains('[redacted-jwt]'));
    expect(text, contains('[redacted-email]'));
  });
}
