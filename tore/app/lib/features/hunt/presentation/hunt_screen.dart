import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/core/qr/qr_parser.dart';
import 'package:tore/features/events/presentation/active_event_context_provider.dart';
import 'package:tore/features/hunt/hunt_models.dart';
import 'package:tore/features/hunt/hunt_providers.dart';
import 'package:tore/features/hunt/presentation/claim_result_sheet.dart';
import 'package:tore/features/hunt/presentation/hunt_leaderboard_screen.dart';
import 'package:tore/features/qr/presentation/qr_scanner_screen.dart';
import 'package:tore/shared/utils/write_gate.dart';
import 'package:tore/ui/components/components.dart';

import '../../../state.dart';

class HuntScreen extends ConsumerStatefulWidget {
  const HuntScreen({super.key, required this.eventId, this.initialClaimPayload});
  final int eventId;
  final QrPayload? initialClaimPayload;

  @override
  ConsumerState<HuntScreen> createState() => _HuntScreenState();
}

class _HuntScreenState extends ConsumerState<HuntScreen> {
  String? _lastClaimInfo;
  bool _claiming = false;

  @override
  void initState() {
    super.initState();
    if (widget.initialClaimPayload != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _claimFromPayload(widget.initialClaimPayload!));
    }
  }

  Future<void> _openScanner(ActiveHunt hunt) async {
    final raw = await Navigator.of(context).push<String>(
      MaterialPageRoute(builder: (_) => const QrScannerScreen(mode: QrScannerMode.pickRaw)),
    );
    if (!mounted || raw == null || raw.isEmpty) return;
    final payload = ref.read(qrParserProvider).parse(raw);
    if (payload.type != QrType.hunt) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Ce QR n’est pas un checkpoint Hunt.')));
      return;
    }
    await _claimFromPayload(payload, hunt: hunt);
  }

  Future<void> _claimFromPayload(QrPayload payload, {ActiveHunt? hunt}) async {
    final eventCtx = ref.read(activeEventContextProvider).valueOrNull;
    final runtimeState = eventCtx?.eventState;
    final reason = writeDisabledReason(ref, intent: WriteIntent.critical, runtimeState: runtimeState);
    if (reason != null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(reason)));
      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        builder: (_) => ClaimResultSheet(errorMessage: reason),
      );
      return;
    }

    final payloadEventId = int.tryParse((payload.fields['event_id'] ?? '').toString()) ?? payload.eventId;
    if (payloadEventId != null && payloadEventId != widget.eventId) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Ce checkpoint est pour un autre event.')));
      return;
    }

    final huntId = int.tryParse((payload.fields['hunt_id'] ?? '').toString()) ?? hunt?.id;
    final checkpointId = int.tryParse((payload.fields['checkpoint_id'] ?? '').toString());
    final token = (payload.fields['token'] ?? payload.tokenId ?? '').toString();
    if (huntId == null || checkpointId == null || token.isEmpty) {
      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        builder: (_) => const ClaimResultSheet(errorMessage: 'QR checkpoint incomplet.'),
      );
      return;
    }

    setState(() => _claiming = true);
    HapticFeedback.lightImpact();
    try {
      final result = await ref.read(apiProvider).claimHunt(
            eventId: widget.eventId,
            huntId: huntId,
            checkpointId: checkpointId,
            token: token,
            idempotencyKey: 'hunt-claim-${widget.eventId}-$huntId-$checkpointId-${DateTime.now().millisecondsSinceEpoch}',
          );
      if (!mounted) return;
      HapticFeedback.heavyImpact();
      SystemSound.play(SystemSoundType.click);
      setState(() {
        _lastClaimInfo = result.alreadyClaimed ? 'Déjà validé' : '+${result.pointsAwarded} points';
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(result.alreadyClaimed ? 'Checkpoint déjà validé.' : 'Checkpoint validé: +${result.pointsAwarded} points')),
      );
      ref.invalidate(activeHuntProvider(widget.eventId));
      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        builder: (_) => ClaimResultSheet(result: result),
      );
    } on DioException catch (e) {
      final reason = (e.response?.data is Map) ? ((e.response?.data as Map)['detail']?['reason'] ?? (e.response?.data as Map)['reason']) : null;
      final msg = 'Erreur claim: ${reason ?? e.response?.statusCode ?? e.message}';
      if (!mounted) return;
      HapticFeedback.mediumImpact();
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        builder: (_) => ClaimResultSheet(errorMessage: msg),
      );
    } finally {
      if (mounted) setState(() => _claiming = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final huntAsync = ref.watch(activeHuntProvider(widget.eventId));
    final state = ref.watch(activeEventContextProvider).valueOrNull?.eventState;
    final blockedReason = writeDisabledReason(ref, intent: WriteIntent.critical, runtimeState: state);
    return Scaffold(
      appBar: AppBar(title: const Text('Hunt')),
      body: huntAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('Hunt indisponible: $error')),
        data: (cached) {
          final hunt = cached.data;
          final ended = hunt.endsAt != null && DateTime.now().isAfter(hunt.endsAt!);
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Row(
                children: [
                  Expanded(child: Text(hunt.title, style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700))),
                  ToreChip(label: ended ? 'ENDED' : 'ACTIVE', variant: ended ? ToreChipVariant.closed : ToreChipVariant.live),
                ],
              ),
              const SizedBox(height: 8),
              Text(hunt.description),
              const SizedBox(height: 8),
              Text('Fin: ${hunt.endsAt?.toLocal() ?? '-'} · checkpoints ${hunt.checkpointsCount}'),
              if (cached.fromCache) ...[
                const SizedBox(height: 8),
                const ToreChip(label: 'Mode lecture (cache)', variant: ToreChipVariant.warn),
              ],
              const SizedBox(height: 12),
              ToreCard(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Text('My score', style: TextStyle(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 6),
                  Text('${hunt.myScore}', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
                  if (_lastClaimInfo != null) Text('Dernière validation: $_lastClaimInfo'),
                ]),
              ),
              const SizedBox(height: 16),
              ToreCTA(
                label: blockedReason == null ? 'Scan checkpoint' : 'Scan checkpoint (bloqué)',
                onPressed: (blockedReason == null && !_claiming && !ended) ? () => _openScanner(hunt) : null,
                busy: _claiming,
              ),
              if (blockedReason != null) ...[
                const SizedBox(height: 8),
                Text(blockedReason, style: Theme.of(context).textTheme.bodySmall),
              ],
              const SizedBox(height: 10),
              ToreCTA(
                label: 'Leaderboard',
                style: ToreCTAStyle.secondary,
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => HuntLeaderboardScreen(eventId: widget.eventId, huntId: hunt.id)),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
