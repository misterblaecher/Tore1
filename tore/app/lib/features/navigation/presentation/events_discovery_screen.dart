import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/auth_models.dart';
import '../../../state.dart';
import '../../events/presentation/create_event_wizard_screen.dart';

class EventsDiscoveryScreen extends ConsumerStatefulWidget {
  const EventsDiscoveryScreen({super.key});

  @override
  ConsumerState<EventsDiscoveryScreen> createState() => _EventsDiscoveryScreenState();
}

class _EventsDiscoveryScreenState extends ConsumerState<EventsDiscoveryScreen> {
  String _filter = 'all';

  @override
  Widget build(BuildContext context) {
    final me = ref.watch(meProvider).valueOrNull;
    final organizer = me?.accountMode == AccountMode.organizer;
    final api = ref.read(apiProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Events'),
        actions: [
          if (organizer)
            IconButton(
              tooltip: 'Créer event',
              onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const CreateEventWizardScreen())),
              icon: const Icon(Icons.add_circle_outline),
            ),
        ],
      ),
      body: FutureBuilder<List<dynamic>>(
        future: api.bars(),
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return const Center(child: Text('Impossible de charger les events.'));
          }

          final bars = (snap.data ?? []).cast<Map<String, dynamic>>();
          final events = <Map<String, dynamic>>[];
          for (final bar in bars) {
            events.add({
              'name': '${bar['name'] ?? 'Event'} — Tonight',
              'when': 'Ce soir',
            });
            events.add({
              'name': '${bar['name'] ?? 'Event'} — Weekly',
              'when': 'Cette semaine',
            });
          }

          final filtered = events.where((event) {
            if (_filter == 'all') return true;
            if (_filter == 'tonight') return event['when'] == 'Ce soir';
            return event['when'] == 'Cette semaine';
          }).toList();

          return Column(
            children: [
              Padding(
                padding: const EdgeInsets.all(12),
                child: SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(value: 'all', label: Text('Tous')),
                    ButtonSegment(value: 'tonight', label: Text('Ce soir')),
                    ButtonSegment(value: 'week', label: Text('Cette semaine')),
                  ],
                  selected: {_filter},
                  onSelectionChanged: (values) => setState(() => _filter = values.first),
                ),
              ),
              Expanded(
                child: ListView.builder(
                  itemCount: filtered.length,
                  itemBuilder: (_, index) {
                    final item = filtered[index];
                    return ListTile(
                      title: Text(item['name']!.toString()),
                      subtitle: Text(item['when']!.toString()),
                      trailing: const Icon(Icons.chevron_right),
                    );
                  },
                ),
              ),
            ],
          );
        },
      ),
      floatingActionButton: organizer
          ? FloatingActionButton.extended(
              onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const CreateEventWizardScreen())),
              icon: const Icon(Icons.add),
              label: const Text('Créer event'),
            )
          : null,
    );
  }
}
