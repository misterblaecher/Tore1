import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../battle_providers.dart';

class BattlesLeaderboardScreen extends ConsumerWidget {
  const BattlesLeaderboardScreen({super.key, required this.eventId});
  final int eventId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(battlesLeaderboardProvider(eventId));
    return Scaffold(
      appBar: AppBar(title: const Text('Battles Leaderboard')),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Erreur: $e')),
        data: (cached) {
          final lb = cached.data;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(lb.rulesText),
              const SizedBox(height: 12),
              ...lb.top3.map((r) => ListTile(title: Text('#${r.rank} ${r.name}'), trailing: Text('${r.score}'))),
              const Divider(),
              ...lb.list.map((r) => ListTile(title: Text('#${r.rank} ${r.name}'), trailing: Text('${r.score}'))),
            ],
          );
        },
      ),
    );
  }
}
