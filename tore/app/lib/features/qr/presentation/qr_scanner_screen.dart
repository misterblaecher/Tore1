import 'dart:async';

import 'package:flutter/scheduler.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../../../core/perf/perf_tracer.dart';
import '../../../core/perf/scan_suppression.dart';
import '../../../core/qr/qr_parser.dart';
import 'code_entry_sheet.dart';
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
  bool _detectedFlash = false;
  int _failedScans = 0;
  final ScanSuppression _suppression = ScanSuppression();
  QrRouteOutcome? _lastOutcome;
  final List<String> _microLog = [];

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
    final now = DateTime.now();
    final qrHash = hashQr(raw);
    if (_handling || _suppression.shouldSuppress(hash: qrHash, now: now)) return;

    HapticFeedback.selectionClick();
    SystemSound.play(SystemSoundType.click);
    setState(() {
      _lastOutcome = const QrRouteOutcome.success("Scan détecté…");
      _detectedFlash = true;
    });
    Future<void>.delayed(const Duration(milliseconds: 180), () {
      if (!mounted) return;
      setState(() => _detectedFlash = false);
    });
    ref.read(perfTracerProvider).mark('scan_detected');

    if (widget.mode == QrScannerMode.pickRaw) {
      if (!mounted) return;
      Navigator.of(context).pop(raw.trim());
      return;
    }

    final payload = ref.read(qrParserProvider).parse(raw);
    if (!_localValidate(payload)) return;

    setState(() => _handling = true);
    await _controller.stop();
    if (!mounted) return;

    SchedulerBinding.instance.addPostFrameCallback((_) async {
      ref.read(perfTracerProvider).mark('route_resolved');
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
            } else {
              _failedScans += 1;
              HapticFeedback.mediumImpact();
            }
            setState(() => _lastOutcome = outcome);
          },
        );

      final tracer = ref.read(perfTracerProvider);
      tracer.mark('screen_pushed');
      final elapsed = tracer.elapsedBetween('scan_detected', 'screen_pushed');
      if (elapsed != null) {
        tracer.measure(PerfMetricKey.scannerFlow, elapsed);
      }

      if (!mounted) return;
      setState(() => _handling = false);
      unawaited(_controller.start());
    });
  }

  Future<void> _handleBarcode(BarcodeCapture capture) async {
    final raw = capture.barcodes
        .map((b) => b.rawValue)
        .firstWhere((v) => v != null && v.trim().isNotEmpty, orElse: () => null);
    if (raw == null) return;
    await _handleDetectedRaw(raw);
  }

  Future<void> _openManualInput() async {
    await showCodeEntrySheet(context);
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
            child: TweenAnimationBuilder<double>(
              tween: Tween(begin: 0.4, end: 1),
              duration: const Duration(milliseconds: 1600),
              curve: Curves.easeInOut,
              builder: (context, glow, child) => Container(
                width: 264,
                height: 264,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(color: const Color(0xFFF4B400), width: 3),
                  boxShadow: [
                    BoxShadow(color: const Color(0x66F4B400).withOpacity(glow), blurRadius: 22, spreadRadius: 2),
                  ],
                ),
              ),
            ),
          ),
          if (_detectedFlash)
            IgnorePointer(
              child: Container(color: const Color(0x33F4B400)),
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
                      child: const Text("Scanne l'arène.", textAlign: TextAlign.center),
                    ),
                    const SizedBox(height: 10),
                    TextButton.icon(
                      onPressed: _openManualInput,
                      icon: const Icon(Icons.keyboard_alt_outlined),
                      label: const Text('Entrer un code'),
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
