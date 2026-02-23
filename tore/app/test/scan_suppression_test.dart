import 'package:flutter_test/flutter_test.dart';
import 'package:tore/core/perf/scan_suppression.dart';

class _FakeClock {
  _FakeClock(this.now);

  DateTime now;

  DateTime call() => now;
}

void main() {
  test('suppresses same hash inside cooldown window using fake clock', () {
    final clock = _FakeClock(DateTime(2025, 1, 1, 12, 0, 0));
    final suppression = ScanSuppression(cooldown: const Duration(milliseconds: 1200), clock: clock.call);

    expect(suppression.shouldSuppress(hash: 'abc'), isFalse);

    clock.now = clock.now.add(const Duration(milliseconds: 400));
    expect(suppression.shouldSuppress(hash: 'abc'), isTrue);

    clock.now = clock.now.add(const Duration(milliseconds: 900));
    expect(suppression.shouldSuppress(hash: 'abc'), isFalse);
  });
}
