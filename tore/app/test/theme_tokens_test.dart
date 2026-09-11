import 'package:flutter_test/flutter_test.dart';
import 'package:tore/theme/tokens.dart';

void main() {
  test('active theme tokens are night-first and authority gold is stable', () {
    expect(ToreSemantic.bg.toARGB32(), 0xFF070607);
    expect(ToreSemantic.accentPrimary.toARGB32(), 0xFFFF2A4D);
    expect(ToreSemantic.accentAuthority.toARGB32(), 0xFFF5C400);
  });
}
