import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../ui/app_design_system.dart';

class UnknownQrScreen extends StatefulWidget {
  const UnknownQrScreen({
    super.key,
    required this.raw,
    required this.reason,
    this.reasonCode = 'unknown',
  });

  final String raw;
  final String reason;
  final String reasonCode;

  @override
  State<UnknownQrScreen> createState() => _UnknownQrScreenState();
}

class _UnknownQrScreenState extends State<UnknownQrScreen> {
  late final TextEditingController _manualController;
  late final DateTime _now;

  @override
  void initState() {
    super.initState();
    _manualController = TextEditingController(text: widget.raw);
    _now = DateTime.now();
  }

  @override
  void dispose() {
    _manualController.dispose();
    super.dispose();
  }

  String get _diagnostic =>
      'qr_length=${widget.raw.length} | timestamp=${_now.toIso8601String()} | env=${kReleaseMode ? 'release' : 'debug'}';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('QR non reconnu')),
      backgroundColor: AppColors.backgroundPrimary,
      body: SolarBackground(
        child: ListView(
          padding: const EdgeInsets.all(AppSpacing.md),
          children: [
            ToreCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const ToreSectionHeader('QR non reconnu'),
                  Text(widget.reason),
                  const SizedBox(height: AppSpacing.xs),
                  Text('Code ${widget.reasonCode}', style: AppTextStyles.muted),
                  const SizedBox(height: AppSpacing.md),
                  TextField(
                    controller: _manualController,
                    decoration: const InputDecoration(labelText: 'Entrer un code', hintText: 'Code alphanumérique ou URL'),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  SelectableText(_diagnostic, style: AppTextStyles.muted),
                  const SizedBox(height: AppSpacing.md),
                  ToreButton.primary(
                    label: 'Réessayer',
                    icon: Icons.qr_code_scanner,
                    onPressed: () => Navigator.of(context).pop(),
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  ToreButton.secondary(
                    label: 'Entrer un code',
                    icon: Icons.keyboard,
                    onPressed: () => Navigator.of(context).pop(_manualController.text.trim()),
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  ToreButton.secondary(
                    label: 'Copier le diagnostic',
                    icon: Icons.copy,
                    onPressed: () async {
                      await Clipboard.setData(ClipboardData(text: _diagnostic));
                    },
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class QrUnknownScreen extends UnknownQrScreen {
  const QrUnknownScreen({super.key, required super.raw, required super.reason, super.reasonCode});
}
