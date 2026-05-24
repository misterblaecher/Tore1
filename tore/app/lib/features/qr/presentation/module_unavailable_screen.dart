import 'package:flutter/material.dart';
import 'package:tore/ui/components/components.dart';

class ModuleUnavailableScreen extends StatelessWidget {
  const ModuleUnavailableScreen({
    super.key,
    required this.title,
    required this.message,
    required this.reasonCode,
  });

  final String title;
  final String message;
  final String reasonCode;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: ToreCard(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.block_outlined, size: 48),
                const SizedBox(height: 12),
                Text(
                  'Module indisponible',
                  style: Theme.of(context).textTheme.titleLarge,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(message, textAlign: TextAlign.center),
                const SizedBox(height: 8),
                Text(
                  'Code: $reasonCode',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 16),
                ToreCTA(
                  label: 'Retry scan',
                  style: ToreCTAStyle.secondary,
                  onPressed: () => Navigator.of(context).pop(),
                ),
                const SizedBox(height: 10),
                ToreCTA(
                  label: 'Retour home',
                  onPressed: () =>
                      Navigator.of(context).popUntil((route) => route.isFirst),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
