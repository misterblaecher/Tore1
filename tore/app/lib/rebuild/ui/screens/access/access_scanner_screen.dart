import 'dart:async';

import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../../../models/rebuild_types.dart';
import '../../theme/tore_theme.dart';
import 'access_actions.dart';
import 'access_scan_frame.dart';

class AccessScannerScreen extends StatefulWidget {
  const AccessScannerScreen({
    super.key,
    required this.onResolve,
    this.network = ConnectivityState.online,
  });

  final Future<void> Function(String payload) onResolve;
  final ConnectivityState network;

  @override
  State<AccessScannerScreen> createState() => _AccessScannerScreenState();
}

class _AccessScannerScreenState extends State<AccessScannerScreen> {
  final MobileScannerController _controller = MobileScannerController(
    detectionSpeed: DetectionSpeed.noDuplicates,
    autoStart: true,
  );

  bool _handling = false;
  bool _torchOn = false;
  bool _detectedFlash = false;
  DateTime _scanLockUntil = DateTime.fromMillisecondsSinceEpoch(0);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _handleBarcode(BarcodeCapture capture) async {
    final raw = capture.barcodes.map((barcode) => barcode.rawValue).firstWhere(
          (value) => value != null && value.trim().isNotEmpty,
          orElse: () => null,
        );
    if (raw == null) return;
    await _resolvePayload(raw);
  }

  Future<void> _resolvePayload(String payload) async {
    if (_handling || DateTime.now().isBefore(_scanLockUntil)) return;
    setState(() {
      _handling = true;
      _detectedFlash = true;
      _scanLockUntil = DateTime.now().add(const Duration(milliseconds: 600));
    });
    Future<void>.delayed(const Duration(milliseconds: 180), () {
      if (mounted) setState(() => _detectedFlash = false);
    });

    await _controller.stop();
    try {
      await widget.onResolve(payload.trim());
    } finally {
      if (mounted) {
        setState(() => _handling = false);
        unawaited(_controller.start());
      }
    }
  }

  Future<void> _toggleTorch() async {
    await _controller.toggleTorch();
    if (mounted) setState(() => _torchOn = !_torchOn);
  }

  Future<void> _openManualCode() async {
    final controller = TextEditingController();
    final value = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      builder: (context) => Padding(
        padding: EdgeInsets.only(
          left: ToreTokens.s16,
          right: ToreTokens.s16,
          top: ToreTokens.s16,
          bottom: MediaQuery.of(context).viewInsets.bottom + ToreTokens.s16,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Entrer un code', style: TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: ToreTokens.s8),
            TextField(
              controller: controller,
              decoration: const InputDecoration(hintText: 'Code alphanumérique'),
            ),
            const SizedBox(height: ToreTokens.s12),
            FilledButton.icon(
              onPressed: () => Navigator.of(context).pop(controller.text.trim()),
              icon: const Icon(Icons.check),
              label: const Text('Valider'),
            ),
          ],
        ),
      ),
    );
    if (value != null && value.isNotEmpty) {
      await _resolvePayload(value);
    }
  }

  Future<void> _openHelp() async {
    await showModalBottomSheet<void>(
      context: context,
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(ToreTokens.s16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Aide scan', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 18)),
              const SizedBox(height: ToreTokens.s8),
              const Text(
                'Centre le QR dans le cadre doré. Active la lampe si la scène est sombre, ou passe par le code manuel.',
              ),
              const SizedBox(height: ToreTokens.s16),
              FilledButton.icon(
                onPressed: () => Navigator.of(context).pop(),
                icon: const Icon(Icons.refresh),
                label: const Text('Réessayer'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          MobileScanner(controller: _controller, onDetect: _handleBarcode),
          Center(
            child: IgnorePointer(
              child: AccessScanFrame(
                height: 320,
                live: true,
                child: _detectedFlash
                    ? Container(color: const Color(0x33F4C430))
                    : const SizedBox.shrink(),
              ),
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(ToreTokens.s12),
              child: Row(
                children: [
                  IconButton.filledTonal(
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.close),
                  ),
                  const Spacer(),
                  if (widget.network != ConnectivityState.online)
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: ToreTokens.s8,
                        vertical: ToreTokens.s4,
                      ),
                      decoration: BoxDecoration(
                        color: ToreTokens.warning,
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: const Text(
                        'OFFLINE',
                        style: TextStyle(fontWeight: FontWeight.w800, fontSize: 11),
                      ),
                    ),
                ],
              ),
            ),
          ),
          Align(
            alignment: Alignment.bottomCenter,
            child: SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(ToreTokens.s16),
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: Colors.black.withValues(alpha: 0.64),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: ToreTokens.border),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(ToreTokens.s16),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('ACCÈS', style: Theme.of(context).textTheme.headlineSmall),
                        const SizedBox(height: ToreTokens.s4),
                        const Text(
                          'Scanne un code TORÈ, invitation, menu, WiFi ou pass staff.',
                        ),
                        const SizedBox(height: ToreTokens.s12),
                        AccessActions(
                          onTorch: _toggleTorch,
                          onManualCode: _openManualCode,
                          onHelp: _openHelp,
                          torchOn: _torchOn,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
          if (_handling) const Center(child: CircularProgressIndicator()),
        ],
      ),
    );
  }
}
