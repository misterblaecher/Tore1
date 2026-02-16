import 'package:flutter_test/flutter_test.dart';
import 'package:tore/core/auth/email_token.dart';

void main() {
  test('normalizes token by trimming spaces', () {
    expect(EmailToken.normalize('  abc-123  '), 'abc-123');
  });
}
