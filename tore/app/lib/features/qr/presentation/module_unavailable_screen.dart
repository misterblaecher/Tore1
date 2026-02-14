import 'package:flutter/material.dart';

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
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
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
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.qr_code_scanner_outlined),
                  label: const Text('Retry scan'),
                ),
              ),
              const SizedBox(height: 10),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: () => Navigator.of(context).popUntil((route) => route.isFirst),
                  icon: const Icon(Icons.home_outlined),
                  label: const Text('Retour home'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
