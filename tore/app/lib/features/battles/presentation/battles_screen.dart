import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/features/events/presentation/active_event_context_provider.dart';
import 'package:tore/shared/widgets/service_limited_banner.dart';
import 'package:tore/shared/utils/runtime_write_guard.dart';
import 'package:tore/shared/utils/write_gate.dart';
import 'package:tore/state.dart';
import '../battle_providers.dart';
import 'battles_leaderboard_screen.dart';

class BattlesScreen extends ConsumerWidget {
  const BattlesScreen({super.key, required this.eventId});
  final int eventId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(battlesStateProvider(eventId));
    final activeEventCtx = ref.watch(activeEventContextProvider).valueOrNull;
    final runtimeState = activeEventCtx?.eventState;
    final readOnly = isReadOnly(ref);
    final degradedBlocked = isWriteDegradedBlocked(ref, WriteIntent.critical);
    final runtimeBlocked = isWriteBlockedByEventState(runtimeState);
    final writesBlocked = isWriteBlocked(
      readOnly: readOnly,
      degradedBlocked: degradedBlocked,
      runtimeBlocked: runtimeBlocked,
    );

    return Scaffold(
      appBar: AppBar(title: const Text('Battles')),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Battles indisponible: $e')),
        data: (cached) {
          final state = cached.data;
          final round = state.round;
          Future<void> sendVote(String choice) async {
            if (!canWrite(ref, intent: WriteIntent.critical, runtimeBlocked: runtimeBlocked) || round == null) {
              return;
            }
            await ref.read(apiProvider).battleVote(eventId: eventId, roundId: round.id, choice: choice, idempotencyKey: 'battle-$choice-${DateTime.now().millisecondsSinceEpoch}');
            ref.invalidate(battlesStateProvider(eventId));
            ref.invalidate(battlesLeaderboardProvider(eventId));
          }

          return ListView(padding: const EdgeInsets.all(16), children: [
            if (cached.fromCache) const Text('Mode cache/offline', style: TextStyle(color: Colors.amber)),
            if (writesBlocked)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: ServiceLimitedBanner(
                  message: writeBlockedMessage(
                    readOnly: readOnly,
                    degradedBlocked: degradedBlocked,
                    runtimeState: runtimeState,
                  ),
                ),
              ),
            if (round == null) const Text('Aucun round actif'),
            if (round != null) ...[
              Text(round.title, style: Theme.of(context).textTheme.titleLarge),
              Text('Status: ${round.status} • ${round.kind}'),
              Text('Votes A/B/P: ${state.counts['A'] ?? 0}/${state.counts['B'] ?? 0}/${state.counts['PARTICIPATE'] ?? 0}'),
              const SizedBox(height: 12),
              if (round.status == 'OPEN' && round.kind == 'PARTICIPATION') FilledButton(onPressed: writesBlocked ? null : () => sendVote('PARTICIPATE'), child: const Text('JE PARTICIPE')),
              if (round.status == 'OPEN' && round.kind == 'DUEL') ...[
                Row(children: [Expanded(child: FilledButton(onPressed: writesBlocked ? null : () => sendVote('A'), child: Text(round.optionALabel ?? 'TEAM A'))), const SizedBox(width: 8), Expanded(child: FilledButton(onPressed: writesBlocked ? null : () => sendVote('B'), child: Text(round.optionBLabel ?? 'TEAM B')))]),
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
