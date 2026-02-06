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

  bool _handled = false;
  bool _torchOn = false;
  CameraFacing _facing = CameraFacing.back;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _handleBarcode(BarcodeCapture capture) async {
    if (_handled) return;
    final raw = capture.barcodes
        .map((b) => b.rawValue)
        .firstWhere((v) => v != null && v.trim().isNotEmpty, orElse: () => null);
    if (raw == null) return;

    setState(() => _handled = true);
    await _controller.stop();
    if (!mounted) return;

    await handleQr(context: context, ref: ref, raw: raw);

    if (!mounted) return;
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Scanner QR'),
        actions: [
          IconButton(
            tooltip: _torchOn ? 'Éteindre le flash' : 'Allumer le flash',
            icon: Icon(_torchOn ? Icons.flash_on : Icons.flash_off),
            onPressed: () async {
              await _controller.toggleTorch();
              setState(() => _torchOn = !_torchOn);
            },
          ),
          IconButton(
            tooltip: 'Switch caméra',
            icon: const Icon(Icons.cameraswitch_outlined),
            onPressed: () async {
              await _controller.switchCamera();
              setState(() {
                _facing = _facing == CameraFacing.back
                    ? CameraFacing.front
                    : CameraFacing.back;
              });
            },
          ),
        ],
      ),
      body: MobileScanner(
        controller: _controller,
        onDetect: _handleBarcode,
        errorBuilder: (context, error, child) {
          final msg = error.errorCode == MobileScannerErrorCode.permissionDenied
              ? 'Permission caméra refusée. Active-la dans les réglages.'
              : 'Erreur scanner: ${error.errorCode.name}';
          return Center(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.qr_code_scanner_outlined, size: 48),
                  const SizedBox(height: 12),
                  Text(msg, textAlign: TextAlign.center),
                  const SizedBox(height: 12),
                  ElevatedButton.icon(
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.arrow_back),
                    label: const Text('Retour'),
                  ),
                ],
              ),
            ),
          );
        },
      ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Text(
            'Caméra: ${_facing == CameraFacing.back ? 'Arrière' : 'Avant'}',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ),
      ),
    );
  }
<<<<<<< HEAD
}
=======
}
>>>>>>> cccfa9d6d4f0e1ae9c1d17452eb3be68653b49bf
