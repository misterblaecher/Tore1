import 'package:flutter/material.dart';

import '../../features/auth/presentation/email_auth_screen.dart';
import '../../ui/app_design_system.dart';

class RequireAuthSheet extends StatelessWidget {
  const RequireAuthSheet({super.key, this.message = 'Cette action nécessite un compte connecté.'});

  final String message;

  static Future<void> show(BuildContext context, {String? message}) {
    return showModalBottomSheet<void>(
      context: context,
      builder: (_) => RequireAuthSheet(message: message ?? 'Cette action nécessite un compte connecté.'),
    );
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text('Connecte-toi pour continuer', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18)),
            const SizedBox(height: AppSpacing.sm),
            Text(message),
            const SizedBox(height: AppSpacing.md),
            ToreButton.primary(
              label: 'Se connecter',
              icon: Icons.login,
              onPressed: () {
                Navigator.of(context).pop();
                Navigator.of(context).push(MaterialPageRoute(builder: (_) => const EmailAuthScreen()));
              },
            ),
            const SizedBox(height: AppSpacing.sm),
            ToreButton.secondary(
              label: 'Plus tard',
              icon: Icons.schedule,
              onPressed: () => Navigator.of(context).pop(),
            ),
          ],
        ),
      ),
    );
  }
}
