import 'package:flutter/material.dart';
import 'package:tore/ui/components/tore_card.dart';
import 'package:tore/ui/components/tore_cta.dart';

import '../hunt_models.dart';

class ClaimResultSheet extends StatelessWidget {
  const ClaimResultSheet({super.key, this.result, this.errorMessage});

  final HuntClaimResponse? result;
  final String? errorMessage;

  @override
  Widget build(BuildContext context) {
    final success = result != null && result!.ok && !result!.alreadyClaimed;
    final already = result != null && result!.alreadyClaimed;
    final title = success
        ? 'Checkpoint validé !'
        : already
            ? 'Déjà validé'
            : 'Validation impossible';
    final subtitle = success
        ? '+${result!.pointsAwarded} points'
        : already
            ? 'Ce checkpoint est déjà compté.'
            : (errorMessage ?? 'Action indisponible.');

    return Padding(
      padding: const EdgeInsets.all(16),
      child: ToreCard(
        focused: success,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title,
                style: Theme.of(context)
                    .textTheme
                    .titleLarge
                    ?.copyWith(fontWeight: FontWeight.w800)),
            const SizedBox(height: 8),
            Text(subtitle),
            if (result != null) ...[
              const SizedBox(height: 12),
              Text('Score total: ${result!.totalScore}',
                  style: const TextStyle(fontWeight: FontWeight.w700)),
            ],
            const SizedBox(height: 16),
            ToreCTA(label: 'OK', onPressed: () => Navigator.of(context).pop()),
          ],
        ),
      ),
    );
  }
}
