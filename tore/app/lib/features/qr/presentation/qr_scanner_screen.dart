import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../qr_router.dart';

class QrScannerScreen extends ConsumerStatefulWidget {
  const QrScannerScreen({super.key});

  @override
  ConsumerState<QrScannerScreen> createState() => _QrScannerScreenState();
}

class _QrScannerScreenState extends ConsumerState<QrScannerScreen> {
  final MobileScannerController _controller = MobileScannerController(
    detectionSpeed: DetectionSpeed.noDuplicates,
    autoStart: true,
  );

  bool _handling = false;
  bool _torchOn = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _handleBarcode(BarcodeCapture capture) async {
    if (_handling) return;
    final raw = capture.barcodes
        .map((b) => b.rawValue)
        .firstWhere((v) => v != null && v.trim().isNotEmpty, orElse: () => null);
    if (raw == null) return;

    setState(() => _handling = true);
    await _controller.stop();
    if (!mounted) return;

    await ref.read(qrRouterServiceProvider).route(context: context, raw: raw);

    if (!mounted) return;
    setState(() => _handling = false);
    unawaited(_controller.start());
  }

  Future<void> _openManualInput() async {
    final manual = await showDialog<String>(
      context: context,
      builder: (ctx) {
        final ctrl = TextEditingController();
        return AlertDialog(
          title: const Text('Saisie manuelle'),
          content: TextField(
            controller: ctrl,
            autofocus: true,
            decoration: const InputDecoration(hintText: 'Code ou tore://...'),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.of(ctx).pop(), child: const Text('Annuler')),
            ElevatedButton(
              onPressed: () => Navigator.of(ctx).pop(ctrl.text.trim()),
              child: const Text('Valider'),
            ),
          ],
        );
      },
    );

    if (!mounted || manual == null || manual.isEmpty) return;

    setState(() => _handling = true);
    await _controller.stop();
    await ref.read(qrRouterServiceProvider).route(context: context, raw: manual);
    if (!mounted) return;
    setState(() => _handling = false);
    unawaited(_controller.start());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          MobileScanner(
            controller: _controller,
            onDetect: _handleBarcode,
            errorBuilder: (context, error, child) {
              final msg = error.errorCode == MobileScannerErrorCode.permissionDenied
                  ? 'Permission caméra refusée.'
                  : 'Erreur caméra: ${error.errorCode.name}';
              return Center(child: Text(msg, textAlign: TextAlign.center));
            },
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  IconButton.filledTonal(
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.close),
                  ),
                  const Spacer(),
                  IconButton.filledTonal(
                    onPressed: () async {
                      await _controller.toggleTorch();
                      if (!mounted) return;
                      setState(() => _torchOn = !_torchOn);
                    },
                    icon: Icon(_torchOn ? Icons.flash_on : Icons.flash_off),
                  ),
                ],
              ),
            ),
          ),
          Align(
            alignment: Alignment.bottomCenter,
            child: SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (_handling)
                      const Padding(
                        padding: EdgeInsets.only(bottom: 10),
                        child: CircularProgressIndicator(),
                      ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      decoration: BoxDecoration(
                        color: Colors.black.withOpacity(0.55),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: const Text('Scanne un QR TORÈ', textAlign: TextAlign.center),
                    ),
                    const SizedBox(height: 10),
                    TextButton.icon(
                      onPressed: _openManualInput,
                      icon: const Icon(Icons.keyboard_alt_outlined),
                      label: const Text('Saisie manuelle'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
