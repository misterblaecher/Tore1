import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/core/write_gate.dart';
import 'package:tore/state.dart';
import '../battle_providers.dart';
import 'battles_leaderboard_screen.dart';

class BattlesScreen extends ConsumerWidget {
  const BattlesScreen({super.key, required this.eventId});
  final int eventId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(battlesStateProvider(eventId));
    return Scaffold(
      appBar: AppBar(title: const Text('Battles')),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Battles indisponible: $e')),
        data: (cached) {
          final state = cached.data;
          final round = state.round;
          Future<void> sendVote(String choice) async {
            final gate = await WriteGate.guard(context: context, ref: ref, eventId: eventId, critical: true, action: 'battle vote');
            if (!gate.allowed || round == null) return;
            await ref.read(apiProvider).battleVote(eventId: eventId, roundId: round.id, choice: choice, idempotencyKey: 'battle-$choice-${DateTime.now().millisecondsSinceEpoch}');
            ref.invalidate(battlesStateProvider(eventId));
            ref.invalidate(battlesLeaderboardProvider(eventId));
          }

          return ListView(padding: const EdgeInsets.all(16), children: [
            if (cached.fromCache) const Text('Mode cache/offline', style: TextStyle(color: Colors.amber)),
            if (round == null) const Text('Aucun round actif'),
            if (round != null) ...[
              Text(round.title, style: Theme.of(context).textTheme.titleLarge),
              Text('Status: ${round.status} • ${round.kind}'),
              Text('Votes A/B/P: ${state.counts['A'] ?? 0}/${state.counts['B'] ?? 0}/${state.counts['PARTICIPATE'] ?? 0}'),
              const SizedBox(height: 12),
              if (round.status == 'OPEN' && round.kind == 'PARTICIPATION') FilledButton(onPressed: () => sendVote('PARTICIPATE'), child: const Text('JE PARTICIPE')),
              if (round.status == 'OPEN' && round.kind == 'DUEL') ...[
                Row(children: [Expanded(child: FilledButton(onPressed: () => sendVote('A'), child: Text(round.optionALabel ?? 'TEAM A'))), const SizedBox(width: 8), Expanded(child: FilledButton(onPressed: () => sendVote('B'), child: Text(round.optionBLabel ?? 'TEAM B')))]),
              ],
              if (round.status == 'LOCKED') Card(child: ListTile(title: const Text('Winner'), subtitle: Text(round.winner ?? 'NONE'))),
            ],
            const SizedBox(height: 16),
            OutlinedButton(onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => BattlesLeaderboardScreen(eventId: eventId))), child: const Text('Voir classement')),
          ]);
        },
      ),
    );
  }
}
