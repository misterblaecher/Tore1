import 'package:flutter/material.dart';

import '../../../models/rebuild_types.dart';
import '../../theme/tore_theme.dart';
import '../../widgets/primitives.dart';

class HeroStatusCard extends StatelessWidget {
  const HeroStatusCard({
    super.key,
    required this.mode,
    required this.eventName,
    required this.barName,
    required this.eventState,
    required this.walletBalance,
    required this.checkInCount,
    required this.orderCount,
    this.syncedAt,
  });

  final ToreMode mode;
  final String eventName;
  final String barName;
  final EventState eventState;
  final double walletBalance;
  final int checkInCount;
  final int orderCount;
  final DateTime? syncedAt;

  @override
  Widget build(BuildContext context) {
    final stateLabel = eventState.name.toUpperCase();
    final syncLabel = syncedAt == null
        ? 'sync locale'
        : 'sync ${syncedAt!.hour.toString().padLeft(2, '0')}:${syncedAt!.minute.toString().padLeft(2, '0')}';

    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF261018), ToreTokens.surface],
        ),
        border: Border.all(color: ToreTokens.border),
      ),
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: ToreTokens.black,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: ToreTokens.ruby),
                  ),
                  child: const Icon(
                    Icons.local_fire_department,
                    color: ToreTokens.yellowCta,
                  ),
                ),
                const SizedBox(width: ToreTokens.s12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(eventName,
                          style: Theme.of(context).textTheme.headlineSmall),
                      const SizedBox(height: ToreTokens.s4),
                      Text(
                        mode == ToreMode.user
                            ? '$barName · pass actif'
                            : '$barName · ${mode.name.toUpperCase()} actif',
                      ),
                    ],
                  ),
                ),
                ToreBadge(
                  label: stateLabel == 'LIVE' ? 'LIVE' : 'BETA',
                  color: eventState.isLive ? ToreTokens.ruby : Colors.orange,
                ),
              ],
            ),
            const SizedBox(height: ToreTokens.s16),
            Row(
              children: [
                Expanded(
                  child: HeroMetric(
                    value: '€${walletBalance.toStringAsFixed(0)}',
                    label: 'wallet',
                  ),
                ),
                const SizedBox(width: ToreTokens.s8),
                Expanded(
                  child: HeroMetric(value: '$checkInCount', label: 'check-ins'),
                ),
                const SizedBox(width: ToreTokens.s8),
                Expanded(
                    child: HeroMetric(value: '$orderCount', label: 'orders')),
              ],
            ),
            const SizedBox(height: ToreTokens.s12),
            Text(
              syncLabel,
              style: const TextStyle(color: Colors.white54, fontSize: 11),
            ),
          ],
        ),
      ),
    );
  }
}

class HeroMetric extends StatelessWidget {
  const HeroMetric({super.key, required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(ToreTokens.s8),
      decoration: BoxDecoration(
        color: ToreTokens.black.withValues(alpha: 0.55),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: ToreTokens.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(value, style: ToreTypography.monoNumber(context, size: 18)),
          Text(
            label,
            style: const TextStyle(color: Colors.white54, fontSize: 11),
          ),
        ],
      ),
    );
  }
}
