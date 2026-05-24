import 'package:flutter/material.dart';
import 'package:tore/ui/components/components.dart';

class QrStatusScreen extends StatelessWidget {
  const QrStatusScreen({
    super.key,
    required this.title,
    required this.message,
    required this.icon,
    this.details,
  });

  final String title;
  final String message;
  final IconData icon;
  final String? details;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: ToreCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Icon(icon, size: 54),
              const SizedBox(height: 12),
              Text(title, style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 10),
              Text(message, style: Theme.of(context).textTheme.titleMedium),
              if (details != null && details!.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(details!, style: Theme.of(context).textTheme.bodySmall),
              ],
              const Spacer(),
              ToreCTA(
                label: 'Rescan',
                onPressed: () => Navigator.of(context).pop(),
              ),
              const SizedBox(height: 10),
              ToreCTA(
                label: 'Home',
                style: ToreCTAStyle.secondary,
                onPressed: () =>
                    Navigator.of(context).popUntil((route) => route.isFirst),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
