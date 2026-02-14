import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class QrUnknownScreen extends StatefulWidget {
  const QrUnknownScreen({super.key, required this.raw, required this.reason});

  final String raw;
  final String reason;

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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('QR inconnu')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(widget.reason, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            Text(
              widget.raw.isEmpty ? '(aucun contenu)' : widget.raw,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 18),
            TextField(
              controller: _manualController,
              decoration: const InputDecoration(
                labelText: 'Code manuel',
                hintText: 'Ex: tore://join_event?event_id=12',
              ),
            ),
            const Spacer(),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: widget.raw.isEmpty
                        ? null
                        : () async {
                            await Clipboard.setData(ClipboardData(text: widget.raw));
                            if (!context.mounted) return;
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('QR copié.')),
                            );
                          },
                    icon: const Icon(Icons.copy),
                    label: const Text('Copier'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.qr_code_scanner_outlined),
                    label: const Text('Retry scan'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: () => Navigator.of(context).pop(_manualController.text.trim()),
                icon: const Icon(Icons.keyboard_alt_outlined),
                label: const Text('Valider saisie manuelle'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
