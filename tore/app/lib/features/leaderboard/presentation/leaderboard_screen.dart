import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../state.dart';

class LeaderboardScreen extends ConsumerWidget {
  const LeaderboardScreen({super.key, this.eventId});

  final int? eventId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final api = ref.watch(apiProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text(
          eventId == null ? 'Leaderboard' : 'Leaderboard — Event #$eventId',
        ),
      ),
      body: FutureBuilder<List<dynamic>>(
        future: api.leaderboard(eventId: eventId),
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(child: Text('Erreur: ${snap.error}'));
          }

          final rows = snap.data ?? const [];
          if (rows.isEmpty) {
            return const Center(child: Text('Aucun score pour le moment'));
          }

          return ListView.separated(
            itemCount: rows.length,
            separatorBuilder: (context, index) => const Divider(height: 1),
            itemBuilder: (_, i) {
              final r = Map<String, dynamic>.from(rows[i] as Map);

              final rank = (r['rank'] as num?)?.toInt() ?? (i + 1);
              final name = (r['display_name'] ?? r['user_id'] ?? '—')
                  .toString();
              final score = (r['score'] ?? r['points'] ?? r['total'] ?? 0)
                  .toString();

              return ListTile(
                leading: CircleAvatar(child: Text('$rank')),
                title: Text(name),
                trailing: Text(
                  score,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              );
            },
          );
        },
      ),
    );
  }
}
