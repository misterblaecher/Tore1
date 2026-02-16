import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/features/events/presentation/active_event_context_provider.dart';
import 'package:tore/features/hunt/hunt_providers.dart';
import 'package:tore/shared/utils/write_gate.dart';
import 'package:tore/ui/components/components.dart';

import '../../../state.dart';

class HuntLeaderboardScreen extends ConsumerStatefulWidget {
  const HuntLeaderboardScreen({super.key, required this.eventId, required this.huntId});
  final int eventId;
  final int huntId;

  @override
  ConsumerState<HuntLeaderboardScreen> createState() => _HuntLeaderboardScreenState();
}

class _HuntLeaderboardScreenState extends ConsumerState<HuntLeaderboardScreen> {
  final Set<String> _pendingSteal = <String>{};

  Future<void> _steal(String victimUserId, String victimName) async {
    final runtimeState = ref.read(activeEventContextProvider).valueOrNull?.eventState;
    final blockedReason = writeDisabledReason(ref, intent: WriteIntent.critical, runtimeState: runtimeState);
    if (blockedReason != null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(blockedReason)));
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Confirmer Steal'),
        content: Text('Voler des points à $victimName ?'),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('Annuler')),
          ElevatedButton(onPressed: () => Navigator.of(ctx).pop(true), child: const Text('Steal')),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    setState(() => _pendingSteal.add(victimUserId));
    try {
      final res = await ref.read(apiProvider).stealHunt(
            eventId: widget.eventId,
            huntId: widget.huntId,
            victimUserId: victimUserId,
            idempotencyKey: 'hunt-steal-${widget.eventId}-${widget.huntId}-$victimUserId-${DateTime.now().millisecondsSinceEpoch}',
          );
      if (!mounted) return;
      final message = res.ok ? 'Steal réussi: +${res.amount}' : _stealErrorLabel(res.result);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
      ref.invalidate(huntLeaderboardProvider(HuntLeaderboardKey(eventId: widget.eventId, huntId: widget.huntId)));
      ref.invalidate(activeHuntProvider(widget.eventId));
    } on DioException catch (e) {
      if (!mounted) return;
      final reason = (e.response?.data is Map) ? ((e.response?.data as Map)['detail']?['reason'] ?? (e.response?.data as Map)['reason']) : null;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Steal impossible: ${reason ?? e.response?.statusCode ?? e.message}')));
    } finally {
      if (mounted) setState(() => _pendingSteal.remove(victimUserId));
    }
  }

  String _stealErrorLabel(String result) {
    switch (result) {
      case 'COOLDOWN':
        return 'Cooldown actif, réessaie plus tard.';
      case 'VICTIM_PRIVATE':
        return 'Cette cible est privée.';
      default:
        return 'Steal non autorisé.';
    }
  }

  @override
  Widget build(BuildContext context) {
    final me = ref.watch(userIdProvider);
    final async = ref.watch(huntLeaderboardProvider(HuntLeaderboardKey(eventId: widget.eventId, huntId: widget.huntId)));

    return Scaffold(
      appBar: AppBar(title: const Text('Hunt Leaderboard')),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Leaderboard indisponible: $e')),
        data: (cached) {
          final lb = cached.data;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (cached.fromCache) const Padding(padding: EdgeInsets.only(bottom: 8), child: ToreChip(label: 'Mode lecture (cache)', variant: ToreChipVariant.warn)),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: lb.top3.map((row) => SizedBox(width: 180, child: ToreCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('#${row.rank} ${row.name}', style: const TextStyle(fontWeight: FontWeight.w800)), const SizedBox(height: 4), Text('Score ${row.score}')])))).toList(),
              ),
              const SizedBox(height: 12),
              const ToreDivider(),
              ...lb.list.map((row) {
                final isMe = me == row.userId;
                final disabled = isMe || cached.fromCache || _pendingSteal.contains(row.userId);
                return Container(
                  color: isMe ? Colors.amber.withOpacity(0.12) : null,
                  child: ToreListRow(
                    title: '#${row.rank} ${row.name}',
                    subtitle: 'Score ${row.score}${row.private ? ' · privé' : ''}',
                    trailing: isMe
                        ? const ToreChip(label: 'ME', variant: ToreChipVariant.info)
                        : TextButton(
                            onPressed: disabled ? null : () => _steal(row.userId, row.name),
                            child: _pendingSteal.contains(row.userId) ? const Text('...') : const Text('Steal'),
                          ),
                  ),
                );
              }),
            ],
          );
        },
      ),
    );
  }
}
