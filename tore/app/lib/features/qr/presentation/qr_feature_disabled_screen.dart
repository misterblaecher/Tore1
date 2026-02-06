import 'package:flutter/material.dart';

class QrFeatureDisabledScreen extends StatelessWidget {
  const QrFeatureDisabledScreen({super.key, required this.featureLabel});

  final String featureLabel;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Fonction désactivée'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Fonction désactivée : $featureLabel',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            const Text(
              'Cette fonctionnalité est désactivée pour cet event.',
            ),
            const Spacer(),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: () => Navigator.of(context).pop(),
                icon: const Icon(Icons.arrow_back),
                label: const Text('Retour'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
