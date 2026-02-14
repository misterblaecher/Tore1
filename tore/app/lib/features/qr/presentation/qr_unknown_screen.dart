import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:tore/ui/components/components.dart';

class QrUnknownScreen extends StatefulWidget {
  const QrUnknownScreen({
    super.key,
    required this.raw,
    required this.reason,
    this.reasonCode = 'unknown',
  });

  final String raw;
  final String reason;
  final String reasonCode;

  @override
  State<QrUnknownScreen> createState() => _QrUnknownScreenState();
}

class _QrUnknownScreenState extends State<QrUnknownScreen> {
  late final TextEditingController _manualController;

  @override
  void initState() {
    super.initState();
    _manualController = TextEditingController(text: widget.raw);
  }

  @override
  void dispose() {
    _manualController.dispose();
    super.dispose();
  }

  String _maskedRaw(String raw) {
    if (raw.length <= 10) return raw;
    return '${raw.substring(0, 6)}…${raw.substring(raw.length - 4)}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('QR inconnu')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: ToreCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(widget.reason, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              Text('Code: ${widget.reasonCode}', style: Theme.of(context).textTheme.bodySmall),
              const SizedBox(height: 12),
              Text('Raw (masqué): ${_maskedRaw(widget.raw)}'),
              const SizedBox(height: 12),
              const Text('Suggestions:'),
              const Text('• Vérifie que le QR commence par tore://'),
              const Text('• Vérifie si le QR appartient au bon module/event'),
              const Text('• Demande un nouveau QR si nécessaire'),
              const SizedBox(height: 16),
              TextField(
                controller: _manualController,
                decoration: const InputDecoration(
                  labelText: 'Code manuel',
                  hintText: 'Ex: tore://join_event?event_id=12',
                ),
              ),
              const Spacer(),
              ToreCTA(
                label: 'Copier raw',
                style: ToreCTAStyle.secondary,
                onPressed: widget.raw.isEmpty
                    ? null
                    : () async {
                        await Clipboard.setData(ClipboardData(text: widget.raw));
                        if (!context.mounted) return;
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('QR copié.')),
                        );
                      },
              ),
              const SizedBox(height: 10),
              ToreCTA(
                label: 'Rescan',
                style: ToreCTAStyle.secondary,
                onPressed: () => Navigator.of(context).pop(),
              ),
              const SizedBox(height: 10),
              ToreCTA(
                label: 'Valider saisie manuelle',
                onPressed: () => Navigator.of(context).pop(_manualController.text.trim()),
              ),
              const SizedBox(height: 10),
              ToreCTA(
                label: 'Home',
                style: ToreCTAStyle.secondary,
                onPressed: () => Navigator.of(context).popUntil((route) => route.isFirst),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
