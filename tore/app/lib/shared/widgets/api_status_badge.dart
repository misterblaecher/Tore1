import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/health_provider.dart';
import '../../theme/tore_colors.dart';

class ApiStatusBadge extends ConsumerWidget {
  const ApiStatusBadge({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final health = ref.watch(apiHealthProvider);

    return health.when(
      loading: () => _chip('API', '…', ToreColors.subtext),
      error: (_, __) => _chip('API', 'KO', ToreColors.rubine),
      data: (ok) => _chip('API', ok ? 'OK' : 'KO', ok ? ToreColors.up : ToreColors.rubine),
    );
  }

  Widget _chip(String left, String right, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.14),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withOpacity(0.35)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            left,
            style: const TextStyle(
              fontFamily: 'monospace',
              color: ToreColors.text,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            right,
            style: const TextStyle(
              fontFamily: 'monospace',
              color: ToreColors.text,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}