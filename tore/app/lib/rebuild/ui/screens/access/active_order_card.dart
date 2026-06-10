import 'package:flutter/material.dart';

import '../../../models/backend_models.dart';
import '../../theme/tore_theme.dart';
import '../../widgets/primitives.dart';

class ActiveOrderCard extends StatelessWidget {
  const ActiveOrderCard({
    super.key,
    required this.order,
    required this.zones,
    required this.onTap,
  });

  final OrderDto order;
  final List<ZoneDto> zones;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final enabledZones = zones.where((zone) => zone.enabled).take(2).map((zone) => zone.name).toList();
    final zoneLabel = enabledZones.isEmpty ? 'retirez au bar actif' : enabledZones.join(' · ');
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(8),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(ToreTokens.s16),
          child: Row(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: ToreTokens.rubyDeep,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.receipt_long, color: ToreTokens.yellowCta),
              ),
              const SizedBox(width: ToreTokens.s12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Commande en cours', style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: ToreTokens.s4),
                    Text('N°${order.id} · ${order.status}'),
                    Text(zoneLabel, style: const TextStyle(color: Colors.white54, fontSize: 12)),
                  ],
                ),
              ),
              const ToreBadge(label: 'LIVE'),
            ],
          ),
        ),
      ),
    );
  }
}
