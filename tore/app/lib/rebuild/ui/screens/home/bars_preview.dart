import 'package:flutter/material.dart';

import '../../theme/tore_theme.dart';

class BarsPreview extends StatelessWidget {
  const BarsPreview({super.key, required this.onBarTap, required this.onOpenMap});

  final VoidCallback onBarTap;
  final ValueChanged<String> onOpenMap;

  @override
  Widget build(BuildContext context) {
    const bars = [
      (
        name: 'L’Embuscade',
        meta: 'Ouvert · 450 m · 2 soirées',
        mapUrl: 'https://maps.app.goo.gl/5tsL5yu1XdKA25js6',
      ),
      (
        name: 'TORÈ Test Bar',
        meta: 'Live · 700 m · 1 event',
        mapUrl: 'https://www.google.com/maps/search/?api=1&query=Li%C3%A8ge%20bar',
      ),
      (
        name: 'Bar B',
        meta: 'Happy hour · 900 m',
        mapUrl: 'https://www.google.com/maps/search/?api=1&query=Li%C3%A8ge%20bar%20B',
      ),
    ];

    return Column(
      children: [
        for (var index = 0; index < bars.length; index++) ...[
          PartnerBarTile(
            name: bars[index].name,
            meta: bars[index].meta,
            onTap: onBarTap,
            onOpenMap: () => onOpenMap(bars[index].mapUrl),
          ),
          if (index != bars.length - 1) const SizedBox(height: ToreTokens.s8),
        ],
      ],
    );
  }
}

class PartnerBarTile extends StatelessWidget {
  const PartnerBarTile({
    super.key,
    required this.name,
    required this.meta,
    required this.onTap,
    required this.onOpenMap,
  });

  final String name;
  final String meta;
  final VoidCallback onTap;
  final VoidCallback onOpenMap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s12),
        child: Row(
          children: [
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: onTap,
              child: Container(
                width: 46,
                height: 46,
                decoration: BoxDecoration(
                  color: ToreTokens.ruby.withValues(alpha: 0.16),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.storefront, color: ToreTokens.yellowCta, size: 22),
              ),
            ),
            const SizedBox(width: ToreTokens.s12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(name, style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: ToreTokens.s4),
                  Text(meta, style: const TextStyle(color: Colors.white54, fontSize: 12)),
                ],
              ),
            ),
            IconButton.filledTonal(
              tooltip: 'Ouvrir dans Google Maps',
              onPressed: onOpenMap,
              icon: const Icon(Icons.map),
            ),
            const SizedBox(width: ToreTokens.s4),
            IconButton(
              tooltip: 'Voir les soirées',
              onPressed: onTap,
              icon: const Icon(Icons.chevron_right),
            ),
          ],
        ),
      ),
    );
  }
}
