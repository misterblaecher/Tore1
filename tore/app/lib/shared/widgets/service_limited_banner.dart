import 'package:flutter/material.dart';

class ServiceLimitedBanner extends StatelessWidget {
  const ServiceLimitedBanner({super.key, required this.message, this.padding});

  final String message;
  final EdgeInsetsGeometry? padding;

  @override
  Widget build(BuildContext context) {
    final child = Material(
      color: Colors.red.shade100,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
          children: [
            const Icon(Icons.lock_clock_outlined),
            const SizedBox(width: 8),
            Expanded(child: Text('Service limité: $message')),
          ],
        ),
      ),
    );

    if (padding == null) return child;
    return Padding(padding: padding!, child: child);
  }
}
