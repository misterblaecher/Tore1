import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../network/providers.dart';
import 'perf_tracer.dart';

class PerfOverlay extends ConsumerWidget {
  const PerfOverlay({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final config = ref.watch(appConfigProvider);
    final enabled = ref.watch(perfOverlayEnabledProvider);
    final isDev = config.environmentName == 'dev';
    if (!isDev || !enabled) return const SizedBox.shrink();

    final tracer = ref.watch(perfTracerProvider);
    final scanner = tracer.summary(PerfMetricKey.scannerFlow);
    final entry = tracer.summary(PerfMetricKey.entryCheckin);
    final order = tracer.summary(PerfMetricKey.orderCreate);

    String line(String name, PerfSummary s) =>
        '$name p50:${s.p50.inMilliseconds}ms p95:${s.p95.inMilliseconds}ms (${s.count})';

    return IgnorePointer(
      child: Align(
        alignment: Alignment.topRight,
        child: SafeArea(
          child: Container(
            margin: const EdgeInsets.only(top: 8, right: 8),
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.black.withValues(alpha: 0.58),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.white24),
            ),
            child: DefaultTextStyle(
              style: const TextStyle(fontSize: 11, color: Colors.white),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(line('Scanner', scanner)),
                  Text(line('Entry', entry)),
                  Text(line('Order', order)),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
