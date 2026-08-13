import 'package:flutter/material.dart';

import '../../theme/tore_theme.dart';
import '../../widgets/primitives.dart';

class NearbyEventsPreview extends StatelessWidget {
  const NearbyEventsPreview({super.key, required this.onOpenEvent});

  final VoidCallback onOpenEvent;

  @override
  Widget build(BuildContext context) {
    const events = [
      (
        title: 'TD Outremeuse',
        place: 'L’Embuscade',
        distance: '450 m',
        time: 'Ce soir · 22:30',
        status: 'QR join',
      ),
      (
        title: 'Rooftop After',
        place: 'Bar B',
        distance: '900 m',
        time: '23:45',
        status: '128 intéressés',
      ),
    ];

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Text('Soirées près de toi',
                    style: Theme.of(context).textTheme.titleMedium),
                const Spacer(),
                const ToreBadge(label: 'Liège', color: ToreTokens.ruby),
              ],
            ),
            const SizedBox(height: ToreTokens.s8),
            for (final event in events)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.local_activity,
                    color: ToreTokens.yellowCta),
                title: Text(event.title),
                subtitle:
                    Text('${event.place} · ${event.distance} · ${event.time}'),
                trailing: TextButton(
                    onPressed: onOpenEvent, child: Text(event.status)),
              ),
          ],
        ),
      ),
    );
  }
}
