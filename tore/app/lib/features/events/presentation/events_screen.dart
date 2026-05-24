import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../state.dart';
import '../../../core/app_context/app_context.dart';
import '../../../core/network/error_mapper.dart';
import 'event_config_providers.dart';
import '../../menu_market/presentation/menu_screen.dart';

class EventsScreen extends ConsumerWidget {
  const EventsScreen({super.key, required this.barId, required this.barName});

  final int barId;
  final String barName;

  DateTime? _tryParseDt(dynamic v) {
    if (v == null) return null;
    final s = v.toString();
    if (s.isEmpty) return null;
    try {
      return DateTime.parse(s);
    } catch (_) {
      return null;
    }
  }

  String _fmt(DateTime dt) {
    String two(int n) => n.toString().padLeft(2, '0');
    return '${two(dt.day)}/${two(dt.month)} ${two(dt.hour)}:${two(dt.minute)}';
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final api = ref.read(apiProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text('Événements — $barName'),
      ),
      body: FutureBuilder<List<dynamic>>(
        future: api.events(barId),
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(
                child: Text(ErrorMapper.message(snap.error as Object)));
          }

          final items = (snap.data ?? []).cast<Map<String, dynamic>>();
          if (items.isEmpty) {
            return const Center(child: Text('Aucun événement'));
          }

          DateTime? getStart(Map<String, dynamic> e) =>
              _tryParseDt(e['starts_at'] ?? e['start_at'] ?? e['start']);
          DateTime? getEnd(Map<String, dynamic> e) =>
              _tryParseDt(e['ends_at'] ?? e['end_at'] ?? e['end']);

          // Tri: par date de début (plus proche en haut). Fallback: id.
          final sorted = [...items]..sort((a, b) {
              final sa = getStart(a);
              final sb = getStart(b);
              if (sa != null && sb != null) return sa.compareTo(sb);
              final ia = (a['id'] as int?) ?? 0;
              final ib = (b['id'] as int?) ?? 0;
              return ib.compareTo(ia);
            });

          return ListView.separated(
            padding: const EdgeInsets.all(12),
            itemCount: sorted.length,
            separatorBuilder: (_, __) => const SizedBox(height: 10),
            itemBuilder: (context, i) {
              final e = sorted[i];

              final id = (e['id'] as int?) ?? 0;
              final rawName = (e['name'] ?? 'Event $id').toString();

              final start = getStart(e);
              final end = getEnd(e);

              final isFree = (e['is_free'] ?? e['free'] ?? false) == true;
              final subtitle = (start == null && end == null)
                  ? null
                  : Text(
                      '${start != null ? _fmt(start) : '?'}  →  ${end != null ? _fmt(end) : '?'}',
                      style: Theme.of(context).textTheme.bodySmall,
                    );

              final title = Text(
                rawName,
                style: Theme.of(context).textTheme.titleMedium,
              );

              return InkWell(
                borderRadius: BorderRadius.circular(16),
                onTap: () {
                  // Persist selection in global context.
                  ref.read(appContextProvider.notifier).setBar(
                        barId: barId,
                        barName: barName,
                      );
                  ref.read(appContextProvider.notifier).enterEvent(
                        eventId: id,
                        eventName: rawName,
                      );
                  ref.read(eventConfigProvider(id).future);
                  Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => MenuScreen(eventId: id)),
                  );
                },
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
                  decoration: BoxDecoration(
                    color: Theme.of(context)
                        .colorScheme
                        .surface
                        .withValues(alpha: 0.06),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(
                      color: Colors.white.withValues(alpha: 0.06),
                    ),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Expanded(child: title),
                                if (isFree)
                                  Padding(
                                    padding: const EdgeInsets.only(left: 8),
                                    child: _Badge(text: 'GRATUIT'),
                                  ),
                              ],
                            ),
                            if (subtitle != null) ...[
                              const SizedBox(height: 6),
                              subtitle,
                            ],
                          ],
                        ),
                      ),
                      const SizedBox(width: 8),
                      const Icon(Icons.chevron_right),
                    ],
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  const _Badge({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.secondary.withValues(alpha: 0.18),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
      ),
      child: Text(
        text,
        style: Theme.of(context).textTheme.labelSmall,
      ),
    );
  }
}
