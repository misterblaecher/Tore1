import 'package:flutter_test/flutter_test.dart';
import 'package:tore/core/perf/scan_suppression.dart';

void main() {
  test('suppresses same hash inside cooldown window', () {
    final suppression = ScanSuppression(cooldown: const Duration(milliseconds: 1200));
    final now = DateTime(2025, 1, 1, 12, 0, 0);

    expect(suppression.shouldSuppress(hash: 'abc', now: now), isFalse);
    expect(suppression.shouldSuppress(hash: 'abc', now: now.add(const Duration(milliseconds: 400))), isTrue);
    expect(suppression.shouldSuppress(hash: 'abc', now: now.add(const Duration(milliseconds: 1300))), isFalse);
  });
}
