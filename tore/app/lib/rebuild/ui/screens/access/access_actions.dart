import 'package:flutter/material.dart';

class AccessActions extends StatelessWidget {
  const AccessActions({
    super.key,
    required this.onTorch,
    required this.onManualCode,
    required this.onHelp,
    this.torchOn = false,
  });

  final VoidCallback onTorch;
  final VoidCallback onManualCode;
  final VoidCallback onHelp;
  final bool torchOn;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        FilledButton.tonalIcon(
          onPressed: onTorch,
          icon: Icon(torchOn ? Icons.flash_on : Icons.flash_auto),
          label: const Text('Lampe auto'),
        ),
        OutlinedButton.icon(
          onPressed: onManualCode,
          icon: const Icon(Icons.keyboard),
          label: const Text('Code manuel'),
        ),
        OutlinedButton.icon(
          onPressed: onHelp,
          icon: const Icon(Icons.help_outline),
          label: const Text('Aide'),
        ),
      ],
    );
  }
}
