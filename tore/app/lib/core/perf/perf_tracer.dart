import 'dart:collection';
import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

enum PerfMetricKey { scannerFlow, entryCheckin, orderCreate }

String hashQr(String raw) => sha1.convert(utf8.encode(raw.trim())).toString();

class PerfSummary {
  const PerfSummary({required this.count, required this.p50, required this.p95});

  final int count;
  final Duration p50;
  final Duration p95;

  static const empty = PerfSummary(count: 0, p50: Duration.zero, p95: Duration.zero);
}

class PerfTracer {
  final Map<PerfMetricKey, ListQueue<int>> _samples = {
    for (final key in PerfMetricKey.values) key: ListQueue<int>(),
  };
  final Map<String, DateTime> _marks = <String, DateTime>{};
  static const int _capacity = 80;

  void mark(String tag) {
    _marks[tag] = DateTime.now();
  }

  Duration? elapsedBetween(String startTag, String endTag) {
    final start = _marks[startTag];
    final end = _marks[endTag];
    if (start == null || end == null) return null;
    return end.difference(start);
  }

  void measure(PerfMetricKey key, Duration duration) {
    final queue = _samples[key]!;
    queue.add(duration.inMilliseconds);
    if (queue.length > _capacity) {
      queue.removeFirst();
    }
  }

  Future<T> timeAsync<T>(PerfMetricKey key, Future<T> Function() fn) async {
    final start = DateTime.now();
    final result = await fn();
    measure(key, DateTime.now().difference(start));
    return result;
  }

  PerfSummary summary(PerfMetricKey key) {
    final queue = _samples[key]!;
    if (queue.isEmpty) return PerfSummary.empty;
    final sorted = queue.toList()..sort();
    int at(double p) {
      final idx = ((sorted.length - 1) * p).round().clamp(0, sorted.length - 1);
      return sorted[idx];
    }

    return PerfSummary(
      count: sorted.length,
      p50: Duration(milliseconds: at(0.5)),
      p95: Duration(milliseconds: at(0.95)),
    );
  }
}

final perfTracerProvider = Provider<PerfTracer>((ref) => PerfTracer());

final perfOverlayEnabledProvider = StateProvider<bool>((ref) => false);
