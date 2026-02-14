import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../qr_router.dart';

enum QrScannerMode { route, pickRaw }

class QrScannerScreen extends ConsumerStatefulWidget {
  const QrScannerScreen({super.key, this.mode = QrScannerMode.route});

  final QrScannerMode mode;

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
  int _failedScans = 0;
  String? _lastRaw;
  DateTime? _lastHandledAt;
  QrRouteOutcome? _lastOutcome;
  final List<String> _microLog = [];

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  bool _isCooldownHit(String raw) {
    final now = DateTime.now();
    final isSame = _lastRaw == raw;
    final isFast = _lastHandledAt != null && now.difference(_lastHandledAt!).inMilliseconds < 800;
    _lastRaw = raw;
    _lastHandledAt = now;
    return isSame && isFast;
  }

  Future<void> _handleDetectedRaw(String raw) async {
    if (_handling || _isCooldownHit(raw)) return;

    if (widget.mode == QrScannerMode.pickRaw) {
      await HapticFeedback.selectionClick();
      if (!mounted) return;
      Navigator.of(context).pop(raw.trim());
      return;
    }

    setState(() => _handling = true);
    await _controller.stop();
    if (!mounted) return;

    await ref.read(qrRouterServiceProvider).route(
      context: context,
      raw: raw,
      onOutcome: (outcome) {
        if (!mounted) return;
        final ts = TimeOfDay.now().format(context);
        _microLog.insert(0, '$ts · ${outcome.label}');
        if (_microLog.length > 3) {
          _microLog.removeRange(3, _microLog.length);
        }
        if (outcome.status == QrRouteStatus.success) {
          _failedScans = 0;
          HapticFeedback.lightImpact();
          SystemSound.play(SystemSoundType.click);
        } else {
          _failedScans += 1;
          HapticFeedback.mediumImpact();
        }
        setState(() => _lastOutcome = outcome);
      },
    );

    if (!mounted) return;
    setState(() => _handling = false);
    unawaited(_controller.start());
  }

  Future<void> _handleBarcode(BarcodeCapture capture) async {
    final raw = capture.barcodes
        .map((b) => b.rawValue)
        .firstWhere((v) => v != null && v.trim().isNotEmpty, orElse: () => null);
    if (raw == null) return;
    await _handleDetectedRaw(raw);
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
    await _handleDetectedRaw(manual);
  }

  @override
  Widget build(BuildContext context) {
    final suggestTorch = !_torchOn && _failedScans >= 3;

    return Scaffold(
      backgroundColor: Colors.black,
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
          Center(
            child: Container(
              width: 260,
              height: 260,
              decoration: BoxDecoration(
                border: Border.all(color: Colors.white70, width: 3),
                borderRadius: BorderRadius.circular(20),
              ),
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  IconButton.filledTonal(onPressed: () => Navigator.of(context).pop(), icon: const Icon(Icons.close)),
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
          if (_lastOutcome != null)
            Align(
              alignment: Alignment.topCenter,
              child: SafeArea(
                child: Padding(
                  padding: const EdgeInsets.only(top: 72),
                  child: _ScanFeedbackBanner(outcome: _lastOutcome!),
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
                    if (_handling) const Padding(padding: EdgeInsets.only(bottom: 10), child: CircularProgressIndicator()),
                    if (suggestTorch)
                      Container(
                        margin: const EdgeInsets.only(bottom: 8),
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                        decoration: BoxDecoration(color: Colors.orange.withOpacity(0.9), borderRadius: BorderRadius.circular(10)),
                        child: const Text('Luminosité faible détectée, active la lampe.'),
                      ),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      decoration: BoxDecoration(color: Colors.black.withOpacity(0.6), borderRadius: BorderRadius.circular(10)),
                      child: const Text('Scanner QR universel TORÈ', textAlign: TextAlign.center),
                    ),
                    const SizedBox(height: 10),
                    TextButton.icon(
                      onPressed: _openManualInput,
                      icon: const Icon(Icons.keyboard_alt_outlined),
                      label: const Text('Input manuel'),
                    ),
                    if (_microLog.isNotEmpty)
                      Container(
                        width: double.infinity,
                        margin: const EdgeInsets.only(top: 8),
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(color: Colors.black.withOpacity(0.6), borderRadius: BorderRadius.circular(10)),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [for (final line in _microLog) Text(line, style: const TextStyle(fontSize: 12))],
                        ),
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

class _ScanFeedbackBanner extends StatelessWidget {
  const _ScanFeedbackBanner({required this.outcome});

  final QrRouteOutcome outcome;

  @override
  Widget build(BuildContext context) {
    final color = switch (outcome.status) {
      QrRouteStatus.success => Colors.greenAccent,
      QrRouteStatus.denied => Colors.orangeAccent,
      QrRouteStatus.unknown => Colors.redAccent,
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.black.withOpacity(0.72),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.8)),
      ),
      child: Text(outcome.label, style: const TextStyle(fontWeight: FontWeight.w700)),
    );
  }
}
