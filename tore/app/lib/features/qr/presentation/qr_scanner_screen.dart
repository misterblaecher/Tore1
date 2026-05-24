import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../../../core/perf/perf_tracer.dart';
import '../../../core/perf/scan_suppression.dart';
import '../../../core/qr/qr_parser.dart';
import '../../../ui/app_design_system.dart';
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
      detectionSpeed: DetectionSpeed.noDuplicates, autoStart: true);
  final ScanSuppression _suppression = ScanSuppression();

  bool _handling = false;
  bool _torchOn = false;
  bool _detectedFlash = false;
  DateTime _scanLockUntil = DateTime.fromMillisecondsSinceEpoch(0);
  QrRouteOutcome? _lastOutcome;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  bool _localValidate(QrPayload payload) {
    final expiry = payload.expiresAt;
    if (expiry != null && expiry.isBefore(DateTime.now())) {
      setState(() => _lastOutcome = const QrRouteOutcome.denied('QR expiré'));
      return false;
    }
    return true;
  }

  Future<void> _handleDetectedRaw(String raw) async {
    if (_handling || DateTime.now().isBefore(_scanLockUntil)) return;
    if (_suppression.shouldSuppress(hash: hashQr(raw), now: DateTime.now()))
      return;

    HapticFeedback.selectionClick();
    setState(() {
      _detectedFlash = true;
      _scanLockUntil = DateTime.now().add(const Duration(milliseconds: 600));
    });
    Future<void>.delayed(const Duration(milliseconds: 200), () {
      if (mounted) setState(() => _detectedFlash = false);
    });

    if (widget.mode == QrScannerMode.pickRaw) {
      Navigator.of(context).pop(raw.trim());
      return;
    }

    final payload = ref.read(qrParserProvider).parse(raw);
    if (!_localValidate(payload)) return;

    setState(() => _handling = true);
    final scannerContext = context;
    await _controller.stop();
    if (!scannerContext.mounted) return;

    await ref.read(qrRouterServiceProvider).route(
          context: scannerContext,
          raw: raw,
          onOutcome: (outcome) => setState(() => _lastOutcome = outcome),
        );

    ref.read(perfTracerProvider).mark('screen_pushed');

    if (mounted) {
      setState(() => _handling = false);
      unawaited(_controller.start());
    }
  }

  Future<void> _handleBarcode(BarcodeCapture capture) async {
    final raw = capture.barcodes.map((b) => b.rawValue).firstWhere(
        (v) => v != null && v.trim().isNotEmpty,
        orElse: () => null);
    if (raw == null) return;
    await _handleDetectedRaw(raw);
  }

  Future<void> _manualCodeEntry() async {
    final controller = TextEditingController();
    final raw = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      builder: (context) => Padding(
        padding: EdgeInsets.only(
            left: 16,
            right: 16,
            top: 16,
            bottom: MediaQuery.of(context).viewInsets.bottom + 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Entrer un code',
                style: TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            TextField(
                controller: controller,
                decoration:
                    const InputDecoration(hintText: 'Code alphanumérique')),
            const SizedBox(height: 12),
            ToreButton.primary(
                label: 'Valider',
                icon: Icons.check,
                onPressed: () =>
                    Navigator.of(context).pop(controller.text.trim())),
          ],
        ),
      ),
    );
    if (raw != null && raw.isNotEmpty) {
      await _handleDetectedRaw(raw);
    }
  }

  Future<void> _openHelp() async {
    await showModalBottomSheet<void>(
      context: context,
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Aide scan',
                  style: TextStyle(fontWeight: FontWeight.w700, fontSize: 18)),
              const SizedBox(height: AppSpacing.sm),
              const Text(
                  'Centre le QR dans l\'anneau doré. Active la lampe si la scène est sombre.'),
              const SizedBox(height: AppSpacing.md),
              ToreButton.primary(
                  label: 'Réessayer',
                  icon: Icons.refresh,
                  onPressed: () => Navigator.of(context).pop()),
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
          const HaloBackground(child: SizedBox.expand()),
          MobileScanner(
            controller: _controller,
            onDetect: _handleBarcode,
          ),
          Center(
            child: TweenAnimationBuilder<double>(
              tween: Tween(begin: 0.7, end: 1.1),
              duration: const Duration(milliseconds: 1200),
              curve: Curves.easeInOut,
              builder: (_, ring, __) => Container(
                width: 250,
                height: 250,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(color: AppColors.accentGold, width: 3),
                  boxShadow: [
                    BoxShadow(
                        color:
                            AppColors.accentGold.withValues(alpha: 0.35 * ring),
                        blurRadius: 26)
                  ],
                ),
              ),
            ),
          ),
          if (_detectedFlash)
            IgnorePointer(child: Container(color: const Color(0x44F4B400))),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  IconButton.filledTonal(
                      onPressed: () => Navigator.of(context).pop(),
                      icon: const Icon(Icons.close)),
                  const Spacer(),
                  IconButton.filledTonal(
                    onPressed: () async {
                      await _controller.toggleTorch();
                      if (mounted) setState(() => _torchOn = !_torchOn);
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
                  child: Container(
                    padding: const EdgeInsets.all(10),
                    color: Colors.black54,
                    child: Text(_lastOutcome!.label),
                  ),
                ),
              ),
            ),
          Align(
            alignment: Alignment.bottomCenter,
            child: SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.md),
                child: Row(
                  children: [
                    Expanded(
                        child: ToreButton.secondary(
                            label: 'Code manuel',
                            icon: Icons.keyboard,
                            onPressed: _manualCodeEntry)),
                    const SizedBox(width: 8),
                    Expanded(
                        child: ToreButton.secondary(
                            label: 'Aide',
                            icon: Icons.help_outline,
                            onPressed: _openHelp)),
                  ],
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
