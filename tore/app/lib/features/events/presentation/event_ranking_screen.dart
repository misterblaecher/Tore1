import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api.dart';
import '../../../state.dart';
import '../../../ui/components/tore_card.dart';

final eventRankingProvider = FutureProvider.family<EventRankingFetchResult, int>((ref, eventId) async {
  final api = ref.watch(apiProvider);
  return api.eventRankingWithCacheStatus(eventId);
});

class EventRankingScreen extends ConsumerWidget {
  const EventRankingScreen({super.key, required this.eventId});

  final int eventId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final rankingAsync = ref.watch(eventRankingProvider(eventId));
    return Scaffold(
      appBar: AppBar(title: const Text('Classement')),
      body: rankingAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('Classement indisponible: $error')),
        data: (result) {
          final payload = result.payload;
          final top3 = (payload['top3'] as List? ?? const []).cast<dynamic>();
          final list = (payload['list'] as List? ?? const []).cast<dynamic>();
          final me = payload['me'] is Map ? Map<String, dynamic>.from(payload['me'] as Map) : null;
          final updatedAt = DateTime.tryParse((payload['updatedAt'] ?? '').toString());
          final rulesText = (payload['rulesText'] ?? '').toString();
          final meRank = me?['rank'];

          return RefreshIndicator(
            onRefresh: () => ref.refresh(eventRankingProvider(eventId).future),
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: 3 + top3.length + list.length,
              itemBuilder: (context, index) {
                if (index == 0) {
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          updatedAt == null
                              ? (result.fromCache ? 'Classement hors-ligne (cache)' : 'Classement live')
                              : 'Mis à jour ${updatedAt.toLocal()}',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        if (result.fromCache)
                          const Padding(
                            padding: EdgeInsets.only(top: 4),
                            child: Text('Affichage du dernier classement en cache.'),
                          ),
                      ],
                    ),
                  );
                }
                if (index == 1) {
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Wrap(
                      spacing: 10,
                      runSpacing: 10,
                      children: [for (final row in top3) _TopCard(entry: Map<String, dynamic>.from(row as Map), meRank: meRank)],
                    ),
                  );
                }
                if (index == 2) {
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: ExpansionTile(
                      tilePadding: EdgeInsets.zero,
                      title: const Text('Règles du classement'),
                      children: [
                        Align(
                          alignment: Alignment.centerLeft,
                          child: Padding(
                            padding: const EdgeInsets.only(bottom: 6),
                            child: Text(rulesText),
                          ),
                        ),
                      ],
                    ),
                  );
                }

                final row = Map<String, dynamic>.from(list[index - 3] as Map);
                final highlightMe = meRank != null && row['rank'] == meRank;
                return Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(10),
                    color: highlightMe ? Colors.amber.withOpacity(0.15) : null,
                    border: Border.all(color: Colors.white12),
                  ),
                  child: Row(
                    children: [
                      SizedBox(width: 28, child: Text('#${row['rank']}')),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text((row['displayName'] ?? 'Player').toString(), style: const TextStyle(fontWeight: FontWeight.w600)),
                            const SizedBox(height: 2),
                            Text(_statsText(row), style: Theme.of(context).textTheme.bodySmall),
                          ],
                        ),
                      ),
                      Text('${row['score'] ?? 0}', style: const TextStyle(fontWeight: FontWeight.bold)),
                    ],
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }

  String _statsText(Map<String, dynamic> row) {
    final stats = row['stats'] is Map ? Map<String, dynamic>.from(row['stats'] as Map) : const <String, dynamic>{};
    return 'cmd ${stats['orders'] ?? 0} · dép ${stats['spentTickets'] ?? 0} · gifts ${stats['giftsSent'] ?? 0} · bets ${stats['bets'] ?? 0}';
  }
}

class _TopCard extends StatelessWidget {
  const _TopCard({required this.entry, this.meRank});

  final Map<String, dynamic> entry;
  final Object? meRank;

  @override
  Widget build(BuildContext context) {
    final rank = (entry['rank'] ?? 0) as int;
    final medal = rank == 1 ? '🥇' : (rank == 2 ? '🥈' : '🥉');
    final focused = meRank != null && meRank == rank;
    return SizedBox(
      width: 230,
      child: ToreCard(
        focused: focused,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('$medal  #$rank', style: const TextStyle(fontWeight: FontWeight.w800)),
            const SizedBox(height: 6),
            Text((entry['displayName'] ?? 'Player').toString(), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                Chip(label: Text('Score ${entry['score'] ?? 0}')),
                if ((entry['stats'] as Map?)?['orders'] != null) Chip(label: Text('Cmd ${(entry['stats'] as Map)['orders']}')),
                if ((entry['stats'] as Map?)?['spentTickets'] != null) Chip(label: Text('Dép ${(entry['stats'] as Map)['spentTickets']}')),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
