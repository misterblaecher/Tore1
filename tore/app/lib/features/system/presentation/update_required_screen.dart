import 'package:flutter/material.dart';

class UpdateRequiredScreen extends StatelessWidget {
  const UpdateRequiredScreen({
    super.key,
    required this.message,
    required this.currentVersion,
    required this.currentBuild,
  });

  final String message;
  final String currentVersion;
  final int currentBuild;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Mise à jour requise')),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 520),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.system_update_alt, size: 52),
                      const SizedBox(height: 16),
                      Text(
                        'Cette version de TORÈ doit être mise à jour.',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 12),
                      Text(message, textAlign: TextAlign.center),
                      const SizedBox(height: 16),
                      Text(
                        'Version actuelle : $currentVersion ($currentBuild)',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 12),
                      const Text(
                        'Les accès sont bloqués pour éviter des actions incompatibles avec le serveur.',
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
