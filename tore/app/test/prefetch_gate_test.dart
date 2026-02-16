import 'package:flutter_test/flutter_test.dart';
import 'package:tore/core/perf/prefetch.dart';

void main() {
  test('blocks repeated prefetch for 30s window', () {
    final gate = PrefetchGate(cooldown: const Duration(seconds: 30));
    final t0 = DateTime(2025, 1, 1, 10, 0, 0);

    expect(gate.canRun(42, t0), isTrue);
    expect(gate.canRun(42, t0.add(const Duration(seconds: 10))), isFalse);
    expect(gate.canRun(42, t0.add(const Duration(seconds: 31))), isTrue);
  });
}
