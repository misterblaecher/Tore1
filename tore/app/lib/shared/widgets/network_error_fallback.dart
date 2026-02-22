import 'package:flutter/material.dart';

class NetworkErrorFallback extends StatelessWidget {
  const NetworkErrorFallback({
    super.key,
    required this.title,
    required this.message,
    required this.onRetry,
    this.icon = Icons.cloud_off_outlined,
  });

  final String title;
  final String message;
  final VoidCallback onRetry;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 56),
            const SizedBox(height: 14),
            Text(title, style: Theme.of(context).textTheme.titleLarge, textAlign: TextAlign.center),
            const SizedBox(height: 10),
            Text(message, style: Theme.of(context).textTheme.bodyMedium, textAlign: TextAlign.center),
            const SizedBox(height: 18),
            FilledButton.icon(onPressed: onRetry, icon: const Icon(Icons.refresh), label: const Text('Réessayer')),
          ],
        ),
      ),
    );
  }
}
