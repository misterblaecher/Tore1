import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/auth_models.dart';
import '../../../core/auth/providers.dart';
import '../../../state.dart';
import '../../../ui/app_design_system.dart';
import '../../../shared/widgets/ui_fallbacks.dart';
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
    final session = ref.watch(authSessionProvider);
    final organizer = me?.accountMode == AccountMode.organizer;
    final api = ref.read(apiProvider);

    return Scaffold(
      backgroundColor: AppColors.backgroundPrimary,
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
      body: SolarBackground(
        child: FutureBuilder<List<dynamic>>(
          future: api.bars(),
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Padding(
                padding: EdgeInsets.all(AppSpacing.md),
                child: ToreLoadingSkeleton(lines: 6),
              );
            }
            if (snap.hasError) {
              return ToreErrorState(
                message: 'Impossible de charger les events.',
                onRetry: () => setState(() {}),
              );
            }

            final bars = (snap.data ?? []).cast<Map<String, dynamic>>();
            final events = <Map<String, dynamic>>[];
            for (final bar in bars) {
              events.add({'name': '${bar['name'] ?? 'Event'} — Tonight', 'when': 'Ce soir'});
              events.add({'name': '${bar['name'] ?? 'Event'} — Weekly', 'when': 'Cette semaine'});
            }

            final filtered = events.where((event) {
              if (_filter == 'all') return true;
              if (_filter == 'tonight') return event['when'] == 'Ce soir';
              return event['when'] == 'Cette semaine';
            }).toList();

            if (filtered.isEmpty) {
              return const ToreEmptyState(
                title: 'Aucun événement',
                message: "Aucune arène active pour ce filtre actuellement.",
              );
            }

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
                      return Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        child: SolarCard(
                          padding: const EdgeInsets.all(14),
                          child: Row(
                            children: [
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(item['name']!.toString(), style: const TextStyle(fontWeight: FontWeight.w700)),
                                    const SizedBox(height: 4),
                                    Text(item['when']!.toString(), style: AppTextStyles.muted),
                                  ],
                                ),
                              ),
                              const Icon(Icons.chevron_right),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                ),
                if (session.isGuest)
                  const Padding(
                    padding: EdgeInsets.all(12),
                    child: AuthRequiredNotice(message: 'Créer un event et gérer le staff nécessitent une session connectée.'),
                  ),
              ],
            );
          },
        ),
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
