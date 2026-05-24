import 'package:flutter/material.dart';

import '../../../models/rebuild_types.dart';
import '../../theme/tore_theme.dart';
import '../../widgets/primitives.dart';

class UpdateRequiredScreen extends StatelessWidget {
  const UpdateRequiredScreen({
    super.key,
    required this.mode,
    required this.message,
    required this.blockedByVersion,
  });

  final ToreMode mode;
  final String message;
  final bool blockedByVersion;

  @override
  Widget build(BuildContext context) {
    final isOrga = mode == ToreMode.orga;
    return ScreenScaffold(
      title: 'Update required',
      scopeBadges: [isOrga ? 'ORGA' : 'USER', 'FROZEN'],
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Card(
            color: ToreTokens.warning.withValues(alpha: .15),
            child: Padding(
              padding: const EdgeInsets.all(ToreTokens.s12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                      isOrga
                          ? 'Writes blocked for operator safety.'
                          : 'Read-only mode active for safety.',
                      style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: ToreTokens.s8),
                  Text(message),
                  const SizedBox(height: ToreTokens.s8),
                  Text(blockedByVersion
                      ? 'Please update to continue.'
                      : 'Temporary freeze in progress.'),
                ],
              ),
            ),
          ),
          const SizedBox(height: ToreTokens.s12),
          const BlockedStateView(
            title: 'Client restricted',
            message:
                'This build can read but cannot perform writes until update/freeze is lifted.',
          ),
        ],
      ),
    );
  }
}
